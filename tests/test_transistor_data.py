"""Validate the generated transistor datasets (skipped if data/transistor/*.csv were not generated yet)."""
import json

import numpy as np
import pandas as pd
import pytest

from dvdml import modelcard
from dvdml.config import REPO_ROOT, load_config, model_path
from dvdml.sampling import CASES

CFG = load_config()
DATA = REPO_ROOT / "data" / "transistor"
NOM = modelcard.nominals(model_path(CFG).read_text(), CFG["assignment"]["process_params"])
pytestmark = pytest.mark.skipif(not all((DATA / f"{c}.csv").exists() for c in CASES), reason="datasets not generated")


@pytest.mark.parametrize("case", CASES)
def test_dataset_schema_and_ranges(case):
    d = pd.read_csv(DATA / f"{case}.csv")
    assert list(d.columns) == CFG["data"]["columns"]
    assert len(d) == CFG["data"]["n_samples"]
    assert np.isfinite(d.to_numpy()).all()
    assert d.vdd.between(0.9, 1.1).all()
    assert (d.vd.between(0, d.vdd)).all() and (d.vs.between(0, d.vdd)).all()
    assert d.w.between(22e-9, 176e-9).all() and d.temp.between(-40, 125).all()
    dev = case.split("_")[0]
    for p, nom in NOM[dev].items():
        assert (d[p] / nom).between(0.9, 1.1).all()
    zero = 0 * d.vdd
    exp_vg = {"nmos_on": d.vdd, "nmos_off": zero, "pmos_on": zero, "pmos_off": d.vdd}[case]
    exp_vb = {"nmos_on": zero, "nmos_off": zero, "pmos_on": d.vdd, "pmos_off": d.vdd}[case]
    assert np.allclose(d.vg, exp_vg) and np.allclose(d.vb, exp_vb)


@pytest.mark.parametrize("case", CASES)
def test_kirchhoff_where_currents_are_resolvable(case):
    d = pd.read_csv(DATA / f"{case}.csv")
    i = d[["id", "ig", "is", "ib"]].to_numpy()
    big = np.abs(i).max(axis=1) > 1e-12            # well above the ~1e-16 A numerical floor
    rel = np.abs(i.sum(axis=1))[big] / np.abs(i).max(axis=1)[big]
    assert big.sum() > 100 and np.percentile(rel, 95) < 1e-3


def test_generation_log_has_no_unexplained_gaps():
    log = json.loads((DATA / "generation_log.json").read_text())
    assert all(v["rows"] == log["n"] for v in log["cases"].values())
    assert "ngspice" in log["simulator"]
