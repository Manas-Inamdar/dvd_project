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
FAMILIES = ("mlp", "lightgbm", "kernel_ridge", "poly_ridge")


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
        if self.family == "lightgbm" and val is not None:
            Xv = self.x_scaler.transform(featurize(val))
            Yv = self.y_scaler.transform(to_signed_log(val[list(CURRENTS)].to_numpy()))
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
    "mlp": [{"hidden": h, "alpha": 1e-7} for h in ((64, 64), (128, 128), (96, 96, 96))],
    "lightgbm": [{"num_leaves": n} for n in (31, 127)],
}
