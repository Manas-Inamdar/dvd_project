"""Part A, step 2 (deliverable 4): train and compare 4 ML model families per transistor case, tuned on the VALIDATION set.

Families (src/dvdml/ml.py): MLP (PyTorch), LightGBM, RBF kernel ridge, polynomial ridge. Each family predicts the signed log of
all four terminal currents from 15 physics features; every hyper-parameter setting in ml.GRIDS is trained on the 7,000-row train
split and scored on the 1,500-row validation split (data/splits, written by scripts/03_make_splits.py). The test split is not used.

Outputs
  results/model_comparison/comparison_val.csv              4 families x 4 cases (best config each): R2, median/P95 error (macro)
  results/model_comparison/comparison_val_by_current.csv   same, per current
  results/model_comparison/all_trials_val.csv              every hyper-parameter trial
  models_candidates/<case>__<family>.joblib                best fitted model of each family (git-ignored)
The winning family (MLP in all four cases) is the basis of the final per-current models (src/dvdml/ml_v2.py, scripts/05d).
Usage: python scripts/04_compare_models.py [--jobs 7] [--cases nmos_on ...] [--families mlp ...] [--max-rows N]
"""
import argparse
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from joblib import Parallel, delayed

import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from dvdml import metrics  # noqa: E402
from dvdml.config import load_config  # noqa: E402
from dvdml.ml import FAMILIES, GRIDS, TransistorModel  # noqa: E402
from dvdml.sampling import CASES  # noqa: E402


def one_trial(case, family, params, train, val, seed):
    t0 = time.time()
    try:
        m = TransistorModel(case, family, params, seed).fit(train, val)
        summ = metrics.summarize(m.predict(val), val)
        mac = metrics.macro(summ)
        return {"case": case, "family": family, "params": params, "seconds": round(time.time() - t0, 1), "model": m, "summary": summ, "macro": mac}
    except Exception as e:  # keep the study running; the failure is recorded in the trials table
        return {"case": case, "family": family, "params": params, "seconds": round(time.time() - t0, 1), "error": repr(e)[:200]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=7)
    ap.add_argument("--cases", nargs="*", default=list(CASES))
    ap.add_argument("--families", nargs="*", default=list(FAMILIES))
    ap.add_argument("--max-rows", type=int, default=None, help="debug: use only the first N rows")
    args = ap.parse_args()
    cfg = load_config()
    assert abs(cfg["ml"]["i_floor"] - metrics.I_FLOOR) < 1e-30, "config i_floor must equal metrics.I_FLOOR"
    out = ROOT / "results" / "model_comparison"; out.mkdir(parents=True, exist_ok=True)
    (ROOT / "models_candidates").mkdir(exist_ok=True)

    data, tasks = {}, []
    for case in args.cases:
        df = pd.read_csv(ROOT / "data" / "transistor" / f"{case}.csv")
        sp = np.load(ROOT / "data" / "splits" / f"{case}.npz")     # scripts/03_make_splits.py
        tr, va = sp["train"], sp["val"]
        if args.max_rows:                                           # debug: smaller train/val subsets
            tr, va = tr[: args.max_rows], va[: max(args.max_rows // 4, 1)]
        data[case] = (df.iloc[tr].reset_index(drop=True), df.iloc[va].reset_index(drop=True))
        for fam in args.families:
            for params in GRIDS[fam]:
                tasks.append((case, fam, params))
    print(f"{len(tasks)} trials on {len(args.cases)} cases ...", flush=True)
    t0 = time.time()
    results = Parallel(n_jobs=args.jobs, verbose=5)(
        delayed(one_trial)(c, f, p, data[c][0], data[c][1], cfg["ml"]["split_seed"]) for c, f, p in tasks)
    print(f"done in {(time.time() - t0) / 60:.1f} min", flush=True)

    trials, best = [], {}
    for r in results:
        row = {"case": r["case"], "family": r["family"], "params": str(r["params"]), "seconds": r["seconds"]}
        if "error" in r:
            row["error"] = r["error"]
        else:
            row.update({f"val_{k}": v for k, v in r["macro"].items()})
            key = (r["case"], r["family"])
            if key not in best or r["macro"]["score"] < best[key]["macro"]["score"]:
                best[key] = r
        trials.append(row)
    pd.DataFrame(trials).to_csv(out / "all_trials_val.csv", index=False)

    table, by_cur = [], []
    for (case, fam), r in sorted(best.items()):
        mac = r["macro"]
        table.append({"case": case, "family": fam, "best_params": str(r["params"]), "val_r2_signed_log": mac["r2_signed_log"],
                      "val_median_err": mac["median_err"], "val_p95_err": mac["p95_err"], "val_score": mac["score"],
                      "currents_scored": mac["currents_scored"], "fit_seconds": r["seconds"]})
        s = r["summary"].reset_index(); s.insert(0, "family", fam); s.insert(0, "case", case); by_cur.append(s)
        joblib.dump(r["model"], ROOT / "models_candidates" / f"{case}__{fam}.joblib")
    pd.DataFrame(table).to_csv(out / "comparison_val.csv", index=False)
    pd.concat(by_cur).to_csv(out / "comparison_val_by_current.csv", index=False)
    pd.set_option("display.width", 220)
    print(pd.DataFrame(table).drop(columns=["best_params"]).to_string(index=False, float_format=lambda x: f"{x:.4g}"))
    errs = [t for t in trials if "error" in t]
    if errs:
        print("FAILED TRIALS:", errs[:5])


if __name__ == "__main__":
    main()
