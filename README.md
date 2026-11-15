# dvd_project - ML-driven PVT-variation-aware leakage estimation (Phase 7 pipeline)

Digital VLSI Design course project. It estimates the leakage current of CMOS gates and an 8-bit parity checker under process,
voltage and temperature (PVT) variation. Machine-learning models are trained on single-transistor SPICE data, and their
predictions are compared with full SPICE simulations.

This branch is a **cleaned copy of the Phase 7 pipeline** (from `feature/phase7-per-current-models`) and contains only the files
that pipeline uses. The original multi-output models, the reports, the documentation and the course material are on `main`.
The Phase 7 ablation study is on `feature/phase7-per-current-models`.

* **Technology:** PTM **22nm_LP** (BSIM4, `22nm_LP.pm`), nominal VDD **1 V**, L = 22 nm, W = 1-8 x Lmin. Simulator: **ngspice 47**.
* **Pipeline:**
  1. single-transistor SPICE data (4 cases: NMOS/PMOS x ON/OFF);
  2. 4 transistor models, each made of one MLP ensemble per terminal current (16 networks in total);
  3. 5 gates x 18 input cases x 200 PVT corners;
  4. 8-bit parity checker (28 NAND2), 256 vectors x 200 corners.
* **Results:**
  * Gate level: mean accuracy **99.65 %** (median error 0.19 %, P95 1.2 %).
  * Parity checker: mean accuracy **99.73 %** (median 0.19 %, P95 0.79 %).
  * Transistor test split: `results/models/test_results.csv`.
* **Model choice:** the MLP was chosen over LightGBM, kernel ridge and polynomial ridge in a validation study; see
  `results/model_comparison.md`.

## Layout
| Path | Content |
|---|---|
| `22nm_LP.pm` | assigned SPICE model card (NMOS + PMOS); path set in `config/project.yaml` |
| `config/project.yaml` | all assignment parameters and seeds |
| `src/dvdml/` | library: sampling, netlists, ngspice runner, gates, circuit, ML models (`ml_v2.py`, which reuses the features of `ml.py`), metrics |
| `scripts/` | numbered pipeline scripts, run in order (see below) |
| `data/transistor/` | the 4 x 10,000-row datasets (deliverable 1) |
| `data/transistor_extra/`, `data/transistor_edge/` | extra uniform rows (30,000 per case) and rail-corner rows (20,000 per case), training only |
| `data/splits/` | fixed-seed 70/15/15 train/validation/test row indices |
| `data/gates/`, `data/circuit/` | SPICE references: 200 corners, gate runs, parity-checker runs |
| `data/netlists/` | example netlists: single transistor, gates, parity checker (deliverable 2) |
| `models/` | the 4 transistor models (`<case>.joblib`), `manifest.json`, per-current metrics in `parts/*.json`, training logs |
| `results/` | `data_check/`, `models/` (transistor test metrics), `gates/`, `circuit/`, `model_comparison.md` |
| `tests/` | pytest suite (101 tests) |

## Setup (macOS, Linux, Windows)
Install [uv](https://docs.astral.sh/uv/) and ngspice 47:
* macOS: `brew install ngspice`
* Linux: use your package manager, or build ngspice 47
* Windows: official build; use `ngspice_con.exe`

```
uv sync                                   # creates .venv with Python 3.12 and the locked package versions (uv.lock)
export NGSPICE_EXE=ngspice                # macOS/Linux. Windows: set NGSPICE_EXE=C:\path\to\ngspice_con.exe
uv run python scripts/00_check_env.py     # prints package versions and the ngspice version
uv run pytest -q
```

## Run (in order)
```
uv run python scripts/01_generate_transistor_data.py   # 4 x 10,000 rows + single-transistor example netlists
uv run python scripts/01b_generate_extra_data.py       # 4 x 30,000 extra uniform rows (training only)
uv run python scripts/01c_generate_edge_data.py        # 4 x 20,000 rail-corner rows (training only)
uv run python scripts/02_data_check.py                 # Kirchhoff check, distributions, trend plots -> results/data_check/
# train the per-current models (resumable: finished parts in models/parts/ are skipped).
# The final models combine five runs with different settings:
uv run python -u scripts/05d_train_per_current.py --device cpu --cases nmos_on pmos_on   --currents ig    --params '{"wnorm": "weff", "edge_data": true}'
uv run python -u scripts/05d_train_per_current.py --device cpu --cases nmos_off pmos_off --currents id is --params '{"wnorm": "weff", "edge_data": true}'
uv run python -u scripts/05d_train_per_current.py --device cpu --cases nmos_on pmos_on   --currents id is --params '{"wnorm": "weff", "n_members": 1}'
uv run python -u scripts/05d_train_per_current.py --device cpu --currents ib
uv run python -u scripts/05d_train_per_current.py --device cpu --cases nmos_off pmos_off --currents ig    --params '{"n_members": 1}'
uv run python scripts/05e_evaluate_v2.py               # transistor test split + rail-corner errors -> results/models/
uv run python scripts/06_gate_spice.py                 # 200 corners x 18 gate cases (cross-checked SPICE reference)
uv run python scripts/07_gate_ml.py                    # gate-level ML vs SPICE -> results/gates/
uv run python scripts/08_circuit_spice.py              # parity checker, 51,200 SPICE runs (~30 min)
uv run python scripts/09_circuit_ml.py                 # circuit-level ML vs SPICE -> results/circuit/
```
`05e`, `07` and `09` only need the committed models and data; they run in about a minute and do not need torch or ngspice.
On a Windows `cmd` shell, write the `--params` JSON as `"{\"wnorm\": \"weff\", \"edge_data\": true}"`.

## Known issues (flagged, code unchanged)
* **`05d` defaults to `--device cuda`.** On machines without an NVIDIA GPU, pass `--device cpu` as above. Otherwise it stops
  with `Torch not compiled with CUDA enabled`. Full training took ~2.5 h on a laptop GPU; on CPU expect several hours.
* **The ngspice executable defaults to `ngspice_con`** (Windows name) in `config/project.yaml`. Set `NGSPICE_EXE` as shown above.
* **macOS: torch + LightGBM in one process hangs.** torch and scikit-learn each ship their own `libomp`. After torch has run,
  LightGBM fails with `OMP: System error #22` and the process hangs. In the test suite this hits
  `tests/test_ml.py::test_each_family_fits_and_predicts_a_toy_problem[lightgbm]` when the whole suite runs. The test passes on
  its own. LightGBM belongs to the model-comparison code in `ml.py` and is not used by the Phase 7 pipeline. On macOS run:
  `uv run pytest -q --deselect "tests/test_ml.py::test_each_family_fits_and_predicts_a_toy_problem[lightgbm]"`
* **`data/splits/` was created by `scripts/03_train_compare_models.py` on `main`** (function `make_split`, seed 20261105, 70/15/15),
  which is not part of this branch. The committed `.npz` files are what `05d`/`05e` read. To regenerate them, use that script from `main`.
* **Re-running on another OS gives tiny differences.** The committed data was made with the official Windows ngspice 47 build.
  When re-run on macOS (Homebrew ngspice 47):
  * `05e`/`07`/`09`: identical to ~1e-10 relative.
  * Transistor datasets (`01`): id and is are identical. Only currents within ~10x of the 1e-15 A noise floor differ.
  * Gate reference (`06`): leakage within 1e-3 relative (median 3e-6). The cross-check picks the other solve in 92 of 3,600 runs.
    Gate-level ML accuracy is unchanged at 99.65 %.
  * Parity checker (`08`, 2-corner subset): within 1e-5.
  * Committed text files use Windows line endings (CRLF).

## Notes
* Several points of the assignment are open; the team's assumptions are documented on `main` (`docs/PROJECT_CONTEXT.md`,
  `docs/DECISIONS.md`) and are **not confirmed by the course staff**. Examples: the gate-leakage definition, gate widths,
  Kirchhoff-consistent gate composition (D-030), extra and rail-corner training data (D-034, D-043), and the parity-checker
  architecture (D-035).
* Gate and circuit SPICE data is evaluation-only (never training data).
