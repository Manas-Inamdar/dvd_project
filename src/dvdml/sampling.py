"""Random sampling of the transistor datasets exactly as in assignment Section 4."""
import numpy as np
import pandas as pd

CASES = ("nmos_on", "nmos_off", "pmos_on", "pmos_off")
INPUT_COLUMNS = ["vdd", "temp", "w", "vd", "vs", "vg", "vb", "vth0", "toxe", "ndep", "u0", "xj"]


def device_type(case: str) -> str:
    return case.split("_")[0]


def gate_body_voltages(case: str, vdd: np.ndarray):
    """Gate/body voltage fixed by the case (assignment Section 4 table)."""
    zero = np.zeros_like(vdd)
    return {
        "nmos_on": (vdd, zero),
        "nmos_off": (zero, zero),
        "pmos_on": (zero, vdd),
        "pmos_off": (vdd, vdd),
    }[case]


def sample_process(rng, nominal: dict[str, float], n: int, tol: float) -> dict[str, np.ndarray]:
    """nominal * U(1-tol, 1+tol); multiplying keeps the sign of negative nominals (PMOS vth0)."""
    return {k: v * rng.uniform(1 - tol, 1 + tol, n) for k, v in nominal.items()}


def sample_case(case: str, n: int, seed: int, cfg: dict, nominal: dict[str, dict[str, float]], batch: int = 0) -> pd.DataFrame:
    """Draw n independent samples for one case. VDD is drawn first (Vd, Vs ranges depend on it).

    `batch` selects an independent deterministic stream (used to replace failed simulations)."""
    a = cfg["assignment"]
    rng = np.random.default_rng([seed, CASES.index(case), batch])
    vdd = a["vdd_nom"] * rng.uniform(1 - a["vdd_tol"], 1 + a["vdd_tol"], n)
    vd = rng.uniform(0.0, 1.0, n) * vdd
    vs = rng.uniform(0.0, 1.0, n) * vdd
    w = a["lmin"] * rng.uniform(a["w_min_mult"], a["w_max_mult"], n)
    temp = rng.uniform(a["temp_min"], a["temp_max"], n)
    proc = sample_process(rng, nominal[device_type(case)], n, a["process_tol"])
    vg, vb = gate_body_voltages(case, vdd)
    df = pd.DataFrame({"vdd": vdd, "temp": temp, "w": w, "vd": vd, "vs": vs, "vg": vg, "vb": vb, **proc})
    return df[INPUT_COLUMNS]
