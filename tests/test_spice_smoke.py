"""Smoke tests that need a real ngspice (skipped if it cannot be found; set NGSPICE_EXE to its path).

They verify the things the whole project depends on: the netlist runs, the current sign convention
(D-006: positive INTO the device), Kirchhoff (id+ig+is+ib ~ 0) and basic physics of the four cases.
"""
import shutil

import pytest

from dvdml import modelcard
from dvdml.config import load_config, model_path
from dvdml.netlist import single_transistor_netlist
from dvdml.spice import ngspice_exe, parse_source_currents, run_netlist, terminal_currents

CFG = load_config()
EXE = ngspice_exe(CFG)
pytestmark = pytest.mark.skipif(shutil.which(EXE) is None, reason="ngspice not found (set NGSPICE_EXE)")

TEXT = model_path(CFG).read_text()
NOM = modelcard.nominals(TEXT, CFG["assignment"]["process_params"])


def _run(case, vd, vs, vdd=1.0, temp=27.0, w=44e-9):
    vg, vb = {"nmos_on": (vdd, 0), "nmos_off": (0, 0), "pmos_on": (0, vdd), "pmos_off": (vdd, vdd)}[case]
    row = {"temp": temp, "w": w, "vd": vd, "vs": vs, "vg": vg, "vb": vb, **NOM[case.split("_")[0]]}
    out = run_netlist(single_transistor_netlist(case, row, CFG, TEXT), CFG)
    src = parse_source_currents(out)
    assert set(src) == {"vd", "vg", "vs", "vb"}, out[-800:]
    return terminal_currents(src)


def test_nmos_on_conducts_into_drain_and_kirchhoff_holds():
    c = _run("nmos_on", vd=1.0, vs=0.0)
    assert c["id"] > 1e-6 and c["is"] < -1e-6          # current enters the drain, leaves the source
    assert abs(sum(c.values())) < 1e-3 * abs(c["id"])  # Kirchhoff


def test_nmos_off_leakage_is_tiny_but_positive_into_drain():
    c = _run("nmos_off", vd=1.0, vs=0.0)
    assert 0 < c["id"] < 1e-6


def test_pmos_on_conducts_with_source_at_high_voltage():
    c = _run("pmos_on", vd=0.0, vs=1.0)  # PMOS: source is the high side
    assert c["is"] > 1e-6 and c["id"] < -1e-6


def test_off_leakage_increases_with_temperature():
    cold = _run("nmos_off", 1.0, 0.0, temp=-40)["id"]
    hot = _run("nmos_off", 1.0, 0.0, temp=125)["id"]
    assert hot > 10 * cold
