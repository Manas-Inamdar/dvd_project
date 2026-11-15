"""Phase 2.3-2.5: data checks for the four transistor datasets.

Outputs (results/data_check/)
  kirchhoff.csv / kirchhoff.md   Kirchhoff check (sum of the four terminal currents) per case
  distributions.png + distributions.csv   target magnitude distributions (feeds Phase-3 preprocessing)
  trend_off_vs_temperature.png, trend_off_vs_vth0.png, trend_ig_vs_toxe.png   the three required trend plots
  trend_checks.json              automatic monotonicity checks of the three trends
Trend plots use controlled one-at-a-time sweeps (everything else fixed) simulated with the same netlist builder.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from dvdml import dataset, modelcard  # noqa: E402
from dvdml.config import load_config, model_path  # noqa: E402
from dvdml.sampling import CASES  # noqa: E402

CUR = ["id", "ig", "is", "ib"]
FLOOR = 1e-16  # A, Kirchhoff check: samples whose largest current is below this are reported separately


def kirchhoff(data_dir: Path, out: Path):
    rows = []
    for case in CASES:
        d = pd.read_csv(data_dir / f"{case}.csv")
        i = d[CUR].to_numpy()
        s = np.abs(i.sum(axis=1))
        mx = np.abs(i).max(axis=1)
        tot = np.abs(i).sum(axis=1)
        rel = s / np.maximum(mx, 1e-30)
        above = mx > FLOOR
        rows.append({
            "case": case, "rows": len(d),
            "abs_residual_median_A": np.median(s), "abs_residual_p95_A": np.percentile(s, 95), "abs_residual_max_A": s.max(),
            "rel_residual_median": np.median(rel), "rel_residual_p95": np.percentile(rel, 95), "rel_residual_max": rel.max(),
            "frac_max|I|<=1e-16A": 1 - above.mean(),
            "rel_residual_median_above_floor": np.median(rel[above]), "rel_residual_p95_above_floor": np.percentile(rel[above], 95),
            "rel_residual_max_above_floor": rel[above].max(),
            "worst_abs_residual_over_sum|I|": (s / np.maximum(tot, 1e-30)).max(),
        })
    k = pd.DataFrame(rows)
    k.to_csv(out / "kirchhoff.csv", index=False)
    with open(out / "kirchhoff.md", "w") as f:
        f.write("Kirchhoff check: |id+ig+is+ib| per sample. Relative = divided by max|I| of that sample.\n"
                f"'above floor' = samples whose largest current exceeds {FLOOR:g} A (below that the solver noise floor dominates).\n\n")
        f.write(k.to_markdown(index=False, floatfmt=".2e") if _has_tabulate() else k.to_string(index=False))
    return k


def _has_tabulate():
    try:
        import tabulate  # noqa: F401
        return True
    except ImportError:
        return False


def distributions(data_dir: Path, out: Path):
    fig, axes = plt.subplots(4, 4, figsize=(14, 11))
    stats = []
    for r, case in enumerate(CASES):
        d = pd.read_csv(data_dir / f"{case}.csv")
        for c, cur in enumerate(CUR):
            a = np.abs(d[cur].to_numpy())
            nz = a[a > 0]
            ax = axes[r, c]
            ax.hist(np.log10(nz), bins=60, color="tab:blue")
            ax.set_title(f"{case} |{cur}|", fontsize=9)
            ax.set_xlabel("log10 |I| (A)", fontsize=8)
            sign_neg = (d[cur] < 0).mean()
            stats.append({"case": case, "current": cur, "frac_exact_zero": (a == 0).mean(), "frac_negative": sign_neg,
                          "frac_below_1e-17": (a < 1e-17).mean(), "frac_below_1e-16": (a < 1e-16).mean(),
                          "min_nonzero_log10": np.log10(nz.min()), "median_log10": np.median(np.log10(nz)), "max_log10": np.log10(nz.max())})
    fig.tight_layout()
    fig.savefig(out / "distributions.png", dpi=110)
    plt.close(fig)
    pd.DataFrame(stats).to_csv(out / "distributions.csv", index=False)
    return pd.DataFrame(stats)


def sweep(cfg, text, nom, case, var, values, base_over=None):
    """Simulate a controlled sweep of one variable; returns DataFrame with currents."""
    a = cfg["assignment"]
    dev = case.split("_")[0]
    vdd = a["vdd_nom"]
    vd, vs = {"nmos": (vdd, 0.0), "pmos": (0.0, vdd)}[dev]   # worst-case leakage bias: full VDD across the device
    vg, vb = {"nmos_on": (vdd, 0), "nmos_off": (0, 0), "pmos_on": (0, vdd), "pmos_off": (vdd, vdd)}[case]
    if case.endswith("_on"):
        vd, vs = {"nmos": (0.0, 0.0), "pmos": (vdd, vdd)}[dev]   # Vds = 0: pure gate-tunnelling operating point
    base = {"vdd": vdd, "temp": 27.0, "w": 4 * a["lmin"], "vd": vd, "vs": vs, "vg": vg, "vb": vb, **nom[dev]}
    if base_over:
        base.update(base_over)
    rows = []
    for v in values:
        r = dict(base)
        r[var] = v
        rows.append(r)
    df = pd.DataFrame(rows)
    res = dataset.simulate_samples(case, df, cfg, text)
    return res


def trend_plots(cfg, text, nom, out: Path):
    checks = {}
    # 1) OFF current vs temperature
    temps = np.linspace(cfg["assignment"]["temp_min"], cfg["assignment"]["temp_max"], 34)
    fig, ax = plt.subplots(figsize=(6, 4.2))
    for case in ("nmos_off", "pmos_off"):
        r = sweep(cfg, text, nom, case, "temp", temps)
        y = np.abs(r["id"].to_numpy())
        ax.semilogy(r["temp"], y, "o-", ms=3, label=f"{case} |Id|")
        checks[f"{case}: |Id| increases with temperature"] = bool(np.all(np.diff(y) > 0))
        checks[f"{case}: |Id| 125C / -40C ratio"] = float(y[-1] / y[0])
    ax.set_xlabel("temperature (degC)"); ax.set_ylabel("|OFF current| (A)"); ax.grid(True, which="both", alpha=.3); ax.legend()
    ax.set_title("OFF current vs temperature (|Vds| = VDD = 1 V, W = 4 Lmin, nominal process)", fontsize=8)
    fig.tight_layout(); fig.savefig(out / "trend_off_vs_temperature.png", dpi=120); plt.close(fig)

    # 2) OFF current vs vth0 (+/-10 % of nominal)
    fig, ax = plt.subplots(figsize=(6, 4.2))
    for case in ("nmos_off", "pmos_off"):
        dev = case.split("_")[0]
        vals = nom[dev]["vth0"] * np.linspace(0.9, 1.1, 21)
        r = sweep(cfg, text, nom, case, "vth0", vals)
        y = np.abs(r["id"].to_numpy())
        ax.semilogy(np.abs(r["vth0"]), y, "o-", ms=3, label=f"{case} |Id|")
        checks[f"{case}: |Id| decreases as |vth0| increases"] = bool(np.all(np.diff(y) < 0))
        checks[f"{case}: |Id| ratio (|vth0| -10% / +10%)"] = float(y[0] / y[-1])
    ax.set_xlabel("|vth0| (V)"); ax.set_ylabel("|OFF current| (A)"); ax.grid(True, which="both", alpha=.3); ax.legend()
    ax.set_title("OFF current vs vth0 (T = 27 C, |Vds| = 1 V, W = 4 Lmin)", fontsize=8)
    fig.tight_layout(); fig.savefig(out / "trend_off_vs_vth0.png", dpi=120); plt.close(fig)

    # 3) gate current vs toxe (ON devices, Vds = 0 -> pure gate leakage; also OFF devices with Vg/Vb as the case defines)
    fig, ax = plt.subplots(figsize=(6, 4.2))
    for case in ("nmos_on", "pmos_on"):
        dev = case.split("_")[0]
        vals = nom[dev]["toxe"] * np.linspace(0.9, 1.1, 21)
        r = sweep(cfg, text, nom, case, "toxe", vals)
        y = np.abs(r["ig"].to_numpy())
        ax.semilogy(r["toxe"] * 1e9, y, "o-", ms=3, label=f"{case} |Ig|")
        checks[f"{case}: |Ig| decreases as toxe increases"] = bool(np.all(np.diff(y) < 0))
        checks[f"{case}: |Ig| ratio (toxe -10% / +10%)"] = float(y[0] / y[-1])
    ax.set_xlabel("toxe (nm)"); ax.set_ylabel("|gate current| (A)"); ax.grid(True, which="both", alpha=.3); ax.legend()
    ax.set_title("Gate current vs toxe (ON devices, Vds = 0, T = 27 C, W = 4 Lmin)", fontsize=8)
    fig.tight_layout(); fig.savefig(out / "trend_ig_vs_toxe.png", dpi=120); plt.close(fig)
    (out / "trend_checks.json").write_text(json.dumps(checks, indent=2))
    return checks


def main():
    cfg = load_config()
    text = model_path(cfg).read_text()
    nom = modelcard.nominals(text, cfg["assignment"]["process_params"])
    data_dir = ROOT / "data" / "transistor"
    out = ROOT / "results" / "data_check"
    out.mkdir(parents=True, exist_ok=True)
    k = kirchhoff(data_dir, out)
    print(k.T.to_string())
    s = distributions(data_dir, out)
    print(s.to_string(index=False, float_format=lambda x: f"{x:.3g}"))
    checks = trend_plots(cfg, text, nom, out)
    print(json.dumps(checks, indent=2))


if __name__ == "__main__":
    main()
