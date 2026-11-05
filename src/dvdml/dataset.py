"""Simulate sampled transistors in parallel and build a dataset with exactly N valid rows.

Failure handling (plan task 1.5): a sample whose ngspice run fails, times out, prints no currents or prints
non-finite values is dropped and replaced by a fresh sample from the next deterministic batch, so a dataset always
has exactly N valid rows and is reproducible from (seed, case).
"""
from concurrent.futures import ThreadPoolExecutor
import math
import os

import numpy as np
import pandas as pd

from .netlist import single_transistor_netlist
from .sampling import sample_case
from .spice import parse_source_currents, run_netlist, terminal_currents

CURRENTS = ["id", "ig", "is", "ib"]


def simulate_row(case: str, row: pd.Series, cfg: dict, model_text: str) -> dict | None:
    """Terminal currents (into the device) for one sample, or None if the simulation failed."""
    try:
        out = run_netlist(single_transistor_netlist(case, row, cfg, model_text), cfg)
        src = parse_source_currents(out)
        if set(src) != {"vd", "vg", "vs", "vb"}:
            return None
        cur = terminal_currents(src)
    except (RuntimeError, OSError):
        return None
    return cur if all(math.isfinite(v) for v in cur.values()) else None


def simulate_samples(case: str, samples: pd.DataFrame, cfg: dict, model_text: str, workers: int | None = None) -> pd.DataFrame:
    """Return samples with id/ig/is/ib columns appended, failed rows removed (index preserved)."""
    workers = workers or max(1, (os.cpu_count() or 2) - 2)
    rows = [r for _, r in samples.iterrows()]
    with ThreadPoolExecutor(max_workers=workers) as ex:  # threads are fine: the work is in ngspice subprocesses
        results = list(ex.map(lambda r: simulate_row(case, r, cfg, model_text), rows))
    ok = [i for i, r in enumerate(results) if r is not None]
    out = samples.iloc[ok].copy()
    for c in CURRENTS:
        out[c] = [results[i][c] for i in ok]
    return out


def generate_case(case: str, n: int, cfg: dict, nominal: dict, model_text: str, workers: int | None = None,
                  simulate=simulate_samples, max_batches: int = 20) -> tuple[pd.DataFrame, int]:
    """Exactly n valid rows for one case. Returns (dataframe in cfg column order, number of failed simulations)."""
    seed = cfg["data"]["seed"]
    parts, have, failed = [], 0, 0
    for batch in range(max_batches):
        need = n - have
        if need <= 0:
            break
        draw = sample_case(case, need, seed, cfg, nominal, batch=batch)
        done = simulate(case, draw, cfg, model_text, workers)
        failed += len(draw) - len(done)
        parts.append(done)
        have += len(done)
    if have < n:
        raise RuntimeError(f"{case}: only {have}/{n} valid samples after {max_batches} batches")
    df = pd.concat(parts, ignore_index=True).iloc[:n]
    return df[cfg["data"]["columns"]], failed
