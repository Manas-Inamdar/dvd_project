"""Phase 3b (assumption A4 / D-037): extra TRAINING-ONLY samples for the four transistor cases.

The deliverable datasets (scripts/01) stay at 10,000 rows per case. The assignment allows the sample count to be increased, so 30,000 additional samples per
case are drawn from the same distributions with an independent random stream (batch 101) and simulated the same way. Validation/test rows are never touched.
Output: data/transistor_extra/<case>.csv.gz (same columns), data/transistor_extra/generation_log.json
Usage: python scripts/01b_generate_extra_data.py [--n 30000] [--workers 12]
"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from dvdml import dataset, modelcard  # noqa: E402
from dvdml.config import load_config, model_path  # noqa: E402
from dvdml.sampling import CASES, sample_case  # noqa: E402

EXTRA_BATCH = 101   # batches 0..99 are used for failure replacement in scripts/01


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30000)
    ap.add_argument("--workers", type=int, default=None)
    args = ap.parse_args()
    cfg = load_config()
    text = model_path(cfg).read_text()
    nom = modelcard.nominals(text, cfg["assignment"]["process_params"])
    out = ROOT / "data" / "transistor_extra"; out.mkdir(parents=True, exist_ok=True)
    log = {}
    for case in CASES:
        f = out / f"{case}.csv.gz"
        if f.exists():
            print(f"{case}: exists, skipped", flush=True)
            continue
        t0 = time.time()
        draw = sample_case(case, args.n, cfg["data"]["seed"], cfg, nom, batch=EXTRA_BATCH)
        done = dataset.simulate_samples(case, draw, cfg, text, args.workers)[cfg["data"]["columns"]]
        done.to_csv(f, index=False)
        log[case] = {"rows": len(done), "failed_sims_dropped": len(draw) - len(done), "seconds": round(time.time() - t0, 1)}
        print(case, log[case], flush=True)
    (out / "generation_log.json").write_text(json.dumps(log, indent=2))


if __name__ == "__main__":
    main()
