"""Phase 5.1-5.2: SPICE reference of the 8-bit parity checker, 256 input vectors x 200 corners = 51,200 runs.

Each run is solved with the mandated options and with the tight cross-check solve (see dvdml/refsolve.py, D-031).
Outputs
  data/circuit/circuit_spice.csv        per run: vector, corner, vdd, temp, v_out, expected parity, leakage (D-011), ground-side leakage, ref_source
  data/netlists/circuit/parity8_<bits>.cir   example netlists (corner 0) for 4 input vectors
Resumable: finished corner chunks are stored in data/circuit/parts/ and skipped on a re-run.
Usage: python scripts/08_circuit_spice.py [--workers 12] [--chunk 20]
"""
import argparse
import itertools
import math
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from dvdml import circuit  # noqa: E402
from dvdml.config import load_config, model_path  # noqa: E402
from dvdml.refsolve import solve_with_crosscheck  # noqa: E402
from dvdml.spice import run_netlist  # noqa: E402

VECTORS = list(itertools.product((0, 1), repeat=circuit.N_INPUTS))


def one(job):
    vec_id, bits, corner, cfg, text = job
    vals, source, d = solve_with_crosscheck(lambda t: circuit.circuit_netlist(bits, corner, cfg, text, fallback=t), run_netlist, circuit.parse_values,
                                            lambda v: circuit.leakage_from_values(v, bits), cfg)
    if vals is None:
        return {"vector": vec_id, "corner": int(corner["corner"]), "ref_source": "failed"}
    leak = circuit.leakage_from_values(vals, bits)
    return {"vector": vec_id, "bits": "".join(map(str, bits)), "corner": int(corner["corner"]), "vdd": corner["vdd"], "temp": corner["temp"],
            "parity": circuit.parity(bits), "v_out": vals["v(out)"], "leak_spice": leak, "leak_ground_side": circuit.leakage_ground_side(vals, bits),
            "ref_source": source, "rel_diff_mandated_vs_tight": d}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--chunk", type=int, default=20, help="corners per resumable chunk")
    ap.add_argument("--corners", type=int, default=None, help="debug: use only the first N corners")
    ap.add_argument("--vectors", type=int, default=256)
    args = ap.parse_args()
    cfg = load_config()
    text = model_path(cfg).read_text()
    corners = pd.read_csv(ROOT / "data" / "gates" / "corners.csv")
    if args.corners:
        corners = corners.iloc[: args.corners]
    out = ROOT / "data" / "circuit"; parts = out / "parts"; parts.mkdir(parents=True, exist_ok=True)
    (ROOT / "data" / "netlists" / "circuit").mkdir(parents=True, exist_ok=True)
    for bits in [(0,) * 8, (1,) + (0,) * 7, (1, 0, 1, 1, 0, 0, 1, 0), (1,) * 8]:
        (ROOT / "data" / "netlists" / "circuit" / f"parity8_{''.join(map(str, bits))}.cir").write_text(
            circuit.circuit_netlist(bits, corners.iloc[0], cfg, text, title=f"example parity8 netlist, inputs {''.join(map(str, bits))}"), encoding="utf-8")

    t0 = time.time()
    n_chunks = math.ceil(len(corners) / args.chunk)
    for ci in range(n_chunks):
        part = parts / f"chunk_{ci:03d}.csv"
        if part.exists():
            print(f"chunk {ci + 1}/{n_chunks}: exists, skipped", flush=True)
            continue
        sub = corners.iloc[ci * args.chunk:(ci + 1) * args.chunk]
        jobs = [(vid, bits, sub.iloc[k], cfg, text) for k in range(len(sub)) for vid, bits in enumerate(VECTORS[: args.vectors])]
        with ThreadPoolExecutor(args.workers) as ex:
            rows = list(ex.map(one, jobs))
        pd.DataFrame(rows).to_csv(part, index=False)
        print(f"chunk {ci + 1}/{n_chunks}: {len(rows)} runs, {time.time() - t0:.0f}s elapsed", flush=True)
    df = pd.concat([pd.read_csv(p, dtype={"bits": str}) for p in sorted(parts.glob("chunk_*.csv"))], ignore_index=True)
    failed = int((df.ref_source == "failed").sum())
    df = df[df.ref_source != "failed"]
    df.to_csv(out / "circuit_spice.csv", index=False)
    print(f"{len(df)} runs ok, {failed} failed; reference source: {df.ref_source.value_counts().to_dict()}; negative leakage: {int((df.leak_spice <= 0).sum())}")
    ok_logic = (abs(df.v_out - df.parity * df.vdd) < 0.02 * df.vdd).mean()
    print(f"output at the correct logic rail in {ok_logic:.4%} of runs")


if __name__ == "__main__":
    main()
