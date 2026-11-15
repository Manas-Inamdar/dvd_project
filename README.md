# ML-Driven PVT Variation Aware Leakage Estimation

Digital VLSI Design course project. **Team 26, Return of LUZAAZ:** Manas Inamdar, Soham Jahagirdar, Sai Rithvik Achutuni, Gautam Gandhi.

The project estimates the leakage current of CMOS circuits under process, voltage and temperature (PVT) variation with machine learning instead of
full SPICE simulation:

1. **Transistor models:** one ML model per case (NMOS ON, NMOS OFF, PMOS ON, PMOS OFF) predicts the four terminal currents (Id, Ig, Is, Ib).
   It is trained on single-transistor SPICE data.
2. **Gates:** using only these four models, the leakage of INV, NAND2, NOR2, AND2 and OR2 is predicted. This covers 18 input cases at 200 PVT
   corners, and each prediction is compared with SPICE.
3. **Test circuit:** an 8-bit parity checker (28 NAND2 gates) is composed from the gate models. All 256 input vectors are evaluated at the same
   200 corners and compared with SPICE of the full netlist.

**Report:** [`report/report.pdf`](report/report.pdf).

## Assignment

| Item | Value |
|---|---|
| Model file | PTM `22nm_LP.pm` (BSIM4), NMOS and PMOS |
| Nominal VDD | 1 V (sampled 0.9 to 1.1 V) |
| Channel length, widths | L = 22 nm; W = 1 to 8 x Lmin |
| Test circuit | 8-bit parity checker |
| Simulator | ngspice-47 |

## Results

| Level | Runs | Mean accuracy | Median error | P95 error | Max error |
|---|---|---|---|---|---|
| Gates (18 cases x 200 corners) | 3,600 | **99.65 %** | 0.19 % | 1.20 % | 5.7 % |
| 8-bit parity checker (256 vectors x 200 corners) | 51,200 | **99.73 %** | 0.19 % | 0.79 % | 1.6 % |

* **Model choice:** four model types were compared on the validation sets (MLP, LightGBM, kernel ridge, polynomial ridge). The MLP was the most
  accurate in every case.
* **Final transistor models:** an MLP ensemble for each terminal current, with targets normalised by the effective width. Training uses extra data
  at the rail corners, where gates operate.
* **Gate leakage:** the predicted transistor currents are composed into gate leakage in a way that satisfies Kirchhoff's current law at every
  internal node. A plain sum of the currents is off by orders of magnitude.

## Deliverables

| # | Deliverable | Location |
|---|---|---|
| 1 | Datasets: 4 CSV files, 10,000 rows each | `data/transistor/{nmos_on,nmos_off,pmos_on,pmos_off}.csv` |
| 2 | Example netlists: single transistor (4), gates (18), test circuit (4 vectors) | `data/netlists/` |
| 3 | Data check: Kirchhoff check and three trend plots | `results/data_check/` |
| 4 | Model comparison table: 4 model types x 4 cases (validation) | `results/model_comparison/` |
| 5 | Chosen models: test errors, predicted-vs-SPICE plots, 4 model files | `models/*.joblib`, `results/models/` |
| 6 | Gate results table (18 cases) | `results/gates/gate_results.csv` |
| 7 | Gate parity plot (log axes) | `results/gates/gate_parity.png` |
| 8 | Test-circuit results and parity plot | `results/circuit/` |
| 9 | Code (scripts run in order, fixed seeds) | `scripts/`, `src/dvdml/` |
| 10 | Report | `report/report.pdf` |

## Repository layout

| Path | Content |
|---|---|
| `22nm_LP.pm` | Assigned SPICE model card |
| `config/project.yaml` | All assignment parameters, solver options and seeds |
| `src/dvdml/` | Library: sampling, netlists, ngspice runner, gates, circuit, ML models (`ml.py` for the comparison, `ml_v2.py` for the final models), metrics |
| `scripts/` | Numbered pipeline scripts (see below) |
| `data/transistor/` | The four 10,000-row datasets |
| `data/transistor_extra/`, `data/transistor_edge/` | Training-only data: 30,000 extra uniform rows and 20,000 rail-corner rows per case |
| `data/splits/` | Fixed-seed 70/15/15 train/validation/test indices |
| `data/gates/`, `data/circuit/` | The 200 PVT corners and the SPICE references (3,600 gate runs and 51,200 circuit runs) |
| `data/netlists/` | Example netlists |
| `models/` | The four final transistor models, their settings (`manifest.json`), per-current validation metrics (`parts/*.json`) and training logs |
| `results/` | `data_check/`, `model_comparison/`, `model_development/`, `models/`, `gates/`, `circuit/`, `error_analysis/` |
| `report/report.pdf` | Project report |
| `tests/` | pytest suite |

## Setup

Requirements:
* [uv](https://docs.astral.sh/uv/).
* ngspice-47. This is needed only for the SPICE steps.
  * Windows: official build, `ngspice_con.exe`.
  * macOS: `brew install ngspice`.
  * Linux: your package manager.

```
uv sync                                   # Python 3.12 and the locked package versions (uv.lock)
set NGSPICE_EXE=C:\path\to\ngspice_con.exe    # Windows (macOS/Linux: export NGSPICE_EXE=ngspice)
uv run python scripts/00_check_env.py     # prints package and ngspice versions
uv run pytest -q
```

## Running the pipeline (in order)

```
uv run python scripts/01_generate_transistor_data.py   # 4 x 10,000 rows + single-transistor example netlists     [SPICE]
uv run python scripts/01b_generate_extra_data.py       # 4 x 30,000 extra uniform rows (training only)              [SPICE]
uv run python scripts/01c_generate_edge_data.py        # 4 x 20,000 rail-corner rows (training only)                [SPICE]
uv run python scripts/02_data_check.py                 # Kirchhoff check, distributions, trend plots                [SPICE]
uv run python scripts/03_make_splits.py                # fixed-seed 70/15/15 split
uv run python scripts/04_compare_models.py             # 4 model types x 4 cases on the validation set
# final per-current models: seven training runs (resumable; existing models/parts/*.joblib are skipped)
uv run python -u scripts/05d_train_per_current.py --cases nmos_on pmos_on   --currents ig    --params '{"wnorm": "weff", "edge_data": true}'
uv run python -u scripts/05d_train_per_current.py --cases nmos_off pmos_off --currents id is --params '{"wnorm": "weff", "edge_data": true}'
uv run python -u scripts/05d_train_per_current.py --cases nmos_on           --currents id    --params '{"wnorm": "weff", "edge_data": true}'
uv run python -u scripts/05d_train_per_current.py --cases nmos_on pmos_on   --currents is    --params '{"wnorm": "weff", "n_members": 1}'
uv run python -u scripts/05d_train_per_current.py --cases pmos_on           --currents id    --params '{"wnorm": "weff", "n_members": 1}'
uv run python -u scripts/05d_train_per_current.py --currents ib
uv run python -u scripts/05d_train_per_current.py --cases nmos_off pmos_off --currents ig    --params '{"n_members": 1}'
uv run python scripts/05e_evaluate_v2.py               # test-set metrics and predicted-vs-SPICE plots
uv run python scripts/06_gate_spice.py                 # 200 corners x 18 gate cases                                [SPICE]
uv run python scripts/07_gate_ml.py                    # gate-level ML vs SPICE
uv run python scripts/08_circuit_spice.py              # parity checker, 51,200 runs (~30 min)                      [SPICE]
uv run python scripts/09_circuit_ml.py                 # circuit-level ML vs SPICE
uv run python scripts/10_error_analysis.py             # error by corner condition
uv run python scripts/11_build_report_tables.py        # LaTeX tables for the report
```

* **Reproducing only the ML results:** scripts `05e`, `07`, `09`, `10` and `11` use only the committed data and models. They need no ngspice and no
  training, and they run in about a minute.
* **Training device:** `05d` uses a CUDA GPU if one is available, otherwise the CPU (`--device cpu|cuda` to force one). Full training takes about
  2.5 hours on a laptop GPU.
* **Windows `cmd` quoting:** write the `--params` JSON as `"{\"wnorm\": \"weff\", \"edge_data\": true}"`.
* **Fixed seeds:** every random draw uses fixed seeds from `config/project.yaml`.

## Notes

* **Assumptions:** the assignment leaves some points open. The team's assumptions are listed in Appendix B of the report and were not confirmed by
  the course staff:
  * the leakage definition;
  * the gate widths;
  * the Kirchhoff-consistent composition of gate leakage;
  * the extra training data;
  * the cross-checked SPICE reference;
  * the parity-checker architecture.
* **Gate and circuit SPICE data** is used for evaluation only, never for training.
* **Decision IDs:** comments of the form `D-0xx` in the code refer to entries in the team's decision log, which is kept in the git history of the
  project.
* **macOS:** torch and LightGBM each ship their own OpenMP runtime. When both are loaded in one process, LightGBM can hang. If the full test suite
  hangs, run `tests/test_ml.py` on its own.
