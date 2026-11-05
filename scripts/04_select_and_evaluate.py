"""Phase 3.4: choose the best family per case on VALIDATION, evaluate it ONCE on TEST, plot, save the 4 model files.

Outputs
  models_saved/<case>.joblib            the four chosen models (TransistorModel; predict(df) -> id, ig, is, ib in A)
  models_saved/manifest.json            family, hyper-parameters, validation score, test metrics per case
  results/models/test_results.csv       per case and current: test metrics (median/P95 error, R2, ...) + macro rows
  results/models/pred_vs_spice_<case>.png   predicted-vs-SPICE plot per case (all four currents, log-log, signed by marker)
"""
import json
import sys
from pathlib import Path

import joblib
import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from dvdml import metrics  # noqa: E402
from dvdml.config import load_config  # noqa: E402
from dvdml.sampling import CASES  # noqa: E402


def plot_case(case, pred, true, out):
    fig, axes = plt.subplots(2, 2, figsize=(9, 8))
    for ax, c in zip(axes.ravel(), metrics.CURRENTS):
        t, p = true[c].to_numpy(), pred[c].to_numpy()
        fl = metrics.I_FLOOR
        tt, pp = np.maximum(np.abs(t), fl * 1e-2), np.maximum(np.abs(p), fl * 1e-2)
        same = np.sign(t) == np.sign(p)
        ax.loglog(tt[same], pp[same], ".", ms=2, alpha=.5, label="sign OK")
        ax.loglog(tt[~same], pp[~same], "r.", ms=3, alpha=.6, label="sign differs")
        lo, hi = min(tt.min(), pp.min()), max(tt.max(), pp.max())
        ax.loglog([lo, hi], [lo, hi], "k-", lw=.6)
        ax.axvline(fl, color="gray", ls=":", lw=1); ax.axhline(fl, color="gray", ls=":", lw=1)
        ax.set_title(f"{case}  |{c}|  (dotted = noise floor {fl:g} A)", fontsize=9)
        ax.set_xlabel("SPICE |I| (A)"); ax.set_ylabel("ML |I| (A)"); ax.legend(fontsize=7)
    fig.tight_layout(); fig.savefig(out, dpi=110); plt.close(fig)


def main():
    cfg = load_config()
    res = ROOT / "results" / "models"
    (ROOT / "models_saved").mkdir(exist_ok=True)
    comp = pd.read_csv(res / "comparison_val.csv")
    rows, manifest = [], {}
    for case in CASES:
        c = comp[comp.case == case].sort_values("val_score")
        best = c.iloc[0]
        model = joblib.load(ROOT / "models_candidates" / f"{case}__{best.family}.joblib")
        df = pd.read_csv(ROOT / "data" / "transistor" / f"{case}.csv")
        te = df.iloc[np.load(ROOT / "data" / "splits" / f"{case}.npz")["test"]].reset_index(drop=True)
        pred = model.predict(te)
        s = metrics.summarize(pred, te)
        mac = metrics.macro(s, cfg["ml"]["min_resolved_frac"])
        for cur, r in s.iterrows():
            rows.append({"case": case, "family": best.family, "current": cur, **r.to_dict()})
        rows.append({"case": case, "family": best.family, "current": "MACRO(" + mac["currents_scored"] + ")", "r2_signed_log": mac["r2_signed_log"],
                     "median_err_resolved": mac["median_err"], "p95_err_resolved": mac["p95_err"]})
        plot_case(case, pred, te, res / f"pred_vs_spice_{case}.png")
        joblib.dump(model, ROOT / "models_saved" / f"{case}.joblib")
        manifest[case] = {"family": best.family, "params": best.best_params, "val_score": float(best.val_score),
                          "test_macro_median_err": float(mac["median_err"]), "test_macro_p95_err": float(mac["p95_err"]),
                          "test_macro_r2_signed_log": float(mac["r2_signed_log"]), "currents_scored": mac["currents_scored"],
                          "n_test": len(te)}
        print(f"{case}: chose {best.family}  val_score={best.val_score:.4g}  test median={mac['median_err']:.4g} p95={mac['p95_err']:.4g} R2(log)={mac['r2_signed_log']:.5f}")
    pd.DataFrame(rows).to_csv(res / "test_results.csv", index=False)
    (ROOT / "models_saved" / "manifest.json").write_text(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
