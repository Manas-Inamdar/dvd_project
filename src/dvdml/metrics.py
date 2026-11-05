"""Error metrics for current predictions (docs/DECISIONS.md D-021, D-024, D-027).

Terminology
  floor      I_FLOOR = 1e-15 A. Currents with |I| below it are at the numerical-noise level of the BSIM4/ngspice
             evaluation (see PROJECT_STATUS findings 8-9) and cannot be learned.
  resolved   samples with |true| > floor. Headline errors are computed on resolved samples.
  floored    relative error on ALL samples with the denominator max(|true|, floor) (shows behaviour below the floor).
  rel. error |pred - true| / |true|   (fraction, 0.01 = 1 %)
"""
import numpy as np
import pandas as pd
from sklearn.metrics import r2_score

CURRENTS = ("id", "ig", "is", "ib")
I_FLOOR = 1e-15
_LN10 = np.log(10.0)


def to_signed_log(i, floor: float = I_FLOOR):
    """y = asinh(I/floor)/ln10: ~ sign(I)*log10(2|I|/floor) for |I| >> floor, ~linear (and 0 at 0) below the floor."""
    return np.arcsinh(np.asarray(i, dtype=float) / floor) / _LN10


def from_signed_log(y, floor: float = I_FLOOR):
    return floor * np.sinh(np.asarray(y, dtype=float) * _LN10)


def rel_error(pred, true):
    return np.abs(pred - true) / np.abs(true)


def floored_rel_error(pred, true, floor: float = I_FLOOR):
    return np.abs(pred - true) / np.maximum(np.abs(true), floor)


def summarize(pred: pd.DataFrame, true: pd.DataFrame, floor: float = I_FLOOR) -> pd.DataFrame:
    """One row per current with R2 (signed-log and linear domain), resolved fraction and error percentiles."""
    rows = []
    for c in CURRENTS:
        p, t = pred[c].to_numpy(float), true[c].to_numpy(float)
        res = np.abs(t) > floor
        e_res = rel_error(p[res], t[res]) if res.any() else np.array([np.nan])
        e_all = floored_rel_error(p, t, floor)
        rows.append({
            "current": c,
            "frac_resolved": res.mean(),
            "r2_signed_log": r2_score(to_signed_log(t, floor), to_signed_log(p, floor)),
            "r2_linear": r2_score(t, p),
            "median_err_resolved": np.median(e_res),
            "p95_err_resolved": np.percentile(e_res, 95),
            "bias_resolved": float(np.mean((p[res] - t[res]) / np.abs(t[res]))) if res.any() else np.nan,
            "median_err_floored_all": np.median(e_all),
            "p95_err_floored_all": np.percentile(e_all, 95),
            "frac_sign_wrong_resolved": float(np.mean(np.sign(p[res]) != np.sign(t[res]))) if res.any() else np.nan,
        })
    return pd.DataFrame(rows).set_index("current")


def macro(summary: pd.DataFrame, min_resolved_frac: float = 0.05) -> dict:
    """Macro-average over the currents that have enough resolved samples (noise-only currents are excluded)."""
    use = summary[summary["frac_resolved"] >= min_resolved_frac]
    return {
        "currents_scored": ",".join(use.index),
        "r2_signed_log": use["r2_signed_log"].mean(),
        "median_err": use["median_err_resolved"].mean(),
        "p95_err": use["p95_err_resolved"].mean(),
        "score": 0.5 * (use["median_err_resolved"].mean() + use["p95_err_resolved"].mean()),  # lower is better
    }
