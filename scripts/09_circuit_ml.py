"""Phase 5.3-5.4: hierarchical ML prediction of the parity checker's leakage vs the SPICE reference.

For every (input vector, corner): the logic value at the inputs of each of the 28 NAND2 gates is determined by logic propagation; the gate
model of Part B for that input combination (NAND2_00/01/10/11) and that corner gives the gate leakage (SPICE-recorded node voltages of the isolated gate at the SAME
corner feed the transistor models, exactly as in Part B); the 28 gate leakages are summed.
This ignores loading between gates and assumes every gate input sits at exactly 0 or VDD.
Uses the gate-level predictions of scripts/07_gate_ml.py (results/gates/gate_runs_ml.csv), so run that script first (and again after retraining the models).

Outputs
  results/circuit/circuit_runs_ml.csv       per run: SPICE and ML leakage
  results/circuit/circuit_results.csv       metrics (overall + per number-of-ones in the input vector), same metrics as the gate table
  results/circuit/circuit_parity.png        ML vs SPICE leakage, log-log
  results/circuit/circuit_error_vs_corner.png
"""
import sys
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from dvdml import circuit  # noqa: E402

VECTORS = [tuple(int(c) for c in format(v, "08b")) for v in range(256)]   # same order as itertools.product((0, 1), repeat=8)


def summarize(df, ml="leak_ml", ref="leak_spice"):
    e = (df[ml] - df[ref]).abs() / df[ref]
    s = (df[ml] - df[ref]) / df[ref]
    return {"n": len(df), "spice_median_A": df[ref].median(), "ml_median_A": df[ml].median(), "bias": s.mean(), "median_err": e.median(),
            "p95_err": e.quantile(0.95), "mean_err": e.mean(), "mean_accuracy": 1 - e.mean(), "max_err": e.max()}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate-runs", default="results/gates/gate_runs_ml.csv", help="gate-level ML predictions to compose the circuit from")
    ap.add_argument("--out-dir", default="results/circuit")
    args = ap.parse_args()
    out = ROOT / args.out_dir; out.mkdir(parents=True, exist_ok=True)
    spice = pd.read_csv(ROOT / "data" / "circuit" / "circuit_spice.csv", dtype={"bits": str})
    gates = pd.read_csv(ROOT / args.gate_runs, dtype={"inputs": str})
    lut = gates[gates.gate == "NAND2"].set_index(["case", "corner"])["leak_ml"]      # Part-B gate model output per (case, corner)
    lut_sp = gates[gates.gate == "NAND2"].set_index(["case", "corner"])["leak_spice"]
    # number of gate instances in each NAND2 case for every vector
    counts = {}
    for vid, bits in enumerate(VECTORS):
        cs = pd.Series([c for _, c in circuit.instance_cases(bits)]).value_counts()
        counts[vid] = cs.to_dict()
    cnt = pd.DataFrame(counts).T.fillna(0).astype(int)                                # rows: vector, columns: NAND2 cases
    ml_leak = np.zeros(len(spice)); sum_gate_spice = np.zeros(len(spice))
    for case in cnt.columns:
        n = spice["vector"].map(cnt[case]).to_numpy()
        per = np.array([lut[(case, c)] for c in spice["corner"]])
        per_sp = np.array([lut_sp[(case, c)] for c in spice["corner"]])
        ml_leak += n * per
        sum_gate_spice += n * per_sp
    spice["leak_ml"] = ml_leak
    spice["leak_sum_of_isolated_gate_spice"] = sum_gate_spice              # diagnostic: SPICE of isolated gates summed (isolates the loading effect)
    spice["n_ones"] = spice["bits"].str.count("1")
    spice.to_csv(out / "circuit_runs_ml.csv", index=False)

    rows = [{"group": "all 51,200 runs", **summarize(spice)}]
    rows += [{"group": f"{k} ones in input", **summarize(g)} for k, g in spice.groupby("n_ones")]
    res = pd.DataFrame(rows)
    res.to_csv(out / "circuit_results.csv", index=False)
    diag = {"ML(circuit) vs SPICE(circuit)": summarize(spice), "sum of isolated-gate SPICE vs SPICE(circuit) [loading effect only]": summarize(spice, "leak_sum_of_isolated_gate_spice")}
    pd.DataFrame([{"comparison": k, **v} for k, v in diag.items()]).to_csv(out / "circuit_decomposition.csv", index=False)
    pd.set_option("display.width", 250)
    print(res[["group", "spice_median_A", "ml_median_A", "bias", "median_err", "p95_err", "mean_accuracy"]].to_string(index=False, float_format=lambda x: f"{x:.4g}"))
    for k, v in diag.items():
        print(f"{k}: bias={v['bias']:+.4f} median_err={v['median_err']:.4f} p95={v['p95_err']:.4f} mean_acc={v['mean_accuracy']:.4f}")

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.loglog(spice.leak_spice, spice.leak_ml, ".", ms=1.5, alpha=.25)
    lo, hi = spice.leak_spice.min() * .8, spice.leak_spice.max() * 1.25
    ax.loglog([lo, hi], [lo, hi], "k-", lw=.7)
    ax.set_xlabel("SPICE leakage (A)"); ax.set_ylabel("ML leakage (A)"); ax.grid(True, which="both", alpha=.3)
    ax.set_title("8-bit parity checker: ML vs SPICE (256 vectors x 200 corners)")
    fig.tight_layout(); fig.savefig(out / "circuit_parity.png", dpi=120); plt.close(fig)

    spice["err"] = (spice.leak_ml - spice.leak_spice).abs() / spice.leak_spice
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    for ax, (x, lab) in zip(axes, [(spice.temp, "temperature (degC)"), (spice.vdd, "VDD (V)"), (spice.n_ones, "number of ones in the input vector")]):
        ax.semilogy(x, spice.err.clip(lower=1e-5), ".", ms=1.5, alpha=.2); ax.set_xlabel(lab); ax.set_ylabel("relative error"); ax.grid(True, which="both", alpha=.3)
    fig.tight_layout(); fig.savefig(out / "circuit_error_vs_corner.png", dpi=110); plt.close(fig)


if __name__ == "__main__":
    main()
