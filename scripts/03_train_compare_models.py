"""Phase 3.1-3.3: split data, tune 4 model families per case on the VALIDATION set, write the comparison table.

Outputs
  data/splits/<case>.npz                         fixed-seed train/val/test row indices (70/15/15)
  results/models/comparison_val.csv              4 families x 4 cases (best config each): R2, median/P95 error (macro over scored currents)
  results/models/comparison_val_by_current.csv   same, per current
  results/models/all_trials_val.csv              every hyper-parameter trial
  models_candidates/<case>__<family>.joblib      best fitted model of each family (git-ignored, used by script 04)
Usage: python scripts/03_train_compare_models.py [--jobs 7] [--cases nmos_on ...] [--families mlp ...] [--max-rows N]
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


def make_split(n: int, cfg: dict, case: str):
    rng = np.random.default_rng([cfg["ml"]["split_seed"], CASES.index(case)])
    idx = rng.permutation(n)
    f = cfg["ml"]["split_fractions"]
    a, b = int(round(f[0] * n)), int(round((f[0] + f[1]) * n))
    return idx[:a], idx[a:b], idx[b:]


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
    out = ROOT / "results" / "models"; out.mkdir(parents=True, exist_ok=True)
    (ROOT / "data" / "splits").mkdir(parents=True, exist_ok=True)
    (ROOT / "models_candidates").mkdir(exist_ok=True)

    data, tasks = {}, []
    for case in args.cases:
        df = pd.read_csv(ROOT / "data" / "transistor" / f"{case}.csv")
        if args.max_rows:
            df = df.iloc[: args.max_rows]
        tr, va, te = make_split(len(df), cfg, case)
        np.savez(ROOT / "data" / "splits" / f"{case}.npz", train=tr, val=va, test=te)
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
