"""Static CMOS gate topologies (INV, NAND2, NOR2, AND2, OR2): one definition feeds BOTH the SPICE netlist and the ML prediction.

Widths are multiples of Lmin (decision D-012, report Appendix B): INV Wn=1 Wp=2; NAND2 Wn=2 Wp=2; NOR2 Wn=1 Wp=4.
Device terminals are (drain, gate, source, body) node names. Nodes: 'vdd', 'vss', inputs 'a','b', internal 'x' (NAND2 series NMOS node),
'y' (NOR2 series PMOS node), 'n' (output of the NAND2/NOR2 stage inside AND2/OR2), 'out'.

Leakage definition (D-011): total current delivered by all sources that sit at VDD (supply + inputs held high); by Kirchhoff this equals the
current absorbed by the sources at 0 V.
"""
from dataclasses import dataclass
import itertools

import pandas as pd

from . import modelcard
from .spice import _NUM

import re


@dataclass(frozen=True)
class Device:
    name: str
    kind: str          # 'nmos' / 'pmos'
    d: str
    g: str
    s: str
    b: str
    w_mult: float      # width in units of Lmin


def _inv(i, o, tag=""):
    return [Device(f"Mp_inv{tag}", "pmos", o, i, "vdd", "vdd", 2), Device(f"Mn_inv{tag}", "nmos", o, i, "vss", "vss", 1)]


def _nand2(o, x="x"):
    return [Device("Mp1", "pmos", o, "a", "vdd", "vdd", 2), Device("Mp2", "pmos", o, "b", "vdd", "vdd", 2),
            Device("Mn1", "nmos", o, "a", x, "vss", 2), Device("Mn2", "nmos", x, "b", "vss", "vss", 2)]


def _nor2(o, y="y"):
    return [Device("Mp1", "pmos", y, "a", "vdd", "vdd", 4), Device("Mp2", "pmos", o, "b", y, "vdd", 4),
            Device("Mn1", "nmos", o, "a", "vss", "vss", 1), Device("Mn2", "nmos", o, "b", "vss", "vss", 1)]


GATES = {
    "INV": {"inputs": ("a",), "devices": _inv("a", "out"), "record": (), "func": lambda a: 1 - a},
    "NAND2": {"inputs": ("a", "b"), "devices": _nand2("out"), "record": ("x",), "func": lambda a, b: 1 - (a & b)},
    "NOR2": {"inputs": ("a", "b"), "devices": _nor2("out"), "record": ("y",), "func": lambda a, b: 1 - (a | b)},
    "AND2": {"inputs": ("a", "b"), "devices": _nand2("n") + _inv("n", "out"), "record": ("x", "n"), "func": lambda a, b: a & b},
    "OR2": {"inputs": ("a", "b"), "devices": _nor2("n") + _inv("n", "out"), "record": ("y", "n"), "func": lambda a, b: a | b},
}


def input_combinations(gate: str):
    n = len(GATES[gate]["inputs"])
    return [bits for bits in itertools.product((0, 1), repeat=n)]


def case_name(gate: str, bits) -> str:
    return f"{gate}_{''.join(str(b) for b in bits)}"


def all_cases():
    return [(g, bits) for g in GATES for bits in input_combinations(g)]


def process_columns(prefix: str, params):
    return [f"{prefix}_{p}" for p in params]


def _nodeset_guess(gate: str, bits, vdd: float) -> dict[str, float]:
    """Initial guesses (logic levels / rough stack-node levels) for the DC solver. They only seed Newton's method (`.nodeset`), they do not
    constrain the converged operating point."""
    g = {"out": GATES[gate]["func"](*bits) * vdd}
    a = bits[0]
    b = bits[1] if len(bits) > 1 else 0
    if gate in ("AND2",):
        g["n"] = (1 - (a & b)) * vdd
    if gate in ("OR2",):
        g["n"] = (1 - (a | b)) * vdd
    if gate in ("NAND2", "AND2"):
        g["x"] = max(vdd - 0.4, 0.0) if (a == 1 and b == 0) else 0.05
    if gate in ("NOR2", "OR2"):
        g["y"] = vdd - 0.05 if a == 0 else 0.4
    return g


# Reference-solution tiers (D-028, D-031). Tier 0 = exactly the mandated options. Tier 1 APPENDS one extra .options line after the mandated
# one (the mandated line stays in the netlist): abstol at the numerical noise floor and tight reltol/vntol. Every run is solved at both tiers;
# tier 0 is the reference where it agrees with tier 1, otherwise tier 1 is (the mandated solve then is not a valid operating point).
FALLBACK_OPTIONS = [None, "abstol=1e-15 reltol=1e-9 vntol=1e-12"]


def gate_netlist(gate: str, bits, corner: pd.Series | dict, cfg: dict, model_text: str, title: str | None = None, fallback: int = 0) -> str:
    """Complete transistor-level ngspice netlist of one gate / input combination / corner.

    corner needs: vdd, temp, n_<param>, p_<param> for the five process parameters (all NMOS share the n_ draw, all PMOS the p_ draw).
    """
    a, s = cfg["assignment"], cfg["spice"]
    g = GATES[gate]
    cards = modelcard.split_cards(model_text)
    nmos = modelcard.set_params(cards["nmos"], {p: float(corner[f"n_{p}"]) for p in a["process_params"]})
    pmos = modelcard.set_params(cards["pmos"], {p: float(corner[f"p_{p}"]) for p in a["process_params"]})
    vdd = float(corner["vdd"])
    node = lambda n: n   # the ground rail is the node 'vss', tied to node 0 through a 0 V source (Vgnd) so the return current is measurable
    lines = [f"* {title or case_name(gate, bits)} - corner {int(corner['corner']) if 'corner' in corner else '?'}", f".options {s['options']}"]
    if FALLBACK_OPTIONS[fallback]:
        lines.append(f"* tight-tolerance cross-check solve (tier {fallback}): the mandated line above is kept, this later line overrides it")
        lines.append(f".options {FALLBACK_OPTIONS[fallback]}")
    lines += [f".temp {float(corner['temp']):.9e}", "", nmos, pmos, "* --- devices: drain gate source body ---"]
    for dv in g["devices"]:
        w = dv.w_mult * a["lmin"]
        area = f" AD={w * a['ldiff']:.9e} AS={w * a['ldiff']:.9e}" if s["add_junction_areas"] else ""
        lines.append(f"{dv.name} {node(dv.d)} {node(dv.g)} {node(dv.s)} {node(dv.b)} {dv.kind} W={w:.9e} L={a['lmin']:.9e}{area}")
    lines.append("* --- sources: supply, ground-rail current probe, inputs at exactly 0 or VDD ---")
    lines.append(f"Vdd vdd 0 dc {vdd:.9e}")
    lines.append("Vgnd vss 0 dc 0")
    for name, bit in zip(g["inputs"], bits):
        lines.append(f"V{name} {name} 0 dc {bit * vdd:.9e}")
    outs = ["v(out)"] + [f"v({r})" for r in g["record"]] + ["i(Vdd)", "i(Vgnd)"] + [f"i(V{n})" for n in g["inputs"]]
    ns = _nodeset_guess(gate, bits, vdd)
    lines.append("* --- solver start values only (do not constrain the result) ---")
    lines.append(".nodeset " + " ".join(f"v({k})={v:.6f}" for k, v in ns.items()))
    lines += ["", ".control", "set numdgt=12", "op", "print " + " ".join(outs), ".endc", ".end", ""]
    return "\n".join(lines)


_VAL_RE = re.compile(rf"^\s*([iv]\(\w+\))\s*=\s*({_NUM})\s*$", re.IGNORECASE | re.MULTILINE)


def parse_values(stdout: str) -> dict[str, float]:
    """All printed v(node)/i(source) values, lower-cased keys."""
    return {m.group(1).lower(): float(m.group(2)) for m in _VAL_RE.finditer(stdout)}


def leakage_from_values(vals: dict[str, float], gate: str, bits) -> float:
    """D-011: current delivered by all sources at VDD = -(I(Vdd) + sum of I(Vin) over inputs held high)."""
    tot = vals["i(vdd)"]
    for name, bit in zip(GATES[gate]["inputs"], bits):
        if bit:
            tot += vals[f"i(v{name})"]
    return -tot


def leakage_ground_side(vals: dict[str, float], gate: str, bits) -> float:
    """Same leakage measured as the current absorbed by the 0 V-level sources (ground rail + inputs held low); equals leakage_from_values."""
    tot = vals["i(vgnd)"]
    for name, bit in zip(GATES[gate]["inputs"], bits):
        if not bit:
            tot += vals[f"i(v{name})"]
    return tot


def node_voltages(gate: str, bits, vdd: float, vals: dict[str, float]) -> dict[str, float]:
    """Voltage of every node of the gate (rails, inputs, recorded internal nodes, output) for the ML terminal-voltage mapping."""
    g = GATES[gate]
    v = {"vdd": vdd, "vss": 0.0, "out": vals["v(out)"]}
    for name, bit in zip(g["inputs"], bits):
        v[name] = bit * vdd
    for r in g["record"]:
        v[r] = vals[f"v({r})"]
    return v
