import numpy as np
import pytest

from dvdml import dataset, modelcard
from dvdml.config import load_config, model_path

CFG = load_config()
TEXT = model_path(CFG).read_text()
NOM = modelcard.nominals(TEXT, CFG["assignment"]["process_params"])


def fake_simulate_with_failures(case, samples, cfg, text, workers=None):
    """Pretend ~25 % of samples fail (decided by sample content); currents are a deterministic function of the sample."""
    keep = (samples["vd"].to_numpy() * 1e9).astype(np.int64) % 4 != 0
    out = samples[keep].copy()
    for c in dataset.CURRENTS:
        out[c] = out["vd"] * 1e-9
    return out


def test_generate_case_returns_exactly_n_valid_rows_and_counts_failures():
    df, failed = dataset.generate_case("nmos_off", 200, CFG, NOM, TEXT, simulate=fake_simulate_with_failures)
    assert len(df) == 200 and failed > 0
    assert list(df.columns) == CFG["data"]["columns"]
    assert df["vd"].is_unique  # replacements come from fresh batches, no duplicated samples


def test_generate_case_is_reproducible():
    a, _ = dataset.generate_case("pmos_on", 100, CFG, NOM, TEXT, simulate=fake_simulate_with_failures)
    b, _ = dataset.generate_case("pmos_on", 100, CFG, NOM, TEXT, simulate=fake_simulate_with_failures)
    assert a.equals(b)


def test_generate_case_gives_up_if_everything_fails():
    never = lambda case, s, cfg, t, w=None: s.iloc[0:0].assign(id=[], ig=[], **{"is": [], "ib": []})
    with pytest.raises(RuntimeError):
        dataset.generate_case("nmos_on", 10, CFG, NOM, TEXT, simulate=never, max_batches=3)
