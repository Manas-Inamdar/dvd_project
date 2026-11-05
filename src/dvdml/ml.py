"""Transistor current models: feature engineering, four model families, a picklable wrapper with a predict API.

A `TransistorModel` maps the raw dataset columns (vdd, temp, w, vd, vs, vg, vb, vth0, toxe, ndep, u0, xj)
to the four terminal currents (id, ig, is, ib) in amperes, positive INTO the device. It is used unchanged by the
gate-level (Phase 4) and circuit-level (Phase 5) code.

Targets are standardised signed-log values  y = asinh(I/I_FLOOR)/ln10  (metrics.to_signed_log), see D-024 / D-027.
"""
import numpy as np
import pandas as pd
from sklearn.kernel_ridge import KernelRidge
from sklearn.linear_model import Ridge
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import PolynomialFeatures, StandardScaler

from .metrics import CURRENTS, I_FLOOR, from_signed_log, to_signed_log

RAW_COLUMNS = ["vdd", "temp", "w", "vd", "vs", "vg", "vb", "vth0", "toxe", "ndep", "u0", "xj"]
FEATURES = ["log_w", "inv_kT", "vdd", "vd", "vs", "vds", "vgs", "vgd", "vbs", "vbd", "abs_vth0", "toxe_nm", "log_ndep", "u0", "xj_nm"]
FAMILIES = ("mlp", "lightgbm", "kernel_ridge", "poly_ridge")   # "mlp_sklearn" = round-1 baseline, not part of the study


def featurize(df: pd.DataFrame) -> np.ndarray:
    """Physics-motivated inputs: log width, 1000/T[K], terminal voltages and their differences, scaled process values."""
    f = pd.DataFrame(index=df.index)
    f["log_w"] = np.log10(df["w"])
    f["inv_kT"] = 1000.0 / (df["temp"] + 273.15)
    f["vdd"], f["vd"], f["vs"] = df["vdd"], df["vd"], df["vs"]
    f["vds"], f["vgs"], f["vgd"] = df["vd"] - df["vs"], df["vg"] - df["vs"], df["vg"] - df["vd"]
    f["vbs"], f["vbd"] = df["vb"] - df["vs"], df["vb"] - df["vd"]
    f["abs_vth0"], f["toxe_nm"], f["log_ndep"] = df["vth0"].abs(), df["toxe"] * 1e9, np.log10(df["ndep"])
    f["u0"], f["xj_nm"] = df["u0"], df["xj"] * 1e9
    return f[FEATURES].to_numpy(float)


def make_estimator(family: str, params: dict, seed: int = 0):
    """Un-fitted estimator on standardised features -> 4 standardised targets (LightGBM: one model per target)."""
    if family == "mlp":
        return _TorchMLP(params, seed)
    if family == "mlp_sklearn":   # round-1 baseline (L-BFGS, under-trained); kept for reference only
        return MLPRegressor(hidden_layer_sizes=tuple(params["hidden"]), activation="tanh", solver="lbfgs",
                            alpha=params.get("alpha", 1e-7), max_iter=params.get("max_iter", 4000), tol=1e-10, random_state=seed)
    if family == "kernel_ridge":
        return KernelRidge(kernel="rbf", alpha=params["alpha"], gamma=params["gamma"])
    if family == "poly_ridge":
        return make_pipeline(PolynomialFeatures(degree=params["degree"], include_bias=False), StandardScaler(),
                             Ridge(alpha=params["alpha"], solver="auto"))
    if family == "lightgbm":
        return _LGBMMulti(params, seed)
    raise ValueError(family)


class _TorchMLP:
    """Fully connected net (float64) trained with Adam + cosine learning-rate decay on standardised targets.

    The state at the epoch with the best validation loss is kept (validation is only used to pick the epoch)."""

    def __init__(self, params: dict, seed: int = 0):
        self.params, self.seed, self.net = params, seed, None

    def _build(self, n_in, n_out):
        import torch
        act = {"silu": torch.nn.SiLU, "tanh": torch.nn.Tanh}[self.params.get("activation", "tanh")]
        dims, layers = [n_in] + list(self.params["hidden"]), []
        for a, b in zip(dims[:-1], dims[1:]):
            layers += [torch.nn.Linear(a, b), act()]
        layers.append(torch.nn.Linear(dims[-1], n_out))
        return torch.nn.Sequential(*layers).double()

    def fit(self, X, Y, X_val=None, Y_val=None, col_weights=None):
        import torch
        p = self.params
        torch.set_num_threads(p.get("threads", 4))
        w = torch.ones(Y.shape[1], dtype=torch.float64) if col_weights is None else torch.as_tensor(col_weights, dtype=torch.float64)
        torch.manual_seed(self.seed)
        self.net = self._build(X.shape[1], Y.shape[1])
        Xt, Yt = torch.from_numpy(X), torch.from_numpy(Y)
        Xv = torch.from_numpy(X_val) if X_val is not None else None
        Yv = torch.from_numpy(Y_val) if Y_val is not None else None
        epochs, bs = p.get("epochs", 1500), p.get("batch", 256)
        opt = torch.optim.Adam(self.net.parameters(), lr=p.get("lr", 3e-3))
        sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs, eta_min=p.get("lr_min", 1e-6))
        best, best_state, g = np.inf, None, torch.Generator().manual_seed(self.seed)
        for ep in range(epochs):
            perm = torch.randperm(len(Xt), generator=g)
            for i in range(0, len(Xt), bs):
                idx = perm[i:i + bs]
                opt.zero_grad()
                loss = torch.mean(w * (self.net(Xt[idx]) - Yt[idx]) ** 2)
                loss.backward()
                opt.step()
            sched.step()
            if Xv is not None and (ep % 10 == 9 or ep == epochs - 1):
                with torch.no_grad():
                    v = torch.mean(w * (self.net(Xv) - Yv) ** 2).item()
                if v < best:
                    best, best_state = v, {k: t.clone() for k, t in self.net.state_dict().items()}
        if best_state is not None:
            self.net.load_state_dict(best_state)
        # full-batch L-BFGS polish for the last digits of precision; kept only if validation improves
        for _ in range(p.get("polish_rounds", 3) if Xv is not None else 0):
            before = {k: t.clone() for k, t in self.net.state_dict().items()}
            lb = torch.optim.LBFGS(self.net.parameters(), lr=1.0, max_iter=p.get("polish_iter", 150), history_size=50,
                                   tolerance_grad=1e-12, tolerance_change=1e-15, line_search_fn="strong_wolfe")

            def closure():
                lb.zero_grad()
                l = torch.mean(w * (self.net(Xt) - Yt) ** 2)
                l.backward()
                return l
            try:
                lb.step(closure)
            except RuntimeError:
                self.net.load_state_dict(before)
                break
            with torch.no_grad():
                v = torch.mean(w * (self.net(Xv) - Yv) ** 2).item()
            if v < best:
                best = v
            else:
                self.net.load_state_dict(before)
                break
        self.best_val_mse = best
        return self

    def predict(self, X):
        import torch
        with torch.no_grad():
            return self.net(torch.from_numpy(np.ascontiguousarray(X, dtype=np.float64))).numpy()


class _LGBMMulti:
    """One LightGBM regressor per target column (LightGBM has no native multi-output regression)."""

    def __init__(self, params: dict, seed: int = 0):
        self.params, self.seed, self.models = params, seed, []

    def fit(self, X, Y, X_val=None, Y_val=None):
        import lightgbm as lgb
        self.models = []
        for k in range(Y.shape[1]):
            m = lgb.LGBMRegressor(n_estimators=self.params.get("n_estimators", 4000), learning_rate=self.params.get("learning_rate", 0.05),
                                  num_leaves=self.params["num_leaves"], min_child_samples=self.params.get("min_child_samples", 10),
                                  subsample=0.9, subsample_freq=1, colsample_bytree=0.9, reg_lambda=1e-3,
                                  random_state=self.seed, n_jobs=2, verbose=-1)
            if X_val is not None:
                m.fit(X, Y[:, k], eval_set=[(X_val, Y_val[:, k])], callbacks=[lgb.early_stopping(150, verbose=False)])
            else:
                m.fit(X, Y[:, k])
            self.models.append(m)
        return self

    def predict(self, X):
        return np.column_stack([m.predict(X) for m in self.models])


class TransistorModel:
    """Fitted model + preprocessing. `predict(df)` -> DataFrame with columns id, ig, is, ib (amperes)."""

    def __init__(self, case: str, family: str, params: dict, seed: int = 0):
        self.case, self.family, self.params, self.seed = case, family, params, seed
        self.x_scaler, self.y_scaler = StandardScaler(), StandardScaler()
        self.estimator = None

    def fit(self, train: pd.DataFrame, val: pd.DataFrame | None = None):
        X = self.x_scaler.fit_transform(featurize(train))
        Y = self.y_scaler.fit_transform(to_signed_log(train[list(CURRENTS)].to_numpy()))
        self.estimator = make_estimator(self.family, self.params, self.seed)
        if self.family in ("lightgbm", "mlp") and val is not None:
            Xv = self.x_scaler.transform(featurize(val))
            Yv = self.y_scaler.transform(to_signed_log(val[list(CURRENTS)].to_numpy()))
            if self.family == "mlp":
                # columns that are (almost) pure numerical noise must not dominate the loss: weight 1 if resolvable, else 0.02
                resolved = (np.abs(train[list(CURRENTS)].to_numpy()) > I_FLOOR).mean(axis=0)
                self.estimator.fit(X, Y, Xv, Yv, col_weights=np.where(resolved >= 0.05, 1.0, 0.02))
            else:
                self.estimator.fit(X, Y, Xv, Yv)
        else:
            self.estimator.fit(X, Y)
        return self

    def predict_signed_log(self, df: pd.DataFrame) -> np.ndarray:
        X = self.x_scaler.transform(featurize(df))
        return self.y_scaler.inverse_transform(np.asarray(self.estimator.predict(X)).reshape(len(df), -1))

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        y = self.predict_signed_log(df)
        return pd.DataFrame(from_signed_log(y), columns=list(CURRENTS), index=df.index)


# Hyper-parameter grids (tuned on the VALIDATION set only). Kept deliberately small so the whole study runs in minutes.
GRIDS = {
    "poly_ridge": [{"degree": d, "alpha": a} for d in (3, 4) for a in (1e-3, 1e-1, 10.0)],
    "kernel_ridge": [{"gamma": g, "alpha": a} for g in (0.01, 0.03, 0.1) for a in (1e-5, 1e-3)],
    "mlp": [{"hidden": h, "epochs": 1200, "activation": "tanh", "polish_rounds": 6, "polish_iter": 300, "threads": 2}
            for h in ((96, 96, 96), (128, 128, 128))],
    "lightgbm": [{"num_leaves": n} for n in (31, 127)],
}
