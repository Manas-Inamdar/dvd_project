"""SPICE netlist builders (single transistor now; gates / circuit in later phases)."""
import pandas as pd

from . import modelcard
from .sampling import device_type


def _fmt(x: float) -> str:
    return f"{float(x):.9e}"


def single_transistor_netlist(case: str, row: pd.Series | dict, cfg: dict, model_text: str, title: str | None = None) -> str:
    """Self-contained ngspice netlist for ONE sample of one of the four single-FET cases.

    * every terminal has its own voltage source (assignment requirement)
    * model card of the device under test has vth0/toxe/ndep/u0/xj replaced by the sampled values
    * required .options line, junction areas AD = AS = W x Ldiff, one temperature per run
    * results are printed by a .control block: operating point, then i(Vd) i(Vg) i(Vs) i(Vb)
    """
    a, s = cfg["assignment"], cfg["spice"]
    dev = device_type(case)
    cards = modelcard.split_cards(model_text)
    dut = modelcard.set_params(cards[dev], {p: float(row[p]) for p in a["process_params"]})
    other = cards["pmos" if dev == "nmos" else "nmos"]
    w, lmin = float(row["w"]), a["lmin"]
    area = f" AD={_fmt(w * a['ldiff'])} AS={_fmt(w * a['ldiff'])}" if s["add_junction_areas"] else ""
    lines = [
        f"* {title or 'single transistor ' + case}",
        f".options {s['options']}",
        f".temp {_fmt(row['temp'])}",
        "",
        "* --- model cards (device under test has sampled process parameters) ---",
        dut,
        other,
        "* --- device: drain gate source body ---",
        f"M1 d g s b {dev} W={_fmt(w)} L={_fmt(lmin)}{area}",
        "* --- one voltage source per terminal ---",
        f"Vd d 0 dc {_fmt(row['vd'])}",
        f"Vg g 0 dc {_fmt(row['vg'])}",
        f"Vs s 0 dc {_fmt(row['vs'])}",
        f"Vb b 0 dc {_fmt(row['vb'])}",
        "",
        ".control",
        "set numdgt=10",
        "op",
        "print i(Vd) i(Vg) i(Vs) i(Vb)",
        ".endc",
        ".end",
        "",
    ]
    return "\n".join(lines)
