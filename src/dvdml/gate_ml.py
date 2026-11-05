"""ML prediction of gate leakage from the four transistor models (assignment Part B step 4).

For every gate run (gate, inputs, corner) the SPICE-recorded node voltages give the terminal voltages (Vd, Vg, Vs, Vb) of every transistor.
Each transistor is routed to the ON or OFF model of its type by its gate voltage (D-029: NMOS ON if Vg > VDD/2, PMOS ON if Vg < VDD/2),
the model predicts (id, ig, is, ib) in A (positive INTO the device), and the gate leakage is the sum of the predicted currents flowing out of
the nodes held at VDD (supply rail and inputs at logic 1) -- the same definition as the SPICE side (D-011).
The ground-side sum (currents absorbed by the 0 V-level nodes) is returned as a second estimate; the difference between the two is the
Kirchhoff imbalance of the ML currents at the internal nodes.
"""
import numpy as np
import pandas as pd

from .gates import GATES, case_name, node_voltages

PROCESS = ["vth0", "toxe", "ndep", "u0", "xj"]


def transistor_rows(gate: str, bits, run: pd.Series, lmin: float) -> list[dict]:
    """One dict per transistor of this gate run with raw model inputs and the node level of each terminal."""
    vdd = float(run["vdd"])
    vals = {f"v({k})": float(run[f"v_{k}"]) for k in ("x", "y", "n") if f"v_{k}" in run and not pd.isna(run[f"v_{k}"])}
    vals["v(out)"] = float(run["v_out"])
    v = node_voltages(gate, bits, vdd, vals)
    inputs_high = {n for n, b in zip(GATES[gate]["inputs"], bits) if b}
    inputs_low = {n for n, b in zip(GATES[gate]["inputs"], bits) if not b}
    rows = []
    for dv in GATES[gate]["devices"]:
        level = lambda node: "hi" if node == "vdd" or node in inputs_high else ("lo" if node == "vss" or node in inputs_low else "int")
        pre = "n" if dv.kind == "nmos" else "p"
        r = {"device": dv.name, "kind": dv.kind, "vdd": vdd, "temp": float(run["temp"]), "w": dv.w_mult * lmin,
             "vd": v[dv.d], "vg": v[dv.g], "vs": v[dv.s], "vb": v[dv.b],
             "node_d": dv.d, "node_g": dv.g, "node_s": dv.s, "node_b": dv.b,
             "lvl_d": level(dv.d), "lvl_g": level(dv.g), "lvl_s": level(dv.s), "lvl_b": level(dv.b)}
        for p in PROCESS:
            r[p] = float(run[f"{pre}_{p}"])
        rows.append(r)
    return rows


def route(kind: str, vg: np.ndarray, vdd: np.ndarray) -> np.ndarray:
    """Model name per transistor from its gate voltage."""
    on = (vg > 0.5 * vdd) if kind == "nmos" else (vg < 0.5 * vdd)
    return np.where(on, f"{kind}_on", f"{kind}_off")


def predict_runs(runs: pd.DataFrame, corners: pd.DataFrame, models: dict, lmin: float) -> pd.DataFrame:
    """runs: SPICE result rows (data/gates/gate_spice.csv). Returns runs with leak_ml (supply side) and leak_ml_ground_side."""
    c = corners.set_index("corner")
    allrows = []
    for idx, run in runs.iterrows():
        gate = run["gate"]
        bits = tuple(int(ch) for ch in run["inputs"])
        full = pd.concat([run, c.loc[int(run["corner"]), [col for col in c.columns if col.startswith(("n_", "p_"))]]])
        for r in transistor_rows(gate, bits, full, lmin):
            r["run_index"] = idx
            allrows.append(r)
    t = pd.DataFrame(allrows)
    run_gate = runs["gate"].to_dict()
    t["model"] = ""
    for kind in ("nmos", "pmos"):
        m = t["kind"] == kind
        t.loc[m, "model"] = route(kind, t.loc[m, "vg"].to_numpy(), t.loc[m, "vdd"].to_numpy())
    for col in ("id", "ig", "is", "ib"):
        t[col] = np.nan
    for name, g in t.groupby("model"):
        pred = models[name].predict(g[["vdd", "temp", "w", "vd", "vs", "vg", "vb"] + PROCESS])
        t.loc[g.index, ["id", "ig", "is", "ib"]] = pred[["id", "ig", "is", "ib"]].to_numpy()
    t["on"] = t["model"].str.endswith("_on")
    terms = {"d": "id", "g": "ig", "s": "is", "b": "ib"}

    def rail_sums(df, id_, is_):
        cur = {"d": id_, "g": df["ig"].to_numpy(), "s": is_, "b": df["ib"].to_numpy()}
        sup = sum(np.where(df[f"lvl_{k}"] == "hi", cur[k], 0.0) for k in terms)     # current leaving a VDD-level node into a device terminal
        gnd = -sum(np.where(df[f"lvl_{k}"] == "lo", cur[k], 0.0) for k in terminals_keys)  # current entering a 0 V-level node
        return sup.sum(), gnd.sum()
    terminals_keys = list(terms)

    naive_sup, naive_gnd, kcl_sup, kcl_gnd, resid = {}, {}, {}, {}, {}
    for run_index, df in t.groupby("run_index"):
        df = df.reset_index(drop=True)
        naive_sup[run_index], naive_gnd[run_index] = rail_sums(df, df["id"].to_numpy(), df["is"].to_numpy())
        # --- KCL-consistent composition (D-030): ON-device channel current is an unknown J, is = -J - ig - ib ---
        on_idx = [i for i in df.index if df.loc[i, "on"]]
        col = {i: k for k, i in enumerate(on_idx)}
        id_base, is_base = df["id"].to_numpy().copy(), df["is"].to_numpy().copy()
        for i in on_idx:
            id_base[i] = 0.0
            is_base[i] = -df.loc[i, "ig"] - df.loc[i, "ib"]
        internal = sorted({n for r in df.itertuples() for n in (r.node_d, r.node_g, r.node_s, r.node_b)
                           if n not in ("vdd", "vss") and n not in GATES[run_gate[run_index]]["inputs"]})
        A = np.zeros((len(internal), max(len(on_idx), 1))); rhs = np.zeros(len(internal))
        for r_i, node in enumerate(internal):
            for i, r in enumerate(df.itertuples()):
                for k, (nn, base, sgn) in {"d": (r.node_d, id_base[i], +1), "g": (r.node_g, r.ig, 0), "s": (r.node_s, is_base[i], -1), "b": (r.node_b, r.ib, 0)}.items():
                    if nn == node:
                        rhs[r_i] -= base
                        if i in col and sgn:
                            A[r_i, col[i]] += sgn
        J = np.linalg.lstsq(A, rhs, rcond=None)[0] if on_idx else np.zeros(1)
        id_f, is_f = id_base.copy(), is_base.copy()
        for i in on_idx:
            id_f[i] += J[col[i]]
            is_f[i] -= J[col[i]]
        kcl_sup[run_index], kcl_gnd[run_index] = rail_sums(df, id_f, is_f)
    out = runs.copy()
    out["leak_ml_naive_supply"] = pd.Series(naive_sup).reindex(out.index)
    out["leak_ml_naive_ground"] = pd.Series(naive_gnd).reindex(out.index)
    out["leak_ml_supply_side"] = pd.Series(kcl_sup).reindex(out.index)
    out["leak_ml_ground_side"] = pd.Series(kcl_gnd).reindex(out.index)
    out["leak_ml"] = 0.5 * (out["leak_ml_supply_side"] + out["leak_ml_ground_side"])   # D-030: mean of the two (a-priori) unbiased estimates
    return out, t
