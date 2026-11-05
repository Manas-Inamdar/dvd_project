"""Phase 4.1-4.3: 200 shared corners + SPICE reference for every gate / input combination (18 cases x 200 corners = 3,600 runs).

Outputs
  data/gates/corners.csv       the 200 corners (reused by the test circuit, Part C)
  data/gates/gate_spice.csv    per run: gate, case, inputs, corner, vdd, temp, node voltages (out and internal), source currents, leakage (D-011)
  netlists/gates/<case>.cir    example netlists (corner 0)
These results are EVALUATION data only; they are never used for training.
Usage: python scripts/06_gate_spice.py [--corners 200] [--workers 12]
"""
import argparse
import math
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from dvdml import gates, modelcard  # noqa: E402
from dvdml.config import load_config, model_path  # noqa: E402
from dvdml.corners import make_corners  # noqa: E402
from dvdml.refsolve import solve_with_crosscheck  # noqa: E402
from dvdml.spice import run_netlist  # noqa: E402


def one(job):
    gate, bits, corner, cfg, text = job
    vals, source, rel_diff = solve_with_crosscheck(
        lambda tier: gates.gate_netlist(gate, bits, corner, cfg, text, fallback=tier), run_netlist, gates.parse_values,
        lambda v: gates.leakage_from_values(v, gate, bits), cfg)
    if vals is None:
        return None
    try:
        row = {"ref_source": source, "rel_diff_mandated_vs_tight": rel_diff, "gate": gate, "case": gates.case_name(gate, bits), "inputs": "".join(map(str, bits)), "corner": int(corner["corner"]),
               "vdd": corner["vdd"], "temp": corner["temp"], "v_out": vals["v(out)"],
               "leak_spice": gates.leakage_from_values(vals, gate, bits), "leak_ground_side": gates.leakage_ground_side(vals, gate, bits),
               "i_vdd": vals["i(vdd)"], "i_vgnd": vals["i(vgnd)"]}
        for r in ("x", "y", "n"):
            row[f"v_{r}"] = vals.get(f"v({r})", float("nan"))
        for n in gates.GATES[gate]["inputs"]:
            row[f"i_v{n}"] = vals[f"i(v{n})"]
        if not all(math.isfinite(row[k]) for k in ("v_out", "leak_spice", "i_vdd")):
            return None
        return row
    except (RuntimeError, KeyError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corners", type=int, default=200)
    ap.add_argument("--workers", type=int, default=12)
    args = ap.parse_args()
    cfg = load_config()
    text = model_path(cfg).read_text()
    nom = modelcard.nominals(text, cfg["assignment"]["process_params"])
    out = ROOT / "data" / "gates"; out.mkdir(parents=True, exist_ok=True)
    (ROOT / "netlists" / "gates").mkdir(parents=True, exist_ok=True)

    corners = make_corners(args.corners, cfg["data"]["seed"], cfg, nom)
    corners.to_csv(out / "corners.csv", index=False)
    for gate, bits in gates.all_cases():
        net = gates.gate_netlist(gate, bits, corners.iloc[0], cfg, text, title=f"example gate netlist {gates.case_name(gate, bits)}")
        (ROOT / "netlists" / "gates" / f"{gates.case_name(gate, bits)}.cir").write_text(net, encoding="utf-8")

    jobs = [(g, b, corners.iloc[i], cfg, text) for g, b in gates.all_cases() for i in range(len(corners))]
    with ThreadPoolExecutor(args.workers) as ex:
        rows = list(ex.map(one, jobs))
    failed = sum(r is None for r in rows)
    df = pd.DataFrame([r for r in rows if r is not None])
    df.to_csv(out / "gate_spice.csv", index=False)
    print(f"{len(df)} runs ok, {failed} failed, {df.case.nunique()} cases; reference source: {df.ref_source.value_counts().to_dict()}")
    print(df.groupby("case").leak_spice.median().to_string(float_format=lambda x: f"{x:.3e}"))


if __name__ == "__main__":
    main()
