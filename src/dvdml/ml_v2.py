"""Per-current transistor models (D-041): one dedicated MLP ensemble per terminal current, physics-normalised targets.

Why (see docs/DECISIONS.md D-041): gate leakage of this 22nm LP card is ~98 % gate tunnelling of ON devices, and the gate operating points
(Vd, Vs at the rails) sit on the edges of the uniformly sampled (Vd, Vs) box. The single 4-output MLP of `ml.py` was 2-3x less accurate there
than on average. This module changes four things, all decided on TRANSISTOR data only (never gate/circuit SPICE data):

1. one network per current (no capacity spent on currents that are irrelevant for that output);
2. width-normalised targets: I / (W / Lmin), or with wnorm="weff" (D-043, used by the final models) I / ((W - 2 wint) / Lmin) for id, ig, is
   (BSIM4 scales channel and tunnelling currents with Weff; wint = 5 nm) and I / (W / Lmin) for ib (junction area AD = W x Ldiff);
3. target transform per current:
     "log"   : constant-sign currents (ON ig, all ib):  y = log10(|I| / (W/Lmin)), trained on resolved rows (|I| > I_FLOOR) only;
     "asinh" : sign-changing currents (id, is):          y = asinh(I / (W/Lmin) / I_FLOOR) / ln10 (the signed log of ml.py);
4. extra physics features (oxide fields Vgs/toxe, Vgd/toxe, gate overdrives, vth0/kT) and a sample weight that emphasises the edges of the
   (Vd, Vs) range (rails), where the gate operating points lie; plus an ensemble of seeds (prediction = mean in target space).

`CompositeTransistorModel.predict(df)` has the same interface as `ml.TransistorModel.predict` (columns id, ig, is, ib in A, positive INTO the
device), so the gate- and circuit-level code uses it unchanged.
"""
import numpy as np
import pandas as pd

from .metrics import CURRENTS, I_FLOOR
from .ml import featurize

LMIN = 22e-9
WINT = 5e-9            # BSIM4 wint of both cards in context/models/22nm_LP.pm (Weff = W - 2*wint; dwg = dwb = 0)
_LN10 = np.log(10.0)
K_B = 8.617333262e-5  # eV/K


def physics_features(df: pd.DataFrame, extra: bool = True) -> np.ndarray:
    """ml.featurize() + (if extra) oxide fields, gate overdrives and vth0/kT."""
    if not extra:
        return featurize(df)
    t = df["toxe"].to_numpy(float) * 1e9
    vgs = (df["vg"] - df["vs"]).to_numpy(float)
    vgd = (df["vg"] - df["vd"]).to_numpy(float)
    vth = df["vth0"].abs().to_numpy(float)
    kt = K_B * (df["temp"].to_numpy(float) + 273.15)
    extra = np.column_stack([vgs / t, vgd / t, np.abs(vgs) - vth, np.abs(vgd) - vth, vth / kt, df["vdd"].to_numpy(float) / t])
    return np.column_stack([featurize(df), extra])


def edge_weight(df: pd.DataFrame, strength: float, scale: float = 0.05) -> np.ndarray:
    """1 + strength * (e(vd) + e(vs)), e(v) = exp(-distance of v to the nearer rail / (scale * VDD)). Chosen a priori (rails = logic levels)."""
    vdd = df["vdd"].to_numpy(float)

    def e(v):
        v = v.to_numpy(float)
        return np.exp(-np.clip(np.minimum(v, vdd - v), 0, None) / (scale * vdd))
    return 1.0 + strength * (e(df["vd"]) + e(df["vs"]))


class CurrentModel:
    """Ensemble of small tanh MLPs for ONE current. Stores weights as numpy arrays (portable, no torch needed to predict)."""

    def __init__(self, current: str, mode: str, params: dict):
        self.current, self.mode, self.params = current, mode, dict(params)
        self.sign = 1.0
        self.members = []          # list of [(W, b), ...] per member, numpy float64
        self.x_mu = self.x_sd = None
        self.y_mu = self.y_sd = None
        self.history = []

    # ---------- target transform ----------
    def _scale(self, df):
        """Width normalisation. True: W / Lmin. "weff": (W - 2*WINT) / Lmin for the channel/tunnelling currents id, ig, is (BSIM4 scales them
        with Weff; wint = 5 nm in BOTH 22nm_LP cards, so Weff/W runs from 0.55 at W = Lmin to 0.94 at 8 Lmin), W / Lmin for ib (junction
        leakage scales with AD = W x Ldiff). False: none."""
        wn = self.params.get("wnorm", True)
        w = df["w"].to_numpy(float)
        if wn == "weff" and self.current != "ib":
            return (w - 2 * WINT) / LMIN
        return w / LMIN if wn else np.ones(len(df))

    def to_target(self, df):
        i = df[self.current].to_numpy(float) / self._scale(df)
        if self.mode == "log":
            return np.log10(np.maximum(np.abs(i), 1e-300))
        return np.arcsinh(i / I_FLOOR) / _LN10

    def from_target(self, y, df):
        s = self._scale(df)
        if self.mode == "log":
            return self.sign * 10.0 ** y * s
        return I_FLOOR * np.sinh(y * _LN10) * s

    # ---------- training ----------
    def _rows(self, df):
        if self.mode == "log":
            return df[df[self.current].abs() > I_FLOOR].reset_index(drop=True)
        return df.reset_index(drop=True)

    def fit(self, train: pd.DataFrame, val: pd.DataFrame, device: str = "cpu", verbose: bool = False):
        import torch
        p = self.params
        torch.set_num_threads(p.get("threads", 4))     # low-load mode (the dev laptop hard-resets under sustained all-core load)
        if self.mode == "log":
            res = train[self.current][train[self.current].abs() > I_FLOOR]
            self.sign = float(np.sign(np.median(np.sign(res))))
        tr, va = self._rows(train), self._rows(val)
        fx = self.params.get("feat", True)
        Xtr, Xva = physics_features(tr, fx), physics_features(va, fx)
        self.x_mu, self.x_sd = Xtr.mean(0), Xtr.std(0)
        self.x_sd[self.x_sd == 0] = 1.0
        ytr = self.to_target(tr)
        self.y_mu, self.y_sd = float(ytr.mean()), float(ytr.std())
        dev, dt = torch.device(device), torch.float64
        T = lambda a: torch.tensor(a, dtype=dt, device=dev)
        xt, yt = T((Xtr - self.x_mu) / self.x_sd), T((ytr - self.y_mu) / self.y_sd)[:, None]
        w = edge_weight(tr, p.get("edge", 4.0))
        wt = T(w / w.mean())[:, None]
        xv, yv = T((Xva - self.x_mu) / self.x_sd), T((self.to_target(va) - self.y_mu) / self.y_sd)[:, None]
        self.members = []
        for seed in range(p.get("n_members", 1)):
            net, best = self._train_one(xt, yt, wt, xv, yv, seed + 1000 * p.get("seed", 0), dev, dt)
            self.members.append([(m.weight.detach().cpu().numpy().copy(), m.bias.detach().cpu().numpy().copy())
                                 for m in net if isinstance(m, torch.nn.Linear)])
            self.history.append(best)
            if verbose:
                print(f"    {self.current} member {seed}: val mse (std. units) {best:.3g}", flush=True)
        return self

    def _train_one(self, xt, yt, wt, xv, yv, seed, dev, dt):
        import torch
        p = self.params
        torch.manual_seed(seed)
        layers, n = [], xt.shape[1]
        for _ in range(p.get("depth", 4)):
            layers += [torch.nn.Linear(n, p.get("width", 128)), torch.nn.Tanh()]
            n = p.get("width", 128)
        # Adam phase in float32 (fast, low power on consumer GPUs); the L-BFGS polish below runs in float64
        f32 = torch.float32 if p.get("adam_fp32", True) else dt
        net = torch.nn.Sequential(*layers, torch.nn.Linear(n, 1)).to(dev, f32)
        xt32, yt32, wt32, xv32, yv32 = (t.to(f32) for t in (xt, yt, wt, xv, yv))
        epochs, bs = p.get("epochs", 1500), p.get("batch", 512)
        opt = torch.optim.Adam(net.parameters(), lr=p.get("lr", 3e-3))
        sch = torch.optim.lr_scheduler.CosineAnnealingLR(opt, epochs, p.get("lr_min", 1e-6))
        g = torch.Generator().manual_seed(seed)
        best, state = np.inf, None
        for ep in range(epochs):
            perm = torch.randperm(len(xt32), generator=g).to(dev)
            for i in range(0, len(xt32), bs):
                idx = perm[i:i + bs]
                opt.zero_grad()
                loss = (wt32[idx] * (net(xt32[idx]) - yt32[idx]) ** 2).mean()
                loss.backward()
                opt.step()
            sch.step()
            if ep % 10 == 9 or ep == epochs - 1:
                with torch.no_grad():
                    v = ((net(xv32) - yv32) ** 2).mean().item()
                if v < best:
                    best, state = v, {k: t.clone() for k, t in net.state_dict().items()}
        net.load_state_dict(state)
        net = net.to(dt)
        with torch.no_grad():
            best = ((net(xv) - yv) ** 2).mean().item()
        for _ in range(p.get("polish_rounds", 6)):     # full-batch L-BFGS polish, kept only while validation improves
            before = {k: t.clone() for k, t in net.state_dict().items()}
            lb = torch.optim.LBFGS(net.parameters(), lr=1.0, max_iter=p.get("polish_iter", 300), history_size=50,
                                   tolerance_grad=1e-14, tolerance_change=1e-16, line_search_fn="strong_wolfe")

            def closure():
                lb.zero_grad()
                l = (wt * (net(xt) - yt) ** 2).mean()
                l.backward()
                return l
            try:
                lb.step(closure)
            except RuntimeError:
                net.load_state_dict(before)
                break
            with torch.no_grad():
                v = ((net(xv) - yv) ** 2).mean().item()
            if np.isfinite(v) and v < best:
                best = v
            else:
                net.load_state_dict(before)
                break
        return net, best

    # ---------- prediction (pure numpy) ----------
    def predict_target(self, df: pd.DataFrame) -> np.ndarray:
        x = (physics_features(df, self.params.get("feat", True)) - self.x_mu) / self.x_sd
        outs = []
        for layers in self.members:
            h = x
            for k, (W, b) in enumerate(layers):
                h = h @ W.T + b
                if k < len(layers) - 1:
                    h = np.tanh(h)
            outs.append(h[:, 0])
        return np.mean(outs, axis=0) * self.y_sd + self.y_mu

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        return self.from_target(self.predict_target(df), df)


class CompositeTransistorModel:
    """Four CurrentModels (id, ig, is, ib) for one transistor case; same predict() interface as ml.TransistorModel."""

    def __init__(self, case: str, models: dict[str, CurrentModel]):
        self.case, self.models = case, models
        self.family = "mlp_per_current"

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame({c: self.models[c].predict(df) for c in CURRENTS}, index=df.index)


# Target transform per (case, current). Constant-sign currents with enough resolved samples -> "log"; sign-changing -> "asinh".
# OFF-state ig is never resolved (|ig| < 1e-15 A in 100 % of rows: arithmetic noise) -> "asinh" (the model then predicts ~0).
MODES = {
    "nmos_on": {"id": "asinh", "ig": "log", "is": "asinh", "ib": "log"},
    "pmos_on": {"id": "asinh", "ig": "log", "is": "asinh", "ib": "log"},
    "nmos_off": {"id": "asinh", "ig": "asinh", "is": "asinh", "ib": "log"},
    "pmos_off": {"id": "asinh", "ig": "asinh", "is": "asinh", "ib": "log"},
}
