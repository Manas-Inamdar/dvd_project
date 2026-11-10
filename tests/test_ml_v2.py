"""Unit tests for the per-current models (src/dvdml/ml_v2.py, D-041)."""
import numpy as np
import pandas as pd
import pytest

from dvdml.metrics import CURRENTS
from dvdml.ml_v2 import MODES, CompositeTransistorModel, CurrentModel, edge_weight, physics_features


def _toy(n=400, seed=0):
    rng = np.random.default_rng(seed)
    vdd = rng.uniform(0.9, 1.1, n)
    d = pd.DataFrame({"vdd": vdd, "temp": rng.uniform(-40, 125, n), "w": 22e-9 * rng.uniform(1, 8, n), "vd": rng.uniform(0, 1, n) * vdd,
                      "vs": rng.uniform(0, 1, n) * vdd, "vg": vdd, "vb": 0.0, "vth0": 0.69 * rng.uniform(.9, 1.1, n),
                      "toxe": 1.4e-9 * rng.uniform(.9, 1.1, n), "ndep": 5.5e18 * rng.uniform(.9, 1.1, n), "u0": 0.035 * rng.uniform(.9, 1.1, n),
                      "xj": 7.2e-9 * rng.uniform(.9, 1.1, n)})
    scale = d.w / 22e-9
    d["ig"] = 1e-11 * scale * np.exp(-(d.toxe * 1e9 - 1.4) * 5) * (d.vg - 0.5 * (d.vd + d.vs))     # positive, smooth, prop. to W
    d["ib"] = -1e-13 * scale * (1 + d.vd)
    d["id"] = 1e-9 * scale * (d.vd - d.vs)                                                          # changes sign
    d["is"] = -d["id"] - d["ig"] - d["ib"]
    return d


def test_target_roundtrip_log_and_asinh():
    d = _toy(50)
    for cur, mode in (("ig", "log"), ("ib", "log"), ("id", "asinh")):
        m = CurrentModel(cur, mode, {})
        m.sign = 1.0 if cur == "ig" else -1.0
        back = m.from_target(m.to_target(d), d)
        np.testing.assert_allclose(back, d[cur].to_numpy(), rtol=1e-9, atol=1e-30)


def test_weff_normalisation_uses_effective_width_except_for_ib():
    d = pd.DataFrame({"w": [22e-9, 44e-9]})
    for cur in ("id", "ig", "is"):
        np.testing.assert_allclose(CurrentModel(cur, "asinh", {"wnorm": "weff"})._scale(d), [12 / 22, 34 / 22])
    np.testing.assert_allclose(CurrentModel("ib", "log", {"wnorm": "weff"})._scale(d), [1.0, 2.0])
    np.testing.assert_allclose(CurrentModel("ig", "log", {"wnorm": True})._scale(d), [1.0, 2.0])     # old models keep W / Lmin


def test_edge_weight_is_largest_at_the_rails():
    d = pd.DataFrame({"vdd": [1.0, 1.0, 1.0], "vd": [0.0, 0.5, 1.0], "vs": [0.0, 0.5, 1.0]})
    w = edge_weight(d, 4.0)
    assert w[0] == pytest.approx(9.0) and w[2] == pytest.approx(9.0) and w[1] == pytest.approx(1.0, abs=1e-3)


def test_physics_features_shapes():
    d = _toy(10)
    assert physics_features(d).shape == (10, 21)
    assert physics_features(d, extra=False).shape == (10, 15)


def test_modes_cover_all_cases_and_currents():
    assert set(MODES) == {"nmos_on", "nmos_off", "pmos_on", "pmos_off"}
    for modes in MODES.values():
        assert set(modes) == set(CURRENTS) and set(modes.values()) <= {"log", "asinh"}


def test_composite_fits_toy_and_predicts_without_torch_objects():
    tr, va = _toy(600, 1), _toy(200, 2)
    p = {"width": 16, "depth": 2, "epochs": 60, "batch": 128, "n_members": 2, "polish_rounds": 1, "polish_iter": 50}
    models = {c: CurrentModel(c, MODES["nmos_on"][c], p).fit(tr, va, device="cpu") for c in CURRENTS}
    comp = CompositeTransistorModel("nmos_on", models)
    pred = comp.predict(va)
    assert list(pred.columns) == list(CURRENTS) and len(pred) == len(va)
    assert (pred["ig"] > 0).all() and (pred["ib"] < 0).all()               # log-mode sign is preserved
    rel = np.abs(pred["ig"] - va["ig"]) / va["ig"]
    assert np.median(rel) < 0.05                                           # learns the smooth toy target
    for m in models.values():                                              # members are plain numpy (portable)
        assert all(isinstance(W, np.ndarray) and isinstance(b, np.ndarray) for mem in m.members for W, b in mem)
