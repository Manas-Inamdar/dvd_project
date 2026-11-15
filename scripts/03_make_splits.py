"""Part A, step 2: fixed-seed random 70/15/15 train/validation/test split of each 10,000-row transistor dataset.

Outputs
  data/splits/<case>.npz   row indices (train, val, test) into data/transistor/<case>.csv

The split is a permutation drawn with numpy's default_rng seeded by [ml.split_seed, case index] (config/project.yaml).
Every later script (04 model comparison, 05d training, 05e test evaluation) reads these files, so all of them use the same rows.
Usage: python scripts/03_make_splits.py [--check]   (--check: only verify that the committed files are reproduced exactly)
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from dvdml.config import load_config  # noqa: E402
from dvdml.sampling import CASES  # noqa: E402


def make_split(n: int, cfg: dict, case: str):
    rng = np.random.default_rng([cfg["ml"]["split_seed"], CASES.index(case)])
    idx = rng.permutation(n)
    f = cfg["ml"]["split_fractions"]
    a, b = int(round(f[0] * n)), int(round((f[0] + f[1]) * n))
    return idx[:a], idx[a:b], idx[b:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="compare with the existing data/splits files instead of writing them")
    args = ap.parse_args()
    cfg = load_config()
    out = ROOT / "data" / "splits"
    out.mkdir(parents=True, exist_ok=True)
    ok = True
    for case in CASES:
        n = len(pd.read_csv(ROOT / "data" / "transistor" / f"{case}.csv"))
        tr, va, te = make_split(n, cfg, case)
        f = out / f"{case}.npz"
        if args.check:
            old = np.load(f)
            same = all(np.array_equal(old[k], v) for k, v in (("train", tr), ("val", va), ("test", te)))
            ok &= same
            print(f"{case}: {'identical' if same else 'DIFFERENT'} ({len(tr)}/{len(va)}/{len(te)})")
        else:
            np.savez(f, train=tr, val=va, test=te)
            print(f"{case}: train {len(tr)}, val {len(va)}, test {len(te)} -> {f.relative_to(ROOT)}")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
