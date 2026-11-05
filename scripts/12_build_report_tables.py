"""Generate report/tables/*.tex from the result CSVs (never type report numbers by hand). Missing inputs give a 'pending' stub.

Also writes the deliverables checklist (appendix A) by checking which output files exist.
"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from dvdml.latex import esc, tabular  # noqa: E402

OUT = ROOT / "report" / "tables"
OUT.mkdir(parents=True, exist_ok=True)


def write(name, text):
    (OUT / f"{name}.tex").write_text(text, encoding="utf-8")


def pending(name, what):
    write(name, f"\\textcolor{{red}}{{[pending: {esc(what)}]}}\n")


def kirchhoff():
    f = ROOT / "results" / "data_check" / "kirchhoff.csv"
    if not f.exists():
        return pending("kirchhoff", "run scripts/02_data_check.py")
    k = pd.read_csv(f)
    t = k[["case", "abs_residual_median_A", "abs_residual_p95_A", "abs_residual_max_A", "rel_residual_median", "rel_residual_p95", "frac_max|I|<=1e-16A"]].copy()
    t.columns = ["case", "abs median [A]", "abs p95 [A]", "abs max [A]", "rel median", "rel p95", "frac. max|I|<1e-16 A"]
    kinds = {c: "sci" for c in t.columns[1:6]}
    kinds["frac. max|I|<1e-16 A"] = "pct"
    write("kirchhoff", tabular(t, kinds, "Kirchhoff check, residual $|I_d+I_g+I_s+I_b|$ per case (absolute and relative to the largest terminal current).", "tab:kirchhoff"))


def models():
    f = ROOT / "results" / "models" / "comparison_val.csv"
    if not f.exists():
        pending("model_comparison", "run scripts/03_train_compare_models.py")
    else:
        c = pd.read_csv(f)
        t = c[["case", "family", "val_r2_signed_log", "val_median_err", "val_p95_err", "best_params"]].copy()
        t["best_params"] = t["best_params"].str.replace("'", "").str.replace("{", "").str.replace("}", "")
        t.columns = ["case", "model", "R2 (signed-log)", "median err", "95th pct err", "best hyper-parameters"]
        write("model_comparison", tabular(t, {"R2 (signed-log)": "g", "median err": "pct", "95th pct err": "pct"},
                                          "Model comparison on the \\emph{validation} set (4 model types $\\times$ 4 cases). Errors are relative errors "
                                          "on currents above the noise floor, averaged over the scored currents.", "tab:comparison", colspec="llrrrl", small=True))
    f = ROOT / "results" / "models" / "test_results.csv"
    m = ROOT / "models_saved" / "manifest.json"
    if not f.exists() or not m.exists():
        return pending("chosen_models", "run scripts/04_select_and_evaluate.py")
    r = pd.read_csv(f)
    man = json.loads(m.read_text())
    t = r[~r.current.str.startswith("MACRO")][["case", "family", "current", "frac_resolved", "r2_signed_log", "median_err_resolved", "p95_err_resolved", "bias_resolved"]].copy()
    t.columns = ["case", "model", "current", "frac. resolved", "R2 (signed-log)", "median err", "95th pct err", "bias"]
    write("chosen_models", tabular(t, {"frac. resolved": "pct", "R2 (signed-log)": "g", "median err": "pct", "95th pct err": "pct", "bias": "pct"},
                                   "Chosen models on the \\emph{test} set, per terminal current (errors on samples with $|I|>10^{-15}$\\,A).", "tab:chosen", colspec="lllrrrrr"))
    mac = pd.DataFrame([{"case": k, "model": v["family"], "currents scored": v["currents_scored"], "median err": v["test_macro_median_err"],
                         "95th pct err": v["test_macro_p95_err"], "R2 (signed-log)": v["test_macro_r2_signed_log"]} for k, v in man.items()])
    write("chosen_macro", tabular(mac, {"median err": "pct", "95th pct err": "pct", "R2 (signed-log)": "g"},
                                  "Chosen models, test-set summary (macro-average over the scored currents).", "tab:chosen_macro", colspec="lllrrr"))
    lc = ROOT / "results" / "models" / "learning_curve.csv"
    if lc.exists():
        d = pd.read_csv(lc)[["case", "n_train", "val_median_err", "val_p95_err"]]
        d.columns = ["case", "train samples", "val median err", "val 95th pct err"]
        write("learning_curve", tabular(d, {"train samples": "int", "val median err": "pct", "val 95th pct err": "pct"},
                                        "Validation error of the chosen model versus training-set size.", "tab:lc", colspec="lrrr"))
    else:
        pending("learning_curve", "run scripts/05_learning_curves.py")


def gate_tables():
    f = ROOT / "results" / "gates" / "gate_results.csv"
    if not f.exists():
        for n in ("gate_results", "gate_estimators", "gate_by_gate", "gate_reference"):
            pending(n, "run scripts/06_gate_spice.py and 07_gate_ml.py")
        return
    g = pd.read_csv(f)
    t = g[["case", "spice_median_A", "ml_median_A", "bias", "median_err", "p95_err"]].copy()
    t.columns = ["case", "SPICE median [A]", "ML median [A]", "bias", "median err", "95th pct err"]
    write("gate_results", tabular(t, {"SPICE median [A]": "sci", "ML median [A]": "sci", "bias": "pct", "median err": "pct", "95th pct err": "pct"},
                                  "Gate-level results for the 18 gate/input cases (200 corners each). Error is $|I_{ML}-I_{SPICE}|/I_{SPICE}$; bias is the mean signed relative error.",
                                  "tab:gates", colspec="lrrrrr"))
    e = pd.read_csv(ROOT / "results" / "gates" / "gate_estimators.csv")[["estimator", "bias", "median_err", "p95_err", "mean_err"]]
    names = {"leak_ml_naive_supply": "plain sum of terminal currents at the VDD-level nodes", "leak_ml_naive_ground": "plain sum of terminal currents at the 0 V-level nodes",
             "leak_ml_supply_side": "KCL-consistent, supply side", "leak_ml_ground_side": "KCL-consistent, ground side", "leak_ml": "KCL-consistent, mean of both (reported)"}
    e["estimator"] = e["estimator"].map(names)
    e.columns = ["estimator", "bias", "median err", "95th pct err", "mean err"]
    write("gate_estimators", tabular(e, {"bias": "g", "median err": "g", "95th pct err": "g", "mean err": "g"},
                                     "Gate-level error of the alternative ways of turning predicted transistor currents into gate leakage (all 3600 runs; fractions, not percent).",
                                     "tab:estimators", colspec="lrrrr"))
    b = pd.read_csv(ROOT / "results" / "gates" / "gate_by_gate.csv")[["gate", "n", "bias", "median_err", "p95_err", "mean_accuracy"]]
    b.columns = ["gate", "runs", "bias", "median err", "95th pct err", "mean accuracy"]
    write("gate_by_gate", tabular(b, {"runs": "int", "bias": "pct", "median err": "pct", "95th pct err": "pct", "mean accuracy": "pct"},
                                  "Gate-level accuracy per gate type.", "tab:bygate", colspec="lrrrrr"))
    s = pd.read_csv(ROOT / "data" / "gates" / "gate_spice.csv", dtype={"inputs": str})
    ref = s["ref_source"].value_counts().rename_axis("reference source").reset_index(name="runs")
    ref["meaning"] = ref["reference source"].map({"mandated": "mandated-option solve (agrees with tight cross-check within 1%)",
                                                  "tight": "mandated solve disagreed with the cross-check -> tight solve used",
                                                  "tight_only": "mandated solve did not converge -> tight solve used"})
    write("gate_reference", tabular(ref, {"runs": "int"}, "Origin of the 3600 gate SPICE reference values.", "tab:ref", colspec="lrl"))


def deliverables():
    R = ROOT
    items = [
        ("1", "Datasets: 4 CSV files, 10,000 rows each", [R / "data/transistor/nmos_on.csv", R / "data/transistor/pmos_off.csv"]),
        ("2", "Example netlists: transistor", [R / "netlists/single_transistor/nmos_on.cir"]),
        ("2", "Example netlists: gates", [R / "netlists/gates"]),
        ("2", "Example netlists: test circuit", [R / "netlists/circuit"]),
        ("3", "Data check: Kirchhoff + 3 trend plots", [R / "results/data_check/kirchhoff.csv", R / "results/data_check/trend_ig_vs_toxe.png"]),
        ("4", "Model comparison table (4 types x 4 cases, validation)", [R / "results/models/comparison_val.csv"]),
        ("5", "Chosen models: test errors, pred-vs-SPICE plots, 4 saved models", [R / "models_saved/manifest.json", R / "results/models/pred_vs_spice_nmos_on.png"]),
        ("6", "Gate results table (18 cases)", [R / "results/gates/gate_results.csv"]),
        ("7", "Gate parity plot", [R / "results/gates/gate_parity.png"]),
        ("8", "Test-circuit results + parity plot", [R / "results/circuit/circuit_results.csv", R / "results/circuit/circuit_parity.png"]),
        ("9", "Code regenerating everything (scripts in order)", [R / "scripts/01_generate_transistor_data.py"]),
        ("10", "Typed report (this document)", [R / "report/report.tex"]),
    ]
    rows = [{"#": n, "deliverable": d, "status": "present" if all(p.exists() for p in paths) else "pending"} for n, d, paths in items]
    write("deliverables", tabular(pd.DataFrame(rows), caption="Deliverables (status generated automatically from the files present in the repository).", label="tab:deliv", colspec="llr"))


if __name__ == "__main__":
    kirchhoff(); models(); gate_tables(); deliverables()
    print("tables written to", OUT)
