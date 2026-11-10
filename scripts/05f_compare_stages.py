"""Phase 7: side-by-side comparison of every model stage at transistor, gate and circuit level (reads existing result files only).

Stages (missing ones are skipped):
  baseline        models_saved/ (Phase 3 headline, 10k data)          results/models/test_results.csv, results/gates, results/circuit
  v2 W-norm       per-current MLPs, I/(W/Lmin), +25k extra rows        results/study_v2_wnormW/{models,gates,circuit}
  v2 Weff         + Weff = W - 2 wint normalisation (D-043)            results/study_v2_weff/{models,gates,circuit}
  v2 final        + rail-corner transistor data (D-043)               results/models_v2, results/gates_v2, results/circuit_v2
Outputs: results/stage_comparison.csv (overall), results/stage_comparison_by_gate.csv, results/stage_comparison_transistor.csv
Error = |ML - SPICE| / SPICE per run; mean accuracy = 1 - mean error (as scripts/07 and 09).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "results"
STAGES = [("baseline", R / "models" / "test_results.csv", R / "gates", R / "circuit"),
          ("v2 W-norm", R / "study_v2_wnormW" / "models" / "test_results.csv", R / "study_v2_wnormW" / "gates", R / "study_v2_wnormW" / "circuit"),
          ("v2 Weff", R / "study_v2_weff" / "models" / "test_results.csv", R / "study_v2_weff" / "gates", R / "study_v2_weff" / "circuit"),
          ("v2 final", R / "models_v2" / "test_results.csv", R / "gates_v2", R / "circuit_v2")]
# currents that carry the gate leakage (D-030 composition: ON channel currents are solved by KCL, OFF gate currents are below the noise floor)
LEAK_CURRENTS = [("nmos_on", "ig"), ("pmos_on", "ig"), ("nmos_off", "id"), ("nmos_off", "is"), ("pmos_off", "id"), ("pmos_off", "is"),
                 ("nmos_on", "ib"), ("pmos_on", "ib"), ("nmos_off", "ib"), ("pmos_off", "ib")]


def stats(ml, ref):
    e = np.abs(ml - ref) / ref
    return {"mean_accuracy": 1 - e.mean(), "median_err": np.median(e), "p95_err": np.quantile(e, 0.95), "max_err": e.max(),
            "bias": np.mean((ml - ref) / ref)}


def main():
    overall, by_gate, trans = [], [], []
    for name, tr, gd, cd in STAGES:
        if not (gd / "gate_runs_ml.csv").exists():
            print(f"{name}: no gate results, skipped", file=sys.stderr)
            continue
        g = pd.read_csv(gd / "gate_runs_ml.csv")
        overall.append({"stage": name, "level": "gate (3,600 runs)", **stats(g.leak_ml.to_numpy(), g.leak_spice.to_numpy())})
        for case, x in g.groupby("case", sort=False):
            by_gate.append({"stage": name, "case": case, **stats(x.leak_ml.to_numpy(), x.leak_spice.to_numpy())})
        if (cd / "circuit_runs_ml.csv").exists():
            c = pd.read_csv(cd / "circuit_runs_ml.csv")
            overall.append({"stage": name, "level": "circuit (51,200 runs)", **stats(c.leak_ml.to_numpy(), c.leak_spice.to_numpy())})
        if tr.exists():
            t = pd.read_csv(tr)
            for case, cur in LEAK_CURRENTS:
                row = t[(t.case == case) & (t.current == cur)]
                if len(row):
                    r = row.iloc[0]
                    trans.append({"stage": name, "case": case, "current": cur, "median_err": r.median_err_resolved, "p95_err": r.p95_err_resolved,
                                  "bias": r.bias_resolved, "r2_signed_log": r.r2_signed_log})
    pd.DataFrame(overall).to_csv(R / "stage_comparison.csv", index=False)
    pd.DataFrame(by_gate).to_csv(R / "stage_comparison_by_gate.csv", index=False)
    pd.DataFrame(trans).to_csv(R / "stage_comparison_transistor.csv", index=False)
    print(pd.DataFrame(overall).to_string(index=False, float_format=lambda v: f"{v:.4f}"))


if __name__ == "__main__":
    main()
