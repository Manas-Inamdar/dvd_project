import math

import joblib
import numpy as np
import pandas as pd
import pytest

from dvdml import gate_ml, gates
from dvdml.config import REPO_ROOT, load_config
from dvdml.refsolve import solve_with_crosscheck
from dvdml.sampling import CASES

CFG = load_config()
HAVE = (all((REPO_ROOT / "models" / f"{c}.joblib").exists() for c in CASES)
        and (REPO_ROOT / "data" / "gates" / "gate_spice.csv").exists())


def _fake(values_by_tier):
    """Helpers for solve_with_crosscheck: tier -> leakage value (None = solver failure)."""
    def make(tier):
        return tier

    def run(net, cfg):
        if values_by_tier[net] is None:
            raise RuntimeError("no convergence")
        return values_by_tier[net]
    return make, run, (lambda s: {"leak": s}), (lambda v: v["leak"])


@pytest.mark.parametrize("t0,t1,source", [(1.0e-10, 1.0e-10 * 1.001, "mandated"), (2.0e-9, 1.0e-11, "tight"), (None, 5e-11, "tight_only"), (4e-11, None, "mandated_only")])
def test_crosscheck_chooses_valid_reference(t0, t1, source):
    make, run, parse, leak = _fake({0: t0, 1: t1})
    v, src, d = solve_with_crosscheck(make, run, parse, leak, CFG)
    assert src == source
    assert v["leak"] == {"mandated": t0, "tight": t1, "tight_only": t1, "mandated_only": t0}[source]


def test_crosscheck_both_fail():
    make, run, parse, leak = _fake({0: None, 1: None})
    assert solve_with_crosscheck(make, run, parse, leak, CFG)[1] == "failed"


def test_route_by_gate_voltage():
    vdd = np.array([1.0, 1.0])
    assert list(gate_ml.route("nmos", np.array([1.0, 0.0]), vdd)) == ["nmos_on", "nmos_off"]
    assert list(gate_ml.route("pmos", np.array([1.0, 0.0]), vdd)) == ["pmos_off", "pmos_on"]


@pytest.mark.skipif(not HAVE, reason="models/gate data not generated")
def test_gate_prediction_is_close_to_spice_and_naive_sum_is_not():
    models = {c: joblib.load(REPO_ROOT / "models" / f"{c}.joblib") for c in CASES}
    runs = pd.read_csv(REPO_ROOT / "data" / "gates" / "gate_spice.csv", dtype={"inputs": str})
    corners = pd.read_csv(REPO_ROOT / "data" / "gates" / "corners.csv")
    sub = runs.groupby("case").head(6)                       # 6 corners per case = 108 runs
    res, dev = gate_ml.predict_runs(sub, corners, models, CFG["assignment"]["lmin"])
    err = (res.leak_ml - res.leak_spice).abs() / res.leak_spice
    assert err.median() < 0.12 and err.quantile(0.9) < 0.4   # KCL-consistent composition
    naive = (res.leak_ml_naive_supply - res.leak_spice).abs() / res.leak_spice
    assert naive.median() > 0.5                              # documents why the plain terminal sum is not used (D-030)
    assert set(dev.model.unique()) <= set(CASES) and np.isfinite(res.leak_ml).all()
    # supply-side and ground-side estimates of the same physical quantity agree closely
    assert ((res.leak_ml_supply_side - res.leak_ml_ground_side).abs() / res.leak_spice).median() < 0.05


@pytest.mark.skipif(not HAVE, reason="gate data not generated")
def test_reference_data_is_physical():
    r = pd.read_csv(REPO_ROOT / "data" / "gates" / "gate_spice.csv", dtype={"inputs": str})
    assert len(r) == 3600 and r.case.nunique() == 18 and r.groupby("case").size().eq(200).all()
    assert (r.leak_spice > 0).all()
    assert (abs(r.leak_spice - r.leak_ground_side) / r.leak_spice < 5e-3).mean() > 0.99      # supply side == ground side (Kirchhoff)
    func_ok = [abs(row.v_out - gates.GATES[row.gate]["func"](*[int(c) for c in row.inputs]) * row.vdd) < 0.02 * row.vdd for row in r.itertuples()]
    assert all(func_ok)                                      # every gate output is at the correct logic rail
