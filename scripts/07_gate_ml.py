"""Phase 4.4-4.6: ML gate-leakage prediction vs SPICE for the 18 gate/input cases x 200 corners.

Outputs
  results/gates/gate_runs_ml.csv       per run: SPICE leakage, ML leakage (supply side and ground side), node voltages
  results/gates/gate_results.csv       one row per case (18): SPICE median, ML median, bias, median error, 95th-percentile error (+ more)
  results/gates/gate_by_gate.csv       summary per gate type
  results/gates/gate_parity.png        ML vs SPICE leakage, all gate simulations, log-log
  results/gates/gate_error_vs_corner.png   error vs temperature and vs vth0 (for the error analysis)
Error definition: e = |ML - SPICE| / SPICE; bias = mean of (ML - SPICE)/SPICE (signed); accuracy = 1 - mean(e).
"""
import sys
from pathlib import Path

import joblib
import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from dvdml import gate_ml, modelcard  # noqa: E402
from dvdml.config import load_config, model_path  # noqa: E402
from dvdml.sampling import CASES  # noqa: E402


def summarize(df: pd.DataFrame, ml="leak_ml", ref="leak_spice") -> dict:
    e = np.abs(df[ml] - df[ref]) / df[ref]
    s = (df[ml] - df[ref]) / df[ref]
    return {"n": len(df), "spice_median_A": df[ref].median(), "ml_median_A": df[ml].median(), "bias": s.mean(), "median_err": e.median(),
            "p95_err": e.quantile(0.95), "mean_err": e.mean(), "mean_accuracy": 1 - e.mean(), "max_err": e.max()}


def main():
    cfg = load_config()
    out = ROOT / "results" / "gates"; out.mkdir(parents=True, exist_ok=True)
    models = {c: joblib.load(ROOT / "models_saved" / f"{c}.joblib") for c in CASES}
    runs = pd.read_csv(ROOT / "data" / "gates" / "gate_spice.csv", dtype={"inputs": str})
    corners = pd.read_csv(ROOT / "data" / "gates" / "corners.csv")
    res, devices = gate_ml.predict_runs(runs, corners, models, cfg["assignment"]["lmin"])
    res.to_csv(out / "gate_runs_ml.csv", index=False)
    devices.drop(columns=[c for c in devices.columns if c.startswith("lvl_")]).to_csv(out / "gate_devices_ml.csv", index=False)

    rows = []
    for case, g in res.groupby("case", sort=False):
        rows.append({"case": case, "gate": g.gate.iloc[0], **summarize(g), "median_err_supply_side": summarize(g, "leak_ml_supply_side")["median_err"],
                     "median_err_ground_side": summarize(g, "leak_ml_ground_side")["median_err"],
                     "median_err_naive_supply": summarize(g, "leak_ml_naive_supply")["median_err"],
                     "frac_tight_reference_runs": (g.ref_source != "mandated").mean()})
    tab = pd.DataFrame(rows)
    tab.to_csv(out / "gate_results.csv", index=False)
    by = pd.DataFrame([{"gate": k, **summarize(g)} for k, g in res.groupby("gate", sort=False)])
    by.to_csv(out / "gate_by_gate.csv", index=False)
    overall = summarize(res)
    pd.set_option("display.width", 250)
    print(tab[["case", "spice_median_A", "ml_median_A", "bias", "median_err", "p95_err", "mean_accuracy"]].to_string(index=False, float_format=lambda x: f"{x:.4g}"))
    print("OVERALL", {k: round(float(v), 5) for k, v in overall.items()})
    for col in ("leak_ml_naive_supply", "leak_ml_naive_ground", "leak_ml_supply_side", "leak_ml_ground_side", "leak_ml"):
        s = summarize(res, col)
        print(f"{col:22s} bias={s['bias']:+.4f} median_err={s['median_err']:.4f} p95_err={s['p95_err']:.4f} mean_err={s['mean_err']:.4f}")
    pd.DataFrame([{"estimator": col, **summarize(res, col)} for col in ("leak_ml_naive_supply", "leak_ml_naive_ground", "leak_ml_supply_side", "leak_ml_ground_side", "leak_ml")]).to_csv(out / "gate_estimators.csv", index=False)

    fig, ax = plt.subplots(figsize=(6, 6))
    for gate, g in res.groupby("gate"):
        ax.loglog(g.leak_spice, g.leak_ml, ".", ms=3, alpha=.6, label=gate)
    lo, hi = res.leak_spice.min() * .7, res.leak_spice.max() * 1.4
    ax.loglog([lo, hi], [lo, hi], "k-", lw=.7)
    ax.set_xlabel("SPICE leakage (A)"); ax.set_ylabel("ML leakage (A)"); ax.legend(); ax.grid(True, which="both", alpha=.3)
    ax.set_title("Gate leakage: ML vs SPICE (all 18 cases x 200 corners)")
    fig.tight_layout(); fig.savefig(out / "gate_parity.png", dpi=120); plt.close(fig)

    res["err"] = np.abs(res.leak_ml - res.leak_spice) / res.leak_spice
    cor = corners.set_index("corner")
    nom_n_vth0 = modelcard.nominals(model_path(cfg).read_text(), ["vth0"])["nmos"]["vth0"]
    res["n_vth0_rel"] = res["corner"].map(cor["n_vth0"]) / nom_n_vth0
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    for ax, (x, lab) in zip(axes, [(res.temp, "temperature (degC)"), (res.vdd, "VDD (V)"), (res["n_vth0_rel"], "NMOS vth0 / nominal")]):
        ax.semilogy(x, res.err.clip(lower=1e-5), ".", ms=2, alpha=.4); ax.set_xlabel(lab); ax.set_ylabel("relative error"); ax.grid(True, which="both", alpha=.3)
    fig.tight_layout(); fig.savefig(out / "gate_error_vs_corner.png", dpi=110); plt.close(fig)


if __name__ == "__main__":
    main()
