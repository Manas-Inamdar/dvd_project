"""Phase 2.1-2.2: generate the four single-transistor datasets (NMOS ON/OFF, PMOS ON/OFF).

Outputs
  data/transistor/<case>.csv           10,000 valid rows, columns exactly as in the assignment
  data/transistor/generation_log.json  counts, failures, timing, simulator version, seed
  data/netlists/single_transistor/<case>.cir  example netlist (first sample of each dataset)
Usage: python scripts/01_generate_transistor_data.py [--n 10000] [--workers 12]
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from dvdml import dataset, modelcard  # noqa: E402
from dvdml.config import load_config, model_path  # noqa: E402
from dvdml.netlist import single_transistor_netlist  # noqa: E402
from dvdml.sampling import CASES  # noqa: E402
from dvdml.spice import ngspice_exe  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=None)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--outdir", default=str(ROOT / "data" / "transistor"))
    args = ap.parse_args()

    cfg = load_config()
    n = args.n or cfg["data"]["n_samples"]
    text = model_path(cfg).read_text()
    nom = modelcard.nominals(text, cfg["assignment"]["process_params"])
    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    (ROOT / "data" / "netlists" / "single_transistor").mkdir(parents=True, exist_ok=True)

    ver = subprocess.run([ngspice_exe(cfg), "-v"], capture_output=True, text=True).stdout
    ver = next((ln.strip("* ").strip() for ln in ver.splitlines() if "ngspice-" in ln), "unknown")
    log = {"simulator": ver, "seed": cfg["data"]["seed"], "n": n, "cases": {}}

    for case in CASES:
        t0 = time.time()
        df, failed = dataset.generate_case(case, n, cfg, nom, text, workers=args.workers)
        df.to_csv(out / f"{case}.csv", index=False)
        net = single_transistor_netlist(case, df.iloc[0], cfg, text, title=f"example single transistor netlist: {case} (first dataset row)")
        (ROOT / "data" / "netlists" / "single_transistor" / f"{case}.cir").write_text(net, encoding="utf-8")
        log["cases"][case] = {"rows": len(df), "failed_sims_replaced": failed, "seconds": round(time.time() - t0, 1)}
        print(f"{case}: {len(df)} rows, {failed} failed sims replaced, {time.time() - t0:.0f}s")
    (out / "generation_log.json").write_text(json.dumps(log, indent=2))


if __name__ == "__main__":
    main()
