"""Enlarged-training-set extension (A4): extra rows are valid, independent of the specified dataset, and validation/test rows are untouched."""
import numpy as np
import pandas as pd
import pytest

from dvdml import modelcard
from dvdml.config import REPO_ROOT, load_config, model_path
from dvdml.sampling import CASES

CFG = load_config()
EXTRA = REPO_ROOT / "data" / "transistor_extra"
NOM = modelcard.nominals(model_path(CFG).read_text(), CFG["assignment"]["process_params"])
pytestmark = pytest.mark.skipif(not all((EXTRA / f"{c}.csv.gz").exists() for c in CASES), reason="extra data not generated")


@pytest.mark.parametrize("case", CASES)
def test_extra_rows_are_valid_and_disjoint_from_the_specified_dataset(case):
    ex = pd.read_csv(EXTRA / f"{case}.csv.gz")
    base = pd.read_csv(REPO_ROOT / "data" / "transistor" / f"{case}.csv")
    assert list(ex.columns) == CFG["data"]["columns"] and len(ex) >= 29000
    assert np.isfinite(ex.to_numpy()).all()
    assert ex.vdd.between(0.9, 1.1).all() and ex.w.between(22e-9, 176e-9).all() and ex.temp.between(-40, 125).all()
    dev = case.split("_")[0]
    for p, nom in NOM[dev].items():
        assert (ex[p] / nom).between(0.9, 1.1).all()
    assert not set(ex.vdd.round(12)) & set(base.vdd.round(12))      # independent random stream: no sample is shared with the specified dataset
