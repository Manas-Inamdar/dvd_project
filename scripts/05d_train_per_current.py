"""Phase 7 (D-041): train the per-current transistor models (src/dvdml/ml_v2.py). Resumable: every finished (case, current) model is saved at once.

Data (TRANSISTOR data only; gate/circuit SPICE data is never touched here):
  train   = original 70 % train split of the 10,000-row dataset + extra rows 0..24,999 (data/transistor_extra, same uniform distribution)
  val     = original 15 % validation split   (early stopping, L-BFGS acceptance)
  holdout = extra rows 25,000..29,999        (never trained on; used to measure the error at the rail corners of the (Vd, Vs) box)
  test    = original 15 % test split         (evaluated once, by scripts/05e_evaluate_v2.py)
  with params {"edge_data": true} (D-043) additionally: rail-corner rows of data/transistor_edge (scripts/01c):
    rows 0..15,999 -> train, 16,000..17,999 -> val, 18,000..19,999 -> "edge_holdout" (reported only)

Outputs (in --out, default models/):
  parts/<case>__<current>.joblib    one CurrentModel per current
  parts/<case>__<current>.json      validation / holdout / rail-corner errors of that current
  <case>.joblib                     CompositeTransistorModel (assembled when all four currents of the case exist)
Usage: python -u scripts/05d_train_per_current.py [--cases nmos_on ...] [--currents ig ...] [--params '{"epochs": 1500}'] [--out models]
"""
import argparse
import json
import os
os.environ.setdefault("OMP_NUM_THREADS", "4")      # low-load mode: cap BLAS/OpenMP threads before numpy/torch load
os.environ.setdefault("MKL_NUM_THREADS", "4")
import sys
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from dvdml.metrics import CURRENTS, I_FLOOR  # noqa: E402
from dvdml.ml_v2 import MODES, CompositeTransistorModel, CurrentModel  # noqa: E402
from dvdml.sampling import CASES  # noqa: E402

N_EXTRA_TRAIN = 25000
N_EDGE_TRAIN, N_EDGE_VAL = 16000, 2000
DEFAULT_PARAMS = {"width": 128, "depth": 4, "epochs": 1500, "batch": 512, "lr": 3e-3, "edge": 4.0, "feat": True, "wnorm": True,
                  "n_members": 3, "polish_rounds": 6, "polish_iter": 300, "seed": 0, "threads": 4, "adam_fp32": True,
                  "edge_data": False}


def load_case(case):
    df = pd.read_csv(ROOT / "data" / "transistor" / f"{case}.csv")
    sp = np.load(ROOT / "data" / "splits" / f"{case}.npz")
    ex = pd.read_csv(ROOT / "data" / "transistor_extra" / f"{case}.csv.gz")
    train = pd.concat([df.iloc[sp["train"]], ex.iloc[:N_EXTRA_TRAIN]], ignore_index=True)
    return train, df.iloc[sp["val"]].reset_index(drop=True), ex.iloc[N_EXTRA_TRAIN:].reset_index(drop=True), df.iloc[sp["test"]].reset_index(drop=True)


def load_edge(case):
    """Rail-corner transistor rows (scripts/01c, D-043) split into (train, val, holdout); None if not generated."""
    f = ROOT / "data" / "transistor_edge" / f"{case}.csv.gz"
    if not f.exists():
        return None
    e = pd.read_csv(f)
    a, b = N_EDGE_TRAIN, N_EDGE_TRAIN + N_EDGE_VAL
    return e.iloc[:a].reset_index(drop=True), e.iloc[a:b].reset_index(drop=True), e.iloc[b:].reset_index(drop=True)


def regions(d):
    rd, rs = d.vd / d.vdd, d.vs / d.vdd
    return {"all": np.ones(len(d), bool), "vd,vs<0.1": (rd < .1) & (rs < .1), "vd,vs>0.9": (rd > .9) & (rs > .9),
            "vs<0.1,vd>0.9": (rs < .1) & (rd > .9), "vs>0.9,vd<0.1": (rs > .9) & (rd < .1),
            "vd,vs exactly at rails": ((rd < 1e-9) | (rd > 1 - 1e-9)) & ((rs < 1e-9) | (rs > 1 - 1e-9))}


def errors(pred, d, cur):
    out = {}
    t = d[cur].to_numpy(float)
    for name, m in regions(d).items():
        m = np.asarray(m) & (np.abs(t) > I_FLOOR)
        if m.sum() == 0:
            out[name] = {"n": 0}
            continue
        e = (pred[m] - t[m]) / np.abs(t[m])
        out[name] = {"n": int(m.sum()), "median": float(np.median(np.abs(e))), "mean": float(np.mean(np.abs(e))),
                     "p95": float(np.percentile(np.abs(e), 95)), "bias": float(e.mean())}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", nargs="*", default=list(CASES))
    ap.add_argument("--currents", nargs="*", default=list(CURRENTS))
    ap.add_argument("--params", default="{}", help="JSON overrides of DEFAULT_PARAMS")
    ap.add_argument("--out", default="models")
    ap.add_argument("--device", default="auto", help="cuda, cpu, or auto (cuda if available)")
    args = ap.parse_args()
    if args.device == "auto":
        import torch
        args.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"device: {args.device}", flush=True)
    params = {**DEFAULT_PARAMS, **json.loads(args.params)}
    out = ROOT / args.out
    (out / "parts").mkdir(parents=True, exist_ok=True)
    (out / "params.json").write_text(json.dumps(params, indent=2))
    for case in args.cases:
        train, val, hold, _ = load_case(case)
        edge = load_edge(case)
        if params["edge_data"]:
            if edge is None:
                raise SystemExit(f"{case}: edge_data requested but data/transistor_edge/{case}.csv.gz is missing (run scripts/01c)")
            train = pd.concat([train, edge[0]], ignore_index=True)
            val = pd.concat([val, edge[1]], ignore_index=True)
        for cur in args.currents:
            f = out / "parts" / f"{case}__{cur}.joblib"
            if f.exists():
                print(f"{case} {cur}: exists, skipped", flush=True)
                continue
            t0 = time.time()
            print(f"{case} {cur}: mode={MODES[case][cur]} training ...", flush=True)
            m = CurrentModel(cur, MODES[case][cur], params).fit(train, val, device=args.device, verbose=True)
            ev = {"case": case, "current": cur, "mode": m.mode, "params": params, "seconds": round(time.time() - t0, 1),
                  "val": errors(m.predict(val), val, cur), "holdout": errors(m.predict(hold), hold, cur)}
            if edge is not None:
                ev["edge_holdout"] = errors(m.predict(edge[2]), edge[2], cur)
            joblib.dump(m, f)
            (out / "parts" / f"{case}__{cur}.json").write_text(json.dumps(ev, indent=2))
            h = ev["holdout"]
            print(f"{case} {cur}: done in {ev['seconds'] / 60:.1f} min | holdout all median {h['all'].get('median', float('nan')):.4f} "
                  + " | ".join(f"{k} med {v['median']:.4f} mean {v['mean']:.4f} bias {v['bias']:+.4f}" for k, v in h.items() if k != "all" and v["n"] > 20),
                  flush=True)
        if all((out / "parts" / f"{case}__{c}.joblib").exists() for c in CURRENTS):
            comp = CompositeTransistorModel(case, {c: joblib.load(out / "parts" / f"{case}__{c}.joblib") for c in CURRENTS})
            joblib.dump(comp, out / f"{case}.joblib")
            print(f"{case}: composite model written", flush=True)


if __name__ == "__main__":
    main()
