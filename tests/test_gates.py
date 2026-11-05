import shutil

import pandas as pd
import pytest

from dvdml import gates, modelcard
from dvdml.config import load_config, model_path
from dvdml.corners import make_corners
from dvdml.spice import ngspice_exe, run_netlist

CFG = load_config()
TEXT = model_path(CFG).read_text()
NOM = modelcard.nominals(TEXT, CFG["assignment"]["process_params"])
CORNERS = make_corners(5, 1, CFG, NOM)
needs_spice = pytest.mark.skipif(shutil.which(ngspice_exe(CFG)) is None, reason="ngspice not found")


def test_there_are_18_cases():
    assert len(gates.all_cases()) == 18


def test_corners_are_reproducible_and_within_ranges():
    a, b = make_corners(200, 3, CFG, NOM), make_corners(200, 3, CFG, NOM)
    assert a.equals(b) and a.vdd.between(0.9, 1.1).all() and a.temp.between(-40, 125).all()
    assert (a["n_vth0"] / NOM["nmos"]["vth0"]).between(0.9, 1.1).all() and (a["p_vth0"] / NOM["pmos"]["vth0"]).between(0.9, 1.1).all()
    assert not (a["n_vth0"] / NOM["nmos"]["vth0"]).equals(a["p_vth0"] / NOM["pmos"]["vth0"])  # NMOS and PMOS draws differ


@pytest.mark.parametrize("gate,bits", gates.all_cases())
def test_netlist_requirements(gate, bits):
    net = gates.gate_netlist(gate, bits, CORNERS.iloc[0], CFG, TEXT)
    assert ".options gmin=1e-18 abstol=1e-18 reltol=1e-6 vntol=1e-9" in net
    n_dev = len(gates.GATES[gate]["devices"])
    dev_lines = [ln for ln in net.splitlines() if ln.startswith("M")]
    assert len(dev_lines) == n_dev and all(" AD=" in ln and " AS=" in ln for ln in dev_lines)
    # the NMOS (PMOS) transistors of one gate share a single process draw: only one nmos and one pmos .model card
    assert net.count(".model") == 2


@needs_spice
@pytest.mark.parametrize("gate,bits", gates.all_cases())
def test_logic_function_leakage_and_kcl_in_spice(gate, bits):
    c = CORNERS.iloc[0]
    vals = gates.parse_values(run_netlist(gates.gate_netlist(gate, bits, c, CFG, TEXT), CFG))
    expect = gates.GATES[gate]["func"](*bits)
    assert abs(vals["v(out)"] - expect * c.vdd) < 0.02 * c.vdd              # static CMOS output is at a rail
    assert gates.leakage_from_values(vals, gate, bits) > 0
    srcs = [vals["i(vdd)"], vals["i(vgnd)"]] + [vals[f"i(v{n})"] for n in gates.GATES[gate]["inputs"]]
    assert abs(sum(srcs)) < 1e-3 * max(abs(s) for s in srcs) + 1e-15        # Kirchhoff: all source currents sum to zero
    leak = gates.leakage_from_values(vals, gate, bits)
    assert abs(gates.leakage_ground_side(vals, gate, bits) - leak) < 1e-3 * leak + 1e-15   # delivered at VDD level == absorbed at 0 V level
