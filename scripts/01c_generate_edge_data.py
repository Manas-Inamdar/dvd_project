"""Phase 7 (D-043): extra TRAINING-ONLY transistor samples concentrated at the rail corners of the (Vd, Vs) box.

Why: in logic gates every transistor terminal sits at (or within microvolts of) a rail, i.e. at a CORNER of the uniformly sampled (Vd, Vs) box,
where the uniform datasets have almost no samples. ngspice proves that the remaining ML error there is a model error, not a reference mismatch:
the single-transistor netlist at the exact gate operating points reproduces the gate-level SPICE input current to < 0.1 % (D-043).

Sampling (per case, deterministic, batch 102; batches 0..99 = failure replacement of scripts/01, 101 = scripts/01b):
  VDD, temperature, process parameters: exactly as sample_case (uniform, same ranges).
  W: log-uniform in [1, 8] x Lmin (more samples at small widths, where Weff/W changes fastest; minimum-size devices are typical in gates).
  Vd and Vs, independently: with p = 0.4 EXACTLY at a rail, p = 0.4 NEAR a rail (distance = 0.1 VDD u^2, u ~ U(0,1)), p = 0.2 uniform in [0, VDD];
  the rail (0 or VDD) is chosen with probability 1/2.
No gate- or circuit-level information is used except the fact that logic nodes sit at the rails.
Output: data/transistor_edge/<case>.csv.gz (same columns), data/transistor_edge/generation_log.json
Usage: python scripts/01c_generate_edge_data.py [--n 20000] [--workers 4]
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from dvdml import dataset, modelcard  # noqa: E402
from dvdml.config import load_config, model_path  # noqa: E402
from dvdml.sampling import CASES, sample_case  # noqa: E402

EDGE_BATCH = 102


def edge_draw(case, n, cfg, nom):
    a = cfg["assignment"]
    df = sample_case(case, n, cfg["data"]["seed"], cfg, nom, batch=EDGE_BATCH)        # VDD, T, process, Vg, Vb as usual
    rng = np.random.default_rng([cfg["data"]["seed"], CASES.index(case), EDGE_BATCH, 1])
    vdd = df["vdd"].to_numpy()

    def terminal():
        kind = rng.choice(3, size=n, p=[0.4, 0.4, 0.2])
        dist = np.where(kind == 0, 0.0, 0.1 * vdd * rng.uniform(0, 1, n) ** 2)
        high = rng.uniform(0, 1, n) < 0.5
        v = np.where(high, vdd - dist, dist)
        return np.where(kind == 2, rng.uniform(0, 1, n) * vdd, v)
    df["vd"], df["vs"] = terminal(), terminal()
    df["w"] = a["lmin"] * np.exp(rng.uniform(np.log(a["w_min_mult"]), np.log(a["w_max_mult"]), n))
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20000)
    ap.add_argument("--workers", type=int, default=4)     # low-load mode (D-042)
    ap.add_argument("--cases", nargs="*", default=list(CASES))
    args = ap.parse_args()
    cfg = load_config()
    text = model_path(cfg).read_text()
    nom = modelcard.nominals(text, cfg["assignment"]["process_params"])
    out = ROOT / "data" / "transistor_edge"
    out.mkdir(parents=True, exist_ok=True)
    logf = out / "generation_log.json"
    log = json.loads(logf.read_text()) if logf.exists() else {}
    for case in args.cases:
        f = out / f"{case}.csv.gz"
        if f.exists():
            print(f"{case}: exists, skipped", flush=True)
            continue
        t0 = time.time()
        draw = edge_draw(case, args.n, cfg, nom)
        done = dataset.simulate_samples(case, draw, cfg, text, args.workers)[cfg["data"]["columns"]]
        done.to_csv(f, index=False)
        log[case] = {"rows": len(done), "failed_sims_dropped": len(draw) - len(done), "seconds": round(time.time() - t0, 1), "batch": EDGE_BATCH,
                     "simulator": "ngspice-47 (official 64-bit build, KLU)"}
        logf.write_text(json.dumps(log, indent=2))
        print(case, log[case], flush=True)


if __name__ == "__main__":
    main()
