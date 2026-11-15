"""Report: generate report/tables/*.tex from the result files, so that no number in the report is typed by hand.

Inputs: results/ (scripts 02, 04, 05e, 07, 09, 10), data/gates/gate_spice.csv, models/manifest.json.
Output: report/tables/<name>.tex (one LaTeX table each, included by report/sections/*.tex).
Usage: python scripts/11_build_report_tables.py
"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from dvdml.latex import tabular  # noqa: E402

RES = ROOT / "results"
OUT = ROOT / "report" / "tables"
CASE = {"nmos_on": "NMOS ON", "nmos_off": "NMOS OFF", "pmos_on": "PMOS ON", "pmos_off": "PMOS OFF"}
FAMILY = {"mlp": "MLP", "lightgbm": "LightGBM", "kernel_ridge": "Kernel ridge", "poly_ridge": "Polynomial ridge"}
P = "pct"


def write(name, text):
    (OUT / f"{name}.tex").write_text(text, encoding="utf-8")


def pct_cols(cols):
    return {c: P for c in cols}


def data_check():
    k = pd.read_csv(RES / "data_check" / "kirchhoff.csv")
    t = k[["case", "abs_residual_median_A", "abs_residual_p95_A", "abs_residual_max_A", "rel_residual_median_above_floor",
           "rel_residual_p95_above_floor"]].copy()
    t["case"] = t["case"].map(CASE)
    t.columns = ["case", "abs. median [A]", "abs. P95 [A]", "abs. max [A]", "rel. median", "rel. P95"]
    write("kirchhoff", tabular(t, {c: "sci" for c in t.columns[1:]},
                               r"Kirchhoff check on the four 10{,}000-row datasets: residual $|I_d+I_g+I_s+I_b|$ per sample, absolute and relative "
                               r"to the largest terminal current of the sample (relative values for samples whose largest current exceeds $10^{-16}$\,A).",
                               "tab:kirchhoff"))
    tr = json.loads((RES / "data_check" / "trend_checks.json").read_text())
    checks = {k: v for k, v in tr.items() if isinstance(v, bool)}
    rows = []
    for (name, ok), (rname, ratio) in zip(checks.items(), ((k, v) for k, v in tr.items() if not isinstance(v, bool))):
        case, trend = name.split(": ", 1)
        rows.append({"case": CASE[case], "expected trend": trend.replace("|", "").replace("Id", "OFF $I_d$").replace("Ig", "ON $I_g$"),
                     "ratio": ratio, "sweep end points": rname.split(": ", 1)[1].replace("|Id|", "").replace("|Ig|", "").replace("ratio", "").strip(" ()"), "check": "pass" if ok else "FAIL"})
    t = pd.DataFrame(rows)
    write("trend_checks", tabular(t, {"ratio": "g"}, "Automatic checks of the three trend sweeps: expected direction and ratio of the currents "
                                  "at the two ends of each sweep (all other inputs fixed at nominal).", "tab:trends", colspec="llrll")
          .replace(r"\$I\_d\$", "$I_d$").replace(r"\$I\_g\$", "$I_g$"))


def model_comparison():
    c = pd.read_csv(RES / "model_comparison" / "comparison_val.csv")
    c["case"] = pd.Categorical(c["case"].map(CASE), list(CASE.values()))
    c["family_name"] = c["family"].map(FAMILY)
    c = c.sort_values(["case", "val_score"])
    c["best_params"] = (c["best_params"].str.replace("'", "").str.replace("{", "").str.replace("}", "").str.replace("hidden: ", "")
                        .str.replace(", epochs: 1200", "").str.replace("num_leaves", "leaves")
                        .str.replace(r"^\((\d+), \d+, \d+\), activation: tanh.*$", r"3 hidden layers x \1 tanh units", regex=True))
    t = c[["case", "family_name", "val_r2_signed_log", "val_median_err", "val_p95_err", "val_score", "best_params"]].copy()
    t["case"] = t["case"].astype(str)
    t.columns = ["case", "model type", "R2", "median err", "P95 err", "score", "best hyper-parameters"]
    write("model_comparison", tabular(t, {"R2": "g", "median err": P, "P95 err": P, "score": "g"},
                                      r"Model comparison on the \emph{validation} set: 4 model types $\times$ 4 cases (best hyper-parameters of each type). "
                                      r"$R^2$ on the signed-log target; relative errors on resolved currents ($|I|>10^{-15}$\,A), averaged over the scored currents; "
                                      r"score $=\frac12$(median + P95), lower is better. Sorted by score within each case.",
                                      "tab:comparison", colspec="llrrrrl"))


def final_models():
    man = json.loads((ROOT / "models" / "manifest.json").read_text())
    rows = []
    for case, v in man.items():
        for cur, s in v["currents"].items():
            p = s["params"]
            w = p.get("wnorm")
            rows.append({"case": CASE[case], "current": cur, "target": "log10|I|" if s["mode"] == "log" else "asinh (signed log)",
                         "members": s["members"], "rail-corner data": "yes" if p.get("edge_data") else "no",
                         "width normalisation": "Weff" if w == "weff" else "W"})
    t = pd.DataFrame(rows)
    write("final_settings", tabular(t, {"members": "int"}, "Settings of the 16 per-current networks of the final models (all: 21 inputs, 4 hidden layers of 128 tanh units, "
                                    "Adam 1500 epochs + L-BFGS polish).", "tab:settings", colspec="lllrll"))
    r = pd.read_csv(RES / "models" / "test_results.csv")
    mac = r[r["current"].str.startswith("MACRO")].copy()
    mac["case"] = mac["case"].map(CASE)
    mac["scored"] = mac["current"].str.extract(r"\((.*)\)")[0]
    t = mac[["case", "scored", "r2_signed_log", "median_err_resolved", "p95_err_resolved"]]
    t.columns = ["case", "currents scored", "R2", "median err", "P95 err"]
    write("chosen_macro", tabular(t, {"R2": "g", "median err": P, "P95 err": P},
                                  r"Final models on the \emph{test} set (1{,}500 rows per case, evaluated once): macro-average over the scored currents.",
                                  "tab:chosen_macro", colspec="llrrr"))
    pc = r[~r["current"].str.startswith("MACRO")].copy()
    pc["case"] = pc["case"].map(CASE)
    pc.loc[pc["frac_resolved"] < 0.05, "r2_signed_log"] = float("nan")     # noise-only current (OFF ig): not scored
    t = pc[["case", "current", "frac_resolved", "r2_signed_log", "median_err_resolved", "p95_err_resolved", "bias_resolved"]]
    t.columns = ["case", "current", "resolved", "R2", "median err", "P95 err", "bias"]
    write("chosen_models", tabular(t, {"resolved": P, "R2": "g", "median err": P, "P95 err": P, "bias": P},
                                   r"Final models on the test set, per terminal current (errors on resolved samples, $|I|>10^{-15}$\,A; "
                                   r"OFF-state $I_g$ is below the floor in every row and is not scored).", "tab:chosen", colspec="llrrrrr"))
    e = pd.read_csv(RES / "models" / "edge_holdout_rail_corners.csv")
    keep = [("nmos_on", "ig"), ("pmos_on", "ig"), ("nmos_off", "id"), ("nmos_off", "is"), ("pmos_off", "id"), ("pmos_off", "is"),
            ("nmos_on", "ib"), ("pmos_on", "ib")]
    e = e[e["region"] == "vd,vs exactly at rails"].set_index(["case", "current"]).loc[keep].reset_index()
    e["case"] = e["case"].map(CASE)
    t = e[["case", "current", "n", "median", "p95", "bias"]]
    t.columns = ["case", "current", "rows", "median err", "P95 err", "bias"]
    write("rail_corners", tabular(t, {"rows": "int", "median err": P, "P95 err": P, "bias": P},
                                  r"Error of the final models at the gate operating points: held-out rail-corner rows with $V_d$ and $V_s$ both exactly at "
                                  r"$0$ or $V_{DD}$ (never used for training or selection), for the currents that enter the gate leakage.", "tab:rails",
                                  colspec="llrrrr"))


def model_development():
    s = pd.read_csv(RES / "model_development" / "stage_comparison.csv")
    names = {"baseline": "one 4-output MLP per case, 7k rows", "v2 W-norm": "one MLP per current, I/(W/Lmin) target",
             "v2 Weff": "+ effective-width target I/(W_eff/Lmin)", "v2 final": "+ rail-corner training rows (final)"}
    s["stage"] = s["stage"].map(names)
    t = s[["stage", "level", "mean_accuracy", "median_err", "p95_err", "max_err"]]
    t.columns = ["model stage", "level", "mean accuracy", "median err", "P95 err", "max err"]
    write("stages", tabular(t, pct_cols(t.columns[2:]), "Gate- and circuit-level accuracy of the successive model stages (same SPICE references, "
                            "same composition code).", "tab:stages", colspec="llrrrr"))


def gates():
    g = pd.read_csv(RES / "gates" / "gate_results.csv")
    t = g[["case", "spice_median_A", "ml_median_A", "bias", "median_err", "p95_err", "mean_accuracy"]].copy()
    t["case"] = t["case"].str.replace("_", " ")
    t.columns = ["gate / input", "SPICE median [A]", "ML median [A]", "bias", "median err", "P95 err", "mean acc."]
    write("gate_results", tabular(t, {"SPICE median [A]": "sci", "ML median [A]": "sci", **pct_cols(t.columns[3:])},
                                  r"Gate-level results for the 18 gate/input cases, 200 PVT corners each. Error $=(I_{ML}-I_{SPICE})/I_{SPICE}$; "
                                  r"bias is its mean, median/P95 are of its absolute value, mean accuracy $=1-$ mean absolute error.", "tab:gates",
                                  colspec="lrrrrrr"))
    b = pd.read_csv(RES / "gates" / "gate_by_gate.csv")[["gate", "n", "bias", "median_err", "p95_err", "max_err", "mean_accuracy"]]
    b.columns = ["gate", "runs", "bias", "median err", "P95 err", "max err", "mean accuracy"]
    e = pd.read_csv(RES / "gates" / "gate_estimators.csv").set_index("estimator").loc["leak_ml"]
    b = pd.concat([b, pd.DataFrame([{"gate": "all", "runs": e["n"], "bias": e["bias"], "median err": e["median_err"], "P95 err": e["p95_err"],
                                     "max err": e["max_err"], "mean accuracy": e["mean_accuracy"]}])], ignore_index=True)
    write("gate_by_gate", tabular(b, {"runs": "int", **pct_cols(b.columns[2:])}, "Gate-level accuracy per gate type and over all 3{,}600 runs.",
                                  "tab:bygate", colspec="lrrrrrr"))
    e = pd.read_csv(RES / "gates" / "gate_estimators.csv")[["estimator", "bias", "median_err", "p95_err", "mean_accuracy"]]
    names = {"leak_ml_naive_supply": "plain sum of predicted currents, supply side", "leak_ml_naive_ground": "plain sum of predicted currents, ground side",
             "leak_ml_supply_side": "KCL-consistent, supply side", "leak_ml_ground_side": "KCL-consistent, ground side",
             "leak_ml": "KCL-consistent, mean of both (reported)"}
    e["estimator"] = e["estimator"].map(names)
    e.columns = ["estimator", "bias", "median err", "P95 err", "mean accuracy"]
    write("gate_estimators", tabular(e, pct_cols(e.columns[1:]), "Gate-level error of the ways of composing predicted transistor currents into a gate "
                                     "leakage (all 3{,}600 runs).", "tab:estimators", colspec="lrrrr"))
    s = pd.read_csv(ROOT / "data" / "gates" / "gate_spice.csv", dtype={"inputs": str})
    ref = s["ref_source"].value_counts().rename_axis("reference").reset_index(name="runs")
    ref["meaning"] = ref["reference"].map({"mandated": "mandated options; agrees with the tight solve within 1 %",
                                           "tight": "mandated solve disagreed with the tight solve; tight solve used",
                                           "tight_only": "mandated solve did not converge; tight solve used"})
    write("gate_reference", tabular(ref, {"runs": "int"}, "Origin of the 3{,}600 gate SPICE reference values.", "tab:ref", colspec="lrl"))


def circuit():
    c = pd.read_csv(RES / "circuit" / "circuit_results.csv")[["group", "n", "spice_median_A", "ml_median_A", "bias", "median_err", "p95_err", "max_err",
                                                              "mean_accuracy"]]
    c.columns = ["input vectors", "runs", "SPICE median [A]", "ML median [A]", "bias", "median err", "P95 err", "max err", "mean acc."]
    write("circuit_results", tabular(c, {"runs": "int", "SPICE median [A]": "sci", "ML median [A]": "sci", **pct_cols(c.columns[4:])},
                                     "Test-circuit results (8-bit parity checker, 256 input vectors $\\times$ 200 corners): all runs, and grouped by the number "
                                     "of ones in the input vector.", "tab:circuit", colspec="lrrrrrrrr"))
    d = pd.read_csv(RES / "circuit" / "circuit_decomposition.csv")[["comparison", "bias", "median_err", "p95_err", "max_err", "mean_accuracy"]]
    d["comparison"] = d["comparison"].map(lambda x: "hierarchical ML vs circuit SPICE" if x.startswith("ML") else
                                          "sum of isolated-gate SPICE vs circuit SPICE (loading only)")
    d.columns = ["comparison", "bias", "median err", "P95 err", "max err", "mean accuracy"]
    write("circuit_decomposition", tabular(d, pct_cols(d.columns[1:]), "Source of the circuit-level error: ML prediction versus the error caused by "
                                           "ignoring loading between gates.", "tab:cdecomp", colspec="lrrrrr"))
    g = pd.read_csv(RES / "gates" / "gate_estimators.csv").set_index("estimator").loc["leak_ml"]
    ci = pd.read_csv(RES / "circuit" / "circuit_results.csv").iloc[0]
    t = pd.DataFrame([{"level": "gates (18 cases)", "runs": g["n"], "bias": g["bias"], "median err": g["median_err"], "P95 err": g["p95_err"],
                       "max err": g["max_err"], "mean accuracy": g["mean_accuracy"]},
                      {"level": "parity checker", "runs": ci["n"], "bias": ci["bias"], "median err": ci["median_err"], "P95 err": ci["p95_err"],
                       "max err": ci["max_err"], "mean accuracy": ci["mean_accuracy"]}])
    write("headline", tabular(t, {"runs": "int", **pct_cols(t.columns[2:])}, "Headline accuracy of the ML leakage estimate against SPICE.",
                              "tab:headline", colspec="lrrrrrr"))


def errors():
    ea = RES / "error_analysis"
    for level in ("gate", "circuit"):
        d = pd.read_csv(ea / f"{level}_error_by_condition.csv")
        d = d[["condition", "range", "n", "bias", "median_err", "p95_err", "max_err"]]
        d.columns = ["condition", "range", "runs", "bias", "median err", "P95 err", "max err"]
        what = "Gate-level (3{,}600 runs)" if level == "gate" else "Parity-checker (51{,}200 runs)"
        write(f"{level}_by_condition", tabular(d, {"runs": "int", **pct_cols(d.columns[3:])},
                                               f"{what} error grouped by corner condition (vth0 deviation relative to the nominal value; "
                                               "negative = lower $|V_{th}|$).", f"tab:{level}cond", colspec="llrrrrr"))
    w = pd.read_csv(ea / "gate_worst_runs.csv").head(10)
    w["case"] = w["case"].str.replace("_", " ")
    w.columns = ["case", "corner", "VDD [V]", "T [C]", "NMOS vth0 [V]", "PMOS vth0 [V]", "SPICE [A]", "ML [A]", "error"]
    write("worst_runs", tabular(w, {"corner": "int", "VDD [V]": "g", "T [C]": "g", "NMOS vth0 [V]": "g", "PMOS vth0 [V]": "g", "SPICE [A]": "sci",
                                    "ML [A]": "sci", "error": P},
                                "The ten gate runs with the largest error and their corner conditions.", "tab:worst", colspec="lrrrrrrrr"))
    s = pd.read_csv(ea / "inv_off_share_by_temperature.csv")
    s["case"] = s["case"].str.replace("_", " ")
    s = s[["case", "temp", "n", "median_off_share", "median_err", "bias"]]
    s.columns = ["case", "T [C]", "runs", "OFF-channel share of leakage", "median err", "bias"]
    write("inv_off_share", tabular(s, {"runs": "int", "OFF-channel share of leakage": P, "median err": P, "bias": P},
                                   "Inverter: share of the leakage carried by the channel (sub-threshold) current of the OFF transistor, and the ML error, "
                                   "by temperature.", "tab:offshare", colspec="llrrrr"))


def deliverables():
    R = ROOT
    items = [
        ("1", "Datasets: 4 CSV files, 10,000 rows, 16 columns", "data/transistor/", [R / "data/transistor/nmos_on.csv"]),
        ("2", "Example netlists: transistor (4), gates (18), test circuit", "data/netlists/", [R / "data/netlists/gates/AND2_00.cir"]),
        ("3", "Data check: Kirchhoff check and three trend plots", "results/data_check/", [R / "results/data_check/kirchhoff.csv"]),
        ("4", "Model comparison table, 4 types x 4 cases (validation)", "results/model_comparison/", [R / "results/model_comparison/comparison_val.csv"]),
        ("5", "Chosen models: test errors, predicted-vs-SPICE plots, 4 model files", "models/, results/models/", [R / "models/nmos_on.joblib"]),
        ("6", "Gate results table (18 cases)", "results/gates/gate_results.csv", [R / "results/gates/gate_results.csv"]),
        ("7", "Gate parity plot (log axes)", "results/gates/gate_parity.png", [R / "results/gates/gate_parity.png"]),
        ("8", "Test-circuit results and parity plot", "results/circuit/", [R / "results/circuit/circuit_parity.png"]),
        ("9", "Code: scripts run in order, fixed seeds", "scripts/, src/dvdml/", [R / "scripts/01_generate_transistor_data.py"]),
        ("10", "Typed report", "report/", [R / "report/report.tex"]),
    ]
    rows = [{"#": n, "deliverable": d, "location": loc, "status": "present" if all(p.exists() for p in ps) else "missing"} for n, d, loc, ps in items]
    write("deliverables", tabular(pd.DataFrame(rows), caption="Deliverables and their location in the repository (status checked automatically).",
                                  label="tab:deliv", colspec="lllr"))


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    data_check(); model_comparison(); final_models(); model_development(); gates(); circuit(); errors(); deliverables()
    print("tables written to", OUT.relative_to(ROOT), ":", ", ".join(sorted(p.stem for p in OUT.glob("*.tex"))))
