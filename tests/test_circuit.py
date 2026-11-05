import itertools
import shutil

import pandas as pd
import pytest

from dvdml import circuit, modelcard
from dvdml.config import load_config, model_path
from dvdml.corners import make_corners
from dvdml.refsolve import solve_with_crosscheck
from dvdml.spice import ngspice_exe, run_netlist

CFG = load_config()
TEXT = model_path(CFG).read_text()
NOM = modelcard.nominals(TEXT, CFG["assignment"]["process_params"])
CORNERS = make_corners(3, 1, CFG, NOM)
needs_spice = pytest.mark.skipif(shutil.which(ngspice_exe(CFG)) is None, reason="ngspice not found")


def test_structure_28_nand_gates_112_transistors():
    assert len(circuit.INSTANCES) == 28
    net = circuit.circuit_netlist((0,) * 8, CORNERS.iloc[0], CFG, TEXT)
    dev = [ln for ln in net.splitlines() if ln.startswith("M_")]
    assert len(dev) == 112 and all(" AD=" in ln for ln in dev)
    assert ".options gmin=1e-18 abstol=1e-18 reltol=1e-6 vntol=1e-9" in net and net.count(".model") == 2


def test_logic_is_parity_for_all_256_vectors():
    for bits in itertools.product((0, 1), repeat=8):
        assert circuit.logic_values(bits)[circuit.OUTPUT] == circuit.parity(bits)


def test_instance_cases_are_part_b_cases():
    cases = circuit.instance_cases((1, 0, 1, 1, 0, 0, 1, 0))
    assert len(cases) == 28 and {c for _, c in cases} <= {"NAND2_00", "NAND2_01", "NAND2_10", "NAND2_11"}


@needs_spice
@pytest.mark.parametrize("bits", [(0,) * 8, (1,) + (0,) * 7, (1, 1, 0, 1, 0, 0, 1, 0), (1,) * 8])
def test_spice_output_is_parity_and_kirchhoff_holds(bits):
    c = CORNERS.iloc[0]
    v, src, d = solve_with_crosscheck(lambda t: circuit.circuit_netlist(bits, c, CFG, TEXT, fallback=t), run_netlist, circuit.parse_values,
                                      lambda x: circuit.leakage_from_values(x, bits), CFG)
    assert v is not None
    assert abs(v["v(out)"] - circuit.parity(bits) * c.vdd) < 0.02 * c.vdd
    leak = circuit.leakage_from_values(v, bits)
    assert leak > 0 and abs(circuit.leakage_ground_side(v, bits) - leak) < 2e-3 * leak + 1e-15
