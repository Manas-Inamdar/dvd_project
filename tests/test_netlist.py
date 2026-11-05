import re

import pytest

from dvdml import modelcard
from dvdml.config import load_config, model_path
from dvdml.netlist import single_transistor_netlist
from dvdml.sampling import CASES, sample_case
from dvdml.spice import parse_source_currents, terminal_currents

CFG = load_config()
TEXT = model_path(CFG).read_text()
NOM = modelcard.nominals(TEXT, CFG["assignment"]["process_params"])


def test_modelcard_override_only_touches_requested_params():
    cards = modelcard.split_cards(TEXT)
    new = modelcard.set_params(cards["nmos"], {"vth0": 0.7, "xj": 8e-9})
    assert modelcard.get_param(new, "vth0") == pytest.approx(0.7)
    assert modelcard.get_param(new, "xj") == pytest.approx(8e-9)
    for p in ("xjbvs", "xjbvd", "u0", "ua", "toxe", "toxp", "ndep", "nsd"):
        assert modelcard.get_param(new, p) == modelcard.get_param(cards["nmos"], p)
    assert len(new.splitlines()) == len(cards["nmos"].splitlines())


@pytest.mark.parametrize("case", CASES)
def test_netlist_requirements(case):
    row = sample_case(case, 3, 5, CFG, NOM).iloc[0]
    net = single_transistor_netlist(case, row, CFG, TEXT)
    assert ".options gmin=1e-18 abstol=1e-18 reltol=1e-6 vntol=1e-9" in net
    for src in ("Vd d 0", "Vg g 0", "Vs s 0", "Vb b 0"):  # own source per terminal
        assert src in net
    m = re.search(r"AD=(\S+) AS=(\S+)", net)
    assert float(m.group(1)) == pytest.approx(row.w * 44e-9)
    assert float(m.group(2)) == pytest.approx(row.w * 44e-9)
    dev = case.split("_")[0]
    assert f"M1 d g s b {dev} " in net
    assert net.count(".model") == 2
    dut_card = modelcard.split_cards(net)[dev]
    assert modelcard.get_param(dut_card, "vth0") == pytest.approx(row.vth0, rel=1e-8)


def test_parse_and_sign_convention():
    out = "i(vd) = -2.680000e-11\ni(vg) = 5.350000e-11\ni(vs) = -2.650000e-17\ni(vb) = 1.0e-18\n"
    cur = terminal_currents(parse_source_currents(out))
    assert cur["id"] == pytest.approx(2.68e-11) and cur["ig"] == pytest.approx(-5.35e-11)
