"""Phase 3b (A4 / D-037): refit the CHOSEN model type of each case on the enlarged training set and evaluate.

Training set = original 70 % train split (7,000 rows) + all extra rows of data/transistor_extra/. Validation and test sets are the ORIGINAL ones, so the
numbers are directly comparable with the 10,000-row models (kept in models_10k/ and results/models/test_results_10k.csv). Model comparison (4 families) stays on
the specified 10,000-row dataset (scripts/03); only the winning type is refit on more data.
Outputs: models_enlarged/<case>.joblib (+ manifest.json), results/models/test_results_enlarged.csv, results/models/enlarged_vs_10k.csv.
         models_saved/ is NOT touched; scripts/05c_select_final.py chooses per case between the 10k model (models_10k/) and the enlarged model.
Usage: python scripts/05b_retrain_enlarged.py [--epochs 500] [--batch 512] [--jobs 4]
"""
import argparse
import ast
import json
import shutil
import sys
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from joblib import Parallel, delayed

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from dvdml import metrics  # noqa: E402
from dvdml.config import load_config  # noqa: E402
from dvdml.ml import TransistorModel  # noqa: E402
from dvdml.sampling import CASES  # noqa: E402


def fit_case(case, params, seed):
    df = pd.read_csv(ROOT / "data" / "transistor" / f"{case}.csv")
    sp = np.load(ROOT / "data" / "splits" / f"{case}.npz")
    extra = pd.read_csv(ROOT / "data" / "transistor_extra" / f"{case}.csv.gz")
    train = pd.concat([df.iloc[sp["train"]], extra], ignore_index=True)
    val, test = df.iloc[sp["val"]].reset_index(drop=True), df.iloc[sp["test"]].reset_index(drop=True)
    t0 = time.time()
    m = TransistorModel(case, "mlp", params, seed).fit(train, val)
    return case, m, len(train), time.time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=500)
    ap.add_argument("--batch", type=int, default=512)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--threads", type=int, default=3)
    args = ap.parse_args()
    cfg = load_config()
    res = ROOT / "results" / "models"
    if not (ROOT / "models_10k").exists():                       # keep the 10k-only models and their test results for comparison
        shutil.copytree(ROOT / "models_saved", ROOT / "models_10k")
        shutil.copy(res / "test_results.csv", res / "test_results_10k.csv")
    man = json.loads((ROOT / "models_10k" / "manifest.json").read_text())   # hyper-parameters of the 10k winners
    (ROOT / "models_enlarged").mkdir(exist_ok=True)
    jobs = []
    for case in CASES:
        base = ast.literal_eval(man[case]["params"]) if isinstance(man[case]["params"], str) else man[case]["params"]
        jobs.append((case, {**base, "epochs": args.epochs, "batch": args.batch, "threads": args.threads, "polish_rounds": 6, "polish_iter": 300}))
    out = Parallel(n_jobs=args.jobs)(delayed(fit_case)(c, p, cfg["ml"]["split_seed"]) for c, p in jobs)

    rows, new_man, cmp_rows = [], {}, []
    old = pd.read_csv(res / "test_results_10k.csv")
    for case, model, n_train, secs in out:
        df = pd.read_csv(ROOT / "data" / "transistor" / f"{case}.csv")
        te = df.iloc[np.load(ROOT / "data" / "splits" / f"{case}.npz")["test"]].reset_index(drop=True)
        pred = model.predict(te)
        s = metrics.summarize(pred, te)
        mac = metrics.macro(s, cfg["ml"]["min_resolved_frac"])
        for cur, r in s.iterrows():
            rows.append({"case": case, "family": "mlp", "current": cur, **r.to_dict()})
        rows.append({"case": case, "family": "mlp", "current": "MACRO(" + mac["currents_scored"] + ")", "r2_signed_log": mac["r2_signed_log"],
                     "median_err_resolved": mac["median_err"], "p95_err_resolved": mac["p95_err"]})
        joblib.dump(model, ROOT / "models_enlarged" / f"{case}.joblib")
        o = old[(old.case == case) & old.current.str.startswith("MACRO")].iloc[0]
        new_man[case] = {**man[case], "trained_on_rows": n_train, "test_macro_median_err": float(mac["median_err"]), "test_macro_p95_err": float(mac["p95_err"]),
                         "test_macro_r2_signed_log": float(mac["r2_signed_log"]), "params": str({**model.params}), "fit_seconds": round(secs, 1)}
        cmp_rows.append({"case": case, "train_rows_10k": 7000, "train_rows_enlarged": n_train, "median_err_10k": o.median_err_resolved, "median_err_enlarged": mac["median_err"],
                         "p95_err_10k": o.p95_err_resolved, "p95_err_enlarged": mac["p95_err"]})
        print(f"{case}: train rows {n_train}  test median {o.median_err_resolved:.4f} -> {mac['median_err']:.4f}   p95 {o.p95_err_resolved:.4f} -> {mac['p95_err']:.4f}  ({secs / 60:.1f} min)", flush=True)
    pd.DataFrame(rows).to_csv(res / "test_results_enlarged.csv", index=False)
    pd.DataFrame(cmp_rows).to_csv(res / "enlarged_vs_10k.csv", index=False)
    (ROOT / "models_enlarged" / "manifest.json").write_text(json.dumps(new_man, indent=2))


if __name__ == "__main__":
    main()
