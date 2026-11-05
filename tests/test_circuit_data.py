"""Validate the circuit-level reference and the hierarchical prediction data (skipped if not generated)."""
import numpy as np
import pandas as pd
import pytest

from dvdml.config import REPO_ROOT

SPICE = REPO_ROOT / "data" / "circuit" / "circuit_spice.csv"
ML = REPO_ROOT / "results" / "circuit" / "circuit_runs_ml.csv"
pytestmark = pytest.mark.skipif(not (SPICE.exists() and ML.exists()), reason="circuit data not generated")


def test_reference_is_complete_and_physical():
    r = pd.read_csv(SPICE, dtype={"bits": str})
    assert len(r) == 256 * 200 and r.groupby("corner").size().eq(256).all() and r.groupby("vector").size().eq(200).all()
    assert (r.leak_spice > 0).all()
    assert (abs(r.v_out - r.parity * r.vdd) < 0.02 * r.vdd).all()                      # circuit computes the parity of its inputs
    assert (abs(r.leak_spice - r.leak_ground_side) / r.leak_spice < 5e-3).mean() > 0.99  # supply side == ground side


def test_hierarchical_prediction_and_loading_effect():
    r = pd.read_csv(ML, dtype={"bits": str})
    assert np.isfinite(r.leak_ml).all() and (r.leak_ml > 0).all()
    # rail-to-rail inputs: sum of isolated-gate SPICE leakages == circuit SPICE leakage (loading between gates is negligible)
    assert (abs(r.leak_sum_of_isolated_gate_spice - r.leak_spice) / r.leak_spice).quantile(0.99) < 1e-3
    err = abs(r.leak_ml - r.leak_spice) / r.leak_spice
    assert err.median() < 0.15 and err.quantile(0.95) < 0.5
