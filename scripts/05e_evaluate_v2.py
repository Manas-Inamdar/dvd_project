"""Phase 7 (D-041): evaluate the per-current models (models_v2/) ONCE on the original TEST split, same metrics as scripts/04 plus rail-corner errors.

Outputs
  results/models_v2/test_results.csv          per case and current: test metrics (metrics.summarize) + macro rows
  results/models_v2/test_rail_corners.csv     per case, current and (Vd, Vs) rail corner: median / mean / P95 error and bias on the test split
  results/models_v2/holdout_rail_corners.csv  same on the 5,000 held-out extra rows (larger corner samples)
  results/models_v2/edge_holdout_rail_corners.csv  same on the 2,000 held-out rail-corner rows of data/transistor_edge (if generated, D-043)
  results/models_v2/pred_vs_spice_<case>.png  predicted-vs-SPICE plot per case
  models_v2/manifest.json                     what each case uses
"""
import importlib.util
import json
import sys
from pathlib import Path

import joblib
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from dvdml import metrics  # noqa: E402
from dvdml.config import load_config  # noqa: E402
from dvdml.plots import plot_case  # noqa: E402
from dvdml.sampling import CASES  # noqa: E402

_spec = importlib.util.spec_from_file_location("train_v2", ROOT / "scripts" / "05d_train_per_current.py")
train_v2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(train_v2)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--models-dir", default="models_v2")
    ap.add_argument("--out-dir", default="results/models_v2")
    args = ap.parse_args()
    cfg = load_config()
    out = ROOT / args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    rows, corner_rows, manifest = [], [], {}
    for case in CASES:
        model = joblib.load(ROOT / args.models_dir / f"{case}.joblib")
        _, _, hold, te = train_v2.load_case(case)
        pred = model.predict(te)
        s = metrics.summarize(pred, te)
        mac = metrics.macro(s, cfg["ml"]["min_resolved_frac"])
        for cur, r in s.iterrows():
            rows.append({"case": case, "family": model.family, "mode": model.models[cur].mode, "current": cur, **r.to_dict()})
        rows.append({"case": case, "family": model.family, "current": "MACRO(" + mac["currents_scored"] + ")", "r2_signed_log": mac["r2_signed_log"],
                     "median_err_resolved": mac["median_err"], "p95_err_resolved": mac["p95_err"]})
        ph = model.predict(hold)
        splits = [("test", te, pred), ("holdout", hold, ph)]
        edge = train_v2.load_edge(case)
        if edge is not None:
            splits.append(("edge_holdout", edge[2], model.predict(edge[2])))
        for split, d, p in splits:
            for cur in metrics.CURRENTS:
                for reg, v in train_v2.errors(p[cur].to_numpy(), d, cur).items():
                    corner_rows.append({"split": split, "case": case, "current": cur, "region": reg, **v})
        plot_case(case, pred, te, out / f"pred_vs_spice_{case}.png")
        manifest[case] = {"family": model.family, "currents": {c: {"mode": m.mode, "params": m.params, "members": len(m.members)} for c, m in model.models.items()},
                          "test_macro_median_err": float(mac["median_err"]), "test_macro_p95_err": float(mac["p95_err"]),
                          "test_macro_r2_signed_log": float(mac["r2_signed_log"]), "currents_scored": mac["currents_scored"], "n_test": len(te)}
        print(f"{case}: test median={mac['median_err']:.4f} p95={mac['p95_err']:.4f} R2(log)={mac['r2_signed_log']:.5f}", flush=True)
    pd.DataFrame(rows).to_csv(out / "test_results.csv", index=False)
    cr = pd.DataFrame(corner_rows)
    cr[cr.split == "test"].drop(columns="split").to_csv(out / "test_rail_corners.csv", index=False)
    cr[cr.split == "holdout"].drop(columns="split").to_csv(out / "holdout_rail_corners.csv", index=False)
    if (cr.split == "edge_holdout").any():
        cr[cr.split == "edge_holdout"].drop(columns="split").to_csv(out / "edge_holdout_rail_corners.csv", index=False)
    (ROOT / args.models_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str))


if __name__ == "__main__":
    main()
