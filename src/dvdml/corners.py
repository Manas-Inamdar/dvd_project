"""The 200 random PVT corners shared by the gate level (Part B) and the test circuit (Part C).

A corner = one draw of VDD, temperature and process parameters (Section 4 distributions). All NMOS in a gate/circuit share the n_* draw,
all PMOS the p_* draw. The same corner table (by index) is used for every gate, input combination and the circuit.
"""
import numpy as np
import pandas as pd


def make_corners(n: int, seed: int, cfg: dict, nominal: dict[str, dict[str, float]]) -> pd.DataFrame:
    a = cfg["assignment"]
    rng = np.random.default_rng([seed, 777])
    d = {"corner": np.arange(n)}
    d["vdd"] = a["vdd_nom"] * rng.uniform(1 - a["vdd_tol"], 1 + a["vdd_tol"], n)
    d["temp"] = rng.uniform(a["temp_min"], a["temp_max"], n)
    for prefix, dev in (("n", "nmos"), ("p", "pmos")):
        for p in a["process_params"]:
            d[f"{prefix}_{p}"] = nominal[dev][p] * rng.uniform(1 - a["process_tol"], 1 + a["process_tol"], n)
    return pd.DataFrame(d)
