"""Report: where the largest gate- and circuit-level errors occur (corner conditions, gate cases, worst runs).

Reads the ML-vs-SPICE run tables written by scripts 07 and 09 and the 200 PVT corners of script 06; no model is evaluated here.
Outputs (results/error_analysis/)
  gate_error_by_condition.csv     gate-level error grouped by temperature, VDD and NMOS/PMOS vth0 deviation (quartile bins)
  circuit_error_by_condition.csv  same for the parity checker
  gate_worst_runs.csv             the 15 gate runs with the largest error, with their corner conditions
  corner_spread.csv               spread of the per-corner mean signed error (gates and circuit)
Usage: python scripts/10_error_analysis.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from dvdml.modelcard import nominals  # noqa: E402
from dvdml.config import load_config, model_path  # noqa: E402

OUT = ROOT / "results" / "error_analysis"


def stats(e: pd.Series) -> dict:
    a = e.abs()
    return {"n": len(e), "bias": e.mean(), "median_err": a.median(), "p95_err": a.quantile(0.95), "max_err": a.max(),
            "mean_accuracy": 1 - a.mean()}


def by_condition(runs: pd.DataFrame, corners: pd.DataFrame, nom: dict) -> pd.DataFrame:
    d = runs.merge(corners[["corner", "n_vth0", "p_vth0"]], on="corner", how="left")
    d["n_vth0_dev"] = d["n_vth0"] / nom["nmos"]["vth0"] - 1
    d["p_vth0_dev"] = d["p_vth0"] / nom["pmos"]["vth0"] - 1
    groups = {"temperature [C]": ("temp", [-40, 0, 40, 80, 125.0001]),
              "VDD [V]": ("vdd", [0.9, 0.95, 1.0, 1.05, 1.1001]),
              "NMOS vth0 deviation": ("n_vth0_dev", [-0.1, -0.05, 0, 0.05, 0.1001]),
              "PMOS vth0 deviation": ("p_vth0_dev", [-0.1, -0.05, 0, 0.05, 0.1001])}
    rows = []
    for label, (col, edges) in groups.items():
        for iv, g in d.groupby(pd.cut(d[col], edges, right=False), observed=True):
            lo, hi = iv.left, min(iv.right, edges[-1] - 0.0001)
            name = f"{lo:+.0%} to {hi:+.0%}" if "deviation" in label else f"{lo:g} to {hi:g}"
            rows.append({"condition": label, "range": name, **stats(g["err"])})
    return pd.DataFrame(rows)


def main():
    cfg = load_config()
    nom = nominals(model_path(cfg).read_text(), ["vth0"])
    OUT.mkdir(parents=True, exist_ok=True)
    corners = pd.read_csv(ROOT / "data" / "gates" / "corners.csv")

    g = pd.read_csv(ROOT / "results" / "gates" / "gate_runs_ml.csv", dtype={"inputs": str})
    g["err"] = (g["leak_ml"] - g["leak_spice"]) / g["leak_spice"]
    c = pd.read_csv(ROOT / "results" / "circuit" / "circuit_runs_ml.csv", dtype={"bits": str})
    c["err"] = (c["leak_ml"] - c["leak_spice"]) / c["leak_spice"]

    by_condition(g, corners, nom).to_csv(OUT / "gate_error_by_condition.csv", index=False)
    by_condition(c, corners, nom).to_csv(OUT / "circuit_error_by_condition.csv", index=False)

    w = g.merge(corners[["corner", "n_vth0", "p_vth0"]], on="corner")
    w["abs_err"] = w["err"].abs()
    w = w.nlargest(15, "abs_err")[["case", "corner", "vdd", "temp", "n_vth0", "p_vth0", "leak_spice", "leak_ml", "err"]]
    w.to_csv(OUT / "gate_worst_runs.csv", index=False)

    rows = []
    for level, d in (("gates (per gate case)", g), ("parity checker", c)):
        key = ["case", "corner"] if "case" in d else ["corner"]
        per = d.groupby(key)["err"].mean()
        rows.append({"level": level, "std_of_corner_mean_err": per.std(), "max_abs_corner_mean_err": per.abs().max(),
                     "std_within_corner": d.groupby(key)["err"].std().mean() if "case" not in d else np.nan})
    pd.DataFrame(rows).to_csv(OUT / "corner_spread.csv", index=False)

    # INV only (one OFF device per run): share of the leakage that is OFF-device channel (sub-threshold) current, by temperature
    dev = pd.read_csv(ROOT / "results" / "gates" / "gate_devices_ml.csv")
    inv = g[g["gate"] == "INV"][["case", "temp", "leak_ml", "err"]]
    off = dev[~dev["on"]].groupby("run_index")["id"].apply(lambda s: s.abs().sum())
    inv = inv.join(off.rename("off_channel"), how="left")
    inv["off_share"] = inv["off_channel"] / inv["leak_ml"]
    tb = pd.cut(inv["temp"], [-40, 0, 40, 80, 125.0001], right=False)
    sh = inv.groupby(["case", tb], observed=True).agg(n=("err", "size"), median_off_share=("off_share", "median"),
                                                       median_err=("err", lambda e: e.abs().median()), bias=("err", "mean")).reset_index()
    sh["temp"] = sh["temp"].map(lambda iv: f"{iv.left:g} to {min(iv.right, 125):g}")
    sh.to_csv(OUT / "inv_off_share_by_temperature.csv", index=False)

    pd.set_option("display.width", 200)
    for f in sorted(OUT.glob("*.csv")):
        print(f"== {f.name}\n{pd.read_csv(f).to_string(index=False, float_format=lambda x: f'{x:.4g}')}\n")


if __name__ == "__main__":
    main()
