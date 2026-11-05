"""Phase 3.5: learning curves - validation accuracy of the CHOSEN model per case vs. training-set size.

The assignment asks for "the smallest dataset possible without compromising accuracy"; this shows where accuracy saturates.
Outputs: results/models/learning_curve.csv, results/models/learning_curve.png
(validation set only; the test set is never touched here)
"""
import ast
import json
import sys
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
from joblib import Parallel, delayed

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from dvdml import metrics  # noqa: E402
from dvdml.config import load_config  # noqa: E402
from dvdml.ml import TransistorModel  # noqa: E402
from dvdml.sampling import CASES  # noqa: E402

SIZES = [500, 1000, 2000, 4000, None]  # None = full training set (7,000)


def run(case, family, params, n, tr, va, seed):
    sub = tr if n is None else tr.iloc[:n]
    m = TransistorModel(case, family, params, seed).fit(sub, va)
    mac = metrics.macro(metrics.summarize(m.predict(va), va))
    return {"case": case, "family": family, "n_train": len(sub), "val_median_err": mac["median_err"], "val_p95_err": mac["p95_err"], "val_r2_signed_log": mac["r2_signed_log"]}


def main():
    cfg = load_config()
    man = json.loads((ROOT / "models_saved" / "manifest.json").read_text())
    tasks = []
    for case in CASES:
        df = pd.read_csv(ROOT / "data" / "transistor" / f"{case}.csv")
        sp = np.load(ROOT / "data" / "splits" / f"{case}.npz")
        tr, va = df.iloc[sp["train"]].reset_index(drop=True), df.iloc[sp["val"]].reset_index(drop=True)
        params = ast.literal_eval(man[case]["params"])
        for n in SIZES:
            tasks.append((case, man[case]["family"], params, n, tr, va, cfg["ml"]["split_seed"]))
    rows = Parallel(n_jobs=7, verbose=3)(delayed(run)(*t) for t in tasks)
    lc = pd.DataFrame(rows)
    lc.to_csv(ROOT / "results" / "models" / "learning_curve.csv", index=False)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for case, g in lc.groupby("case"):
        axes[0].loglog(g.n_train, g.val_median_err, "o-", label=f"{case} ({g.family.iloc[0]})")
        axes[1].loglog(g.n_train, g.val_p95_err, "o-", label=case)
    axes[0].set_title("validation median error vs training size"); axes[1].set_title("validation 95th-percentile error vs training size")
    for a in axes:
        a.set_xlabel("training samples"); a.set_ylabel("relative error (resolved currents)"); a.grid(True, which="both", alpha=.3)
    axes[0].legend(fontsize=7); fig.tight_layout(); fig.savefig(ROOT / "results" / "models" / "learning_curve.png", dpi=110)
    print(lc.to_string(index=False, float_format=lambda x: f"{x:.4g}"))


if __name__ == "__main__":
    main()
