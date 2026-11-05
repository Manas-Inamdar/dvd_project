# dvd_project - ML-driven PVT-variation-aware leakage estimation

Digital VLSI Design course project (team 26): estimate the leakage current of CMOS gates and an 8-bit parity checker under process, voltage and
temperature variation with machine-learning models trained on single-transistor SPICE data, and compare with full SPICE simulations.

* Technology: PTM **22nm_LP** (BSIM4), nominal VDD **1 V**, L = 22 nm, W = 1-8 x Lmin. Simulator: **ngspice 47**.
* Pipeline: single-transistor data (4 cases) -> 4 ML models (MLP chosen) -> 5 gates x 18 input cases x 200 corners -> 8-bit parity checker (256 vectors x 200 corners).
* Headline results (models trained on the specified 10,000-row datasets): gate level median error 5.5 % (mean accuracy 92.8 %), parity checker median error 6.4 % (92.5 %).
  The 99 % accuracy target is not reached. An enlarged-training-set extension is reported next to it (it improves the transistor models but not the gate level).

## Layout
| Path | Content |
|---|---|
| `context/` | assignment, TA slides, PTM models, example netlist, anonymized chat transcript (no screenshots) |
| `docs/` | PROJECT_CONTEXT, IMPLEMENTATION_PLAN, PROJECT_STATUS, DECISIONS, TEAM_WORKFLOW |
| `config/project.yaml` | all assignment parameters and seeds |
| `src/dvdml/` | library: sampling, netlists, ngspice runner, gates, circuit, ML models, metrics |
| `scripts/` | numbered pipeline scripts, run in order (see below) |
| `data/` | transistor datasets (10,000 rows x 4), splits, extra training data, gate and circuit SPICE references |
| `models_saved/` | the four final transistor models (headline); `models_10k/`, `models_enlarged/`, `models_selected/` = extension |
| `netlists/` | example netlists: single transistor, gates, parity checker |
| `results/` | tables and figures (data check, models, gates, circuit) |
| `report/` | LaTeX report (`report.tex`, sections, generated tables) |
| `tests/` | pytest suite (96 tests; those needing ngspice skip if it is not found) |

## Run
```
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt        # pandas is pinned (see requirements.txt)
set NGSPICE_EXE=C:\path\to\ngspice_con.exe                         # ngspice 47
.venv\Scripts\python.exe scripts\00_check_env.py
.venv\Scripts\python.exe scripts\01_generate_transistor_data.py    # 4 x 10,000 rows
.venv\Scripts\python.exe scripts\02_data_check.py                  # Kirchhoff, distributions, trend plots
.venv\Scripts\python.exe scripts\03_train_compare_models.py        # 4 model types x 4 cases (validation)
.venv\Scripts\python.exe scripts\04_select_and_evaluate.py         # chosen models, test metrics, plots
.venv\Scripts\python.exe scripts\05_learning_curves.py
.venv\Scripts\python.exe scripts\06_gate_spice.py                  # 200 corners, 18 gate cases (cross-checked reference)
.venv\Scripts\python.exe scripts\07_gate_ml.py                     # gate-level ML vs SPICE
.venv\Scripts\python.exe scripts\08_circuit_spice.py               # parity checker, 51,200 runs (~30 min)
.venv\Scripts\python.exe scripts\09_circuit_ml.py                  # circuit-level ML vs SPICE
# extension (enlarged training set):
.venv\Scripts\python.exe scripts\01b_generate_extra_data.py ; scripts\05b_retrain_enlarged.py ; scripts\05c_select_final.py
.venv\Scripts\python.exe scripts\07_gate_ml.py --models-dir models_selected --out-dir results/gates_selected
.venv\Scripts\python.exe scripts\09_circuit_ml.py --gate-runs results/gates_selected/gate_runs_ml.csv --out-dir results/circuit_selected
.venv\Scripts\python.exe scripts\12_build_report_tables.py         # regenerate the report tables
.venv\Scripts\python.exe -m pytest -q
```
The report is compiled from `report/report.tex` (e.g. on Overleaf: upload `report/` and `results/`; graphics are found via `../results/...`).

## Notes
* Several points of the assignment are open; our assumptions (gate leakage definition, gate widths, Kirchhoff-consistent composition, dataset size, parity-checker architecture) are listed in `docs/PROJECT_CONTEXT.md` and the report appendix and are **not confirmed by the course staff**.
* The SPICE reference is cross-checked: the mandated solver options give invalid operating points in 3.5 % of the gate runs (see report Section 4).
