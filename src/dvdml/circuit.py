"""8-bit parity checker: output = XOR of the eight inputs (1 when an odd number of inputs is 1).

Architecture (D-035): a balanced tree of seven XOR2 cells; each XOR2 is four NAND2 gates (the classic 4-NAND XOR):
    n1 = NAND(a, b);  n2 = NAND(a, n1);  n3 = NAND(b, n1);  y = NAND(n2, n3)
=> 28 NAND2 gates, 112 transistors. Every gate is the NAND2 of Part B (same topology and widths, gates.GATES['NAND2']), so the circuit-level ML
prediction is composed from the gate-level models exactly as the assignment describes.

Leakage definition = gate level (D-011): total current delivered by all sources at VDD (supply + primary inputs held high) = current absorbed at 0 V.
"""
from dataclasses import dataclass

import pandas as pd

from . import modelcard
from .gates import FALLBACK_OPTIONS, GATES, parse_values  # noqa: F401  (parse_values re-exported for the scripts)

N_INPUTS = 8


@dataclass(frozen=True)
class Instance:
    name: str
    a: str
    b: str
    out: str


def _xor(a: str, b: str, y: str, tag: str) -> list[Instance]:
    n1, n2, n3 = f"{tag}_n1", f"{tag}_n2", f"{tag}_n3"
    return [Instance(f"{tag}_g1", a, b, n1), Instance(f"{tag}_g2", a, n1, n2), Instance(f"{tag}_g3", b, n1, n3), Instance(f"{tag}_g4", n2, n3, y)]


def build_parity8() -> list[Instance]:
    ins = [f"i{k}" for k in range(N_INPUTS)]
    inst = []
    for k in range(4):
        inst += _xor(ins[2 * k], ins[2 * k + 1], f"s1_{k}", f"x1_{k}")
    inst += _xor("s1_0", "s1_1", "s2_0", "x2_0") + _xor("s1_2", "s1_3", "s2_1", "x2_1")
    inst += _xor("s2_0", "s2_1", "out", "x3_0")
    return inst


INSTANCES = build_parity8()
OUTPUT = "out"


def logic_values(bits) -> dict[str, int]:
    """Logic value of every node for an input vector (bits[k] = value of i<k>)."""
    v = {f"i{k}": int(b) for k, b in enumerate(bits)}
    for g in INSTANCES:
        v[g.out] = 1 - (v[g.a] & v[g.b])
    return v


def parity(bits) -> int:
    return sum(int(b) for b in bits) % 2


def instance_cases(bits) -> list[tuple[Instance, str]]:
    """For every NAND2 instance the Part-B case name ('NAND2_ab') that applies for this input vector."""
    v = logic_values(bits)
    return [(g, f"NAND2_{v[g.a]}{v[g.b]}") for g in INSTANCES]


def _x_guess(a: int, b: int, vdd: float) -> float:
    return max(vdd - 0.4, 0.0) if (a == 1 and b == 0) else 0.05


def circuit_netlist(bits, corner: pd.Series | dict, cfg: dict, model_text: str, fallback: int = 0, title: str | None = None) -> str:
    """Complete transistor-level ngspice netlist of the parity checker for one input vector and one corner."""
    a_cfg, s = cfg["assignment"], cfg["spice"]
    cards = modelcard.split_cards(model_text)
    nmos = modelcard.set_params(cards["nmos"], {p: float(corner[f"n_{p}"]) for p in a_cfg["process_params"]})
    pmos = modelcard.set_params(cards["pmos"], {p: float(corner[f"p_{p}"]) for p in a_cfg["process_params"]})
    vdd = float(corner["vdd"])
    lines = [f"* {title or 'parity8 ' + ''.join(map(str, bits))} - corner {int(corner['corner']) if 'corner' in corner else '?'}", f".options {s['options']}"]
    if FALLBACK_OPTIONS[fallback]:
        lines += [f"* tight-tolerance cross-check solve (tier {fallback}): the mandated line above is kept, this later line overrides it", f".options {FALLBACK_OPTIONS[fallback]}"]
    lines += [f".temp {float(corner['temp']):.9e}", "", nmos, pmos, "* --- 28 NAND2 gates (4 transistors each): drain gate source body ---"]
    for g in INSTANCES:
        node = {"a": g.a, "b": g.b, "out": g.out, "x": f"{g.name}_x", "vdd": "vdd", "vss": "vss"}
        for dv in GATES["NAND2"]["devices"]:
            w = dv.w_mult * a_cfg["lmin"]
            area = f" AD={w * a_cfg['ldiff']:.9e} AS={w * a_cfg['ldiff']:.9e}" if s["add_junction_areas"] else ""
            lines.append(f"M_{g.name}_{dv.name} {node[dv.d]} {node[dv.g]} {node[dv.s]} {node[dv.b]} {dv.kind} W={w:.9e} L={a_cfg['lmin']:.9e}{area}")
    lines += ["* --- sources: supply, ground-rail current probe, primary inputs at exactly 0 or VDD ---", f"Vdd vdd 0 dc {vdd:.9e}", "Vgnd vss 0 dc 0"]
    for k, b in enumerate(bits):
        lines.append(f"Vi{k} i{k} 0 dc {int(b) * vdd:.9e}")
    v = logic_values(bits)
    ns = [f"v({g.out})={v[g.out] * vdd:.6f}" for g in INSTANCES] + [f"v({g.name}_x)={_x_guess(v[g.a], v[g.b], vdd):.6f}" for g in INSTANCES]
    lines += ["* --- solver start values only (do not constrain the result) ---", ".nodeset " + " ".join(ns), "",
              ".control", "set numdgt=12", "op", "print v(out) i(Vdd) i(Vgnd) " + " ".join(f"i(Vi{k})" for k in range(N_INPUTS)), ".endc", ".end", ""]
    return "\n".join(lines)


def leakage_from_values(vals: dict[str, float], bits) -> float:
    """Current delivered by all sources at VDD (supply + inputs held high)."""
    tot = vals["i(vdd)"] + sum(vals[f"i(vi{k})"] for k, b in enumerate(bits) if int(b))
    return -tot


def leakage_ground_side(vals: dict[str, float], bits) -> float:
    return vals["i(vgnd)"] + sum(vals[f"i(vi{k})"] for k, b in enumerate(bits) if not int(b))
