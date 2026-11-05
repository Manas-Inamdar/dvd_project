import numpy as np
import pytest

from dvdml import modelcard
from dvdml.config import load_config, model_path
from dvdml.sampling import CASES, INPUT_COLUMNS, sample_case

CFG = load_config()
TEXT = model_path(CFG).read_text()
NOM = modelcard.nominals(TEXT, CFG["assignment"]["process_params"])


def test_nominals_match_model_file():
    assert NOM["nmos"]["vth0"] == pytest.approx(0.68858)
    assert NOM["pmos"]["vth0"] == pytest.approx(-0.63745)
    assert NOM["nmos"]["ndep"] == pytest.approx(5.5e18)
    assert NOM["pmos"]["u0"] == pytest.approx(0.011)
    assert NOM["nmos"]["xj"] == pytest.approx(7.2e-9)


@pytest.mark.parametrize("case", CASES)
def test_ranges_and_fixed_voltages(case):
    df = sample_case(case, 5000, 1, CFG, NOM)
    assert list(df.columns) == INPUT_COLUMNS and len(df) == 5000
    assert df.vdd.between(0.9, 1.1).all()
    assert (df.vd >= 0).all() and (df.vd <= df.vdd).all()
    assert (df.vs >= 0).all() and (df.vs <= df.vdd).all()
    assert df.w.between(22e-9, 176e-9).all()
    assert df.temp.between(-40, 125).all()
    dev = case.split("_")[0]
    for p, nom in NOM[dev].items():
        ratio = df[p] / nom
        assert ratio.between(0.9, 1.1).all() and ratio.max() > 1.09 and ratio.min() < 0.91
    zero = 0 * df.vdd
    exp_vg = {"nmos_on": df.vdd, "nmos_off": zero, "pmos_on": zero, "pmos_off": df.vdd}[case]
    exp_vb = {"nmos_on": zero, "nmos_off": zero, "pmos_on": df.vdd, "pmos_off": df.vdd}[case]
    assert np.allclose(df.vg, exp_vg) and np.allclose(df.vb, exp_vb)


def test_reproducible_and_independent_between_cases():
    a = sample_case("nmos_on", 100, 7, CFG, NOM)
    b = sample_case("nmos_on", 100, 7, CFG, NOM)
    c = sample_case("nmos_off", 100, 7, CFG, NOM)
    assert a.equals(b) and not np.allclose(a.vdd, c.vdd)
    assert not np.allclose(a.vd / a.vdd, a.vs / a.vdd)  # Vd and Vs independent
