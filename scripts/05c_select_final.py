"""Phase 3b: choose, per case, the FINAL transistor model between the 10,000-row model and the model refit on the enlarged training set.

Selection uses the VALIDATION set only (never the test set, never the gate/circuit data):
    score = 0.5 * (median error + 95th-percentile error) + 2 * mean |bias|          (macro over the scored currents; lower is better)
The |bias| term is included because gate and circuit leakage are SUMS of currents: a systematic bias of one current adds up, whereas a median
error averages out. (Observed: the enlarged NMOS ON model had a smaller median error but a 2-6 % bias and made the gate level worse.)
The test set is then evaluated once for the chosen models.
This is the ENLARGED-TRAINING-SET extension (assumption A4); models_saved/ (the 10,000-row models of the assignment's specified setting) is not touched.
Outputs: models_selected/<case>.joblib + manifest.json, results/models/final_selection.csv, test_results_selected.csv
"""
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from dvdml import metrics  # noqa: E402
from dvdml.config import load_config  # noqa: E402
from dvdml.sampling import CASES  # noqa: E402

BIAS_WEIGHT = 2.0


def val_score(model, va, min_frac):
    s = metrics.summarize(model.predict(va), va)
    use = s[s.frac_resolved >= min_frac]
    mac = metrics.macro(s, min_frac)
    return {"median_err": mac["median_err"], "p95_err": mac["p95_err"], "mean_abs_bias": float(use.bias_resolved.abs().mean()),
            "score": mac["score"] + BIAS_WEIGHT * float(use.bias_resolved.abs().mean())}


def main():
    cfg = load_config()
    res = ROOT / "results" / "models"
    man10 = json.loads((ROOT / "models_10k" / "manifest.json").read_text())
    manEnl = json.loads((ROOT / "models_enlarged" / "manifest.json").read_text())
    (ROOT / "models_selected").mkdir(exist_ok=True)
    sel_rows, rows, manifest = [], [], {}
    for case in CASES:
        df = pd.read_csv(ROOT / "data" / "transistor" / f"{case}.csv")
        sp = np.load(ROOT / "data" / "splits" / f"{case}.npz")
        va, te = df.iloc[sp["val"]].reset_index(drop=True), df.iloc[sp["test"]].reset_index(drop=True)
        cands = {"10k": joblib.load(ROOT / "models_10k" / f"{case}.joblib"), "enlarged": joblib.load(ROOT / "models_enlarged" / f"{case}.joblib")}
        sc = {k: val_score(m, va, cfg["ml"]["min_resolved_frac"]) for k, m in cands.items()}
        for k, v in sc.items():
            sel_rows.append({"case": case, "candidate": k, **v})
        best = min(sc, key=lambda k: sc[k]["score"])
        model = cands[best]
        pred = model.predict(te)
        s = metrics.summarize(pred, te)
        mac = metrics.macro(s, cfg["ml"]["min_resolved_frac"])
        for cur, r in s.iterrows():
            rows.append({"case": case, "family": "mlp", "training_set": best, "current": cur, **r.to_dict()})
        rows.append({"case": case, "family": "mlp", "training_set": best, "current": "MACRO(" + mac["currents_scored"] + ")", "r2_signed_log": mac["r2_signed_log"],
                     "median_err_resolved": mac["median_err"], "p95_err_resolved": mac["p95_err"]})
        joblib.dump(model, ROOT / "models_selected" / f"{case}.joblib")
        base = man10[case] if best == "10k" else manEnl[case]
        manifest[case] = {**base, "chosen_training_set": best, "val_score_10k": sc["10k"]["score"], "val_score_enlarged": sc["enlarged"]["score"],
                          "test_macro_median_err": float(mac["median_err"]), "test_macro_p95_err": float(mac["p95_err"]),
                          "test_macro_r2_signed_log": float(mac["r2_signed_log"]), "currents_scored": mac["currents_scored"], "n_test": len(te)}
        print(f"{case}: val score 10k={sc['10k']['score']:.4f} enlarged={sc['enlarged']['score']:.4f} -> {best};  test median={mac['median_err']:.4f} p95={mac['p95_err']:.4f}")
    pd.DataFrame(sel_rows).to_csv(res / "final_selection.csv", index=False)
    pd.DataFrame(rows).to_csv(res / "test_results_selected.csv", index=False)
    (ROOT / "models_selected" / "manifest.json").write_text(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
