import numpy as np
import pandas as pd
import pytest

from dvdml import metrics
from dvdml.ml import FEATURES, GRIDS, TransistorModel, featurize


def test_signed_log_roundtrip_and_properties():
    i = np.array([-1e-6, -3e-12, -1e-15, 0.0, 1e-18, 1e-15, 5e-9, 1e-4])
    y = metrics.to_signed_log(i)
    assert np.allclose(metrics.from_signed_log(y), i, rtol=1e-9, atol=1e-30)
    assert y[3] == 0 and np.all(np.diff(y) > 0)                      # monotone, zero maps to zero
    assert abs(y[4]) < 0.01                                           # far below floor ~ 0
    assert y[-1] == pytest.approx(np.log10(2e11), rel=1e-3)           # ~ log10(2|I|/floor) above the floor


def test_error_metrics_floor_and_resolved():
    true = pd.DataFrame({c: [1e-6, 1e-9, 0.0, 5e-17] for c in metrics.CURRENTS})
    pred = pd.DataFrame({c: [1.01e-6, 0.9e-9, 3e-16, 0.0] for c in metrics.CURRENTS})
    s = metrics.summarize(pred, true)
    assert s.loc["id", "frac_resolved"] == 0.5
    assert s.loc["id", "median_err_resolved"] == pytest.approx(0.055, abs=1e-6)      # median of 0.01 and 0.1
    assert s.loc["id", "median_err_floored_all"] < 0.2                                # tiny rows are only ~0.3 / ~0.05 off the floor
    assert metrics.macro(s)["score"] > 0


def _toy(n=2000, seed=0):
    rng = np.random.default_rng(seed)
    d = pd.DataFrame({"vdd": rng.uniform(.9, 1.1, n), "temp": rng.uniform(-40, 125, n), "w": 22e-9 * rng.uniform(1, 8, n)})
    d["vd"], d["vs"] = d.vdd * rng.uniform(0, 1, n), d.vdd * rng.uniform(0, 1, n)
    d["vg"], d["vb"] = d.vdd, 0.0
    d["vth0"], d["toxe"], d["ndep"] = 0.69 * rng.uniform(.9, 1.1, n), 1.4e-9 * rng.uniform(.9, 1.1, n), 5.5e18 * rng.uniform(.9, 1.1, n)
    d["u0"], d["xj"] = 0.035 * rng.uniform(.9, 1.1, n), 7.2e-9 * rng.uniform(.9, 1.1, n)
    cur = 1e-6 * d.w / 22e-9 * (d.vd - d.vs) * np.exp(-(d.vth0 - 0.69) * 8)       # smooth, sign-changing toy "id"
    d["id"], d["is"], d["ig"], d["ib"] = cur, -cur, 1e-12 * d.vdd, -1e-14 * d.vdd
    return d


def test_featurize_columns():
    assert featurize(_toy(5)).shape == (5, len(FEATURES))


@pytest.mark.parametrize("family", ["poly_ridge", "kernel_ridge", "mlp", "lightgbm"])
def test_each_family_fits_and_predicts_a_toy_problem(family):
    d = _toy()
    params = {"poly_ridge": {"degree": 3, "alpha": 1e-3}, "kernel_ridge": {"gamma": 0.03, "alpha": 1e-4},
              "mlp": {"hidden": (16, 16), "epochs": 60, "threads": 2}, "lightgbm": {"num_leaves": 15, "n_estimators": 200}}[family]
    tr, te = d.iloc[:1700], d.iloc[1700:]
    m = TransistorModel("nmos_on", family, params).fit(tr, te)
    p = m.predict(te)
    assert list(p.columns) == list(metrics.CURRENTS) and np.isfinite(p.to_numpy()).all()
    s = metrics.summarize(p, te)
    assert s.loc["id", "r2_signed_log"] > 0.6                           # learned something on every family


def test_grids_cover_all_families_with_four_distinct_types():
    assert set(GRIDS) == {"poly_ridge", "kernel_ridge", "mlp", "lightgbm"}
