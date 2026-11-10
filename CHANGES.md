# CHANGES - Phase 7: accuracy push to the 99 % target (2026-11-10)

**Result:** the 99 % mean-accuracy target is reached at both levels, with the existing SPICE references and the unchanged gate/circuit scripts.

| Level | Phase 3 headline (`models_saved/`) | **Phase 7 (`models_v2/`)** |
|---|---|---|
| Gate level, 3,600 runs: mean accuracy | 92.8 % | **99.65 %** |
| median / P95 / max error | 5.5 % / 19.6 % / 59 % | **0.19 % / 1.2 % / 5.7 %** |
| bias, R2 (linear / log10) | +1.5 %, 0.985 / 0.993 | **+0.03 %, 0.99997 / 0.99997** |
| Parity checker, 51,200 runs: mean accuracy | 92.5 % | **99.73 %** |
| median / P95 / max error | 6.4 % / 19.1 % / 46 % | **0.19 % / 0.79 % / 1.6 %** |

All 18 gate cases are at 99.4 % or better. The circuit error is flat across input vectors (0.19-0.20 % median). The spread of the error between PVT corners fell from 9.9 % to 0.33 %.

The 10,000-row deliverable datasets, the train/validation/test splits, the gate and circuit SPICE references and the Phase 1-6 models and results are **unchanged**. Phase 7 is added next to them. Whether `models_v2` becomes the headline is a team decision (D-044).

## What was wrong (diagnosis)
1. **The leakage is almost only gate tunnelling of ON transistors.** For this card about 98 % of the gate leakage is gate-oxide tunnelling (`ig`) of the ON devices. OFF subthreshold current is about 2 % and body current about 0.1 %. The old single 4-output MLP spent equal effort on ON `id`/`is`, which the KCL composition (D-030) never uses.
2. **Gates operate at the corners of the training domain.** Every transistor in a gate has its drain and source at a rail. Those points are the corners of the uniformly sampled (Vd, Vs) box, where the training data is sparse.
3. **The width scaling was wrong.** BSIM4 scales tunnelling and channel currents with the effective width Weff = W - 2·wint (wint = 5 nm). At W = Lmin that is only 55 % of the drawn W. The gates use exactly the smallest widths (1, 2, 4 x Lmin).
4. **Simulator check.** ngspice proves the remaining error was the model's. Single-transistor SPICE at the exact gate operating points equals the gate-level SPICE input current to < 0.1 %. The old models were still 3 % off there.

## What changed
| Change | Where | Decision |
|---|---|---|
| One MLP ensemble per terminal current (3 seeds, tanh 4x128, Adam + L-BFGS polish). Log targets for constant-sign currents, signed-log for id/is. Physics features (oxide fields, overdrives, vth0/kT). Rail-emphasis sample weight. Pure-numpy prediction, same `predict` interface as before | `src/dvdml/ml_v2.py`, `scripts/05d_train_per_current.py` | D-041 |
| Effective-width target normalisation, `wnorm="weff"` | `src/dvdml/ml_v2.py` | D-043 |
| 4 x 20,000 **transistor-level** training rows concentrated at the rail corners: 40 % exactly at a rail, 40 % near a rail, 20 % uniform; W log-uniform. 0 failed simulations | `scripts/01c_generate_edge_data.py`, `data/transistor_edge/` | D-043 |
| Evaluation on the test split plus rail-corner holdouts; stage-by-stage comparison | `scripts/05e_evaluate_v2.py`, `scripts/05f_compare_stages.py` | |
| Low-load training mode: one job at a time, fp32 Adam, 4 threads, resumable. The second dev laptop hard-reset under sustained full load | `scripts/05d_train_per_current.py` | D-042 |
| `torch` added to `requirements.txt` (it was used by `ml.py` but missing) | `requirements.txt` | |
| Unit tests for the new module (target round trip, Weff scaling, edge weight, features, toy fit) | `tests/test_ml_v2.py` | |
| Docs: decisions D-041..D-044, D-039 marked superseded, status, README run steps | `docs/`, `README.md` | |

**Rule kept:** gate and circuit SPICE values were used only to evaluate and diagnose, never to train, calibrate or select models. All training and model choices use transistor data: validation split, holdout rows and rail-corner holdout rows.

## Progress by stage (gate / circuit mean accuracy)
| Stage | Gate | Circuit |
|---|---|---|
| Phase 3 headline | 92.8 % | 92.5 % |
| Per-current models, I/(W/Lmin) | 96.6 % | 97.9 % |
| + Weff normalisation | 97.6 % | 97.8 % |
| **+ rail-corner transistor data (final)** | **99.65 %** | **99.73 %** |

NMOS ON `ig` (the dominant term) at the gate input operating points: +7.1 % → +3.4 % → **+0.35 %**.
Full tables: `results/stage_comparison.csv`, `results/stage_comparison_by_gate.csv`, `results/stage_comparison_transistor.csv`.

## New and changed files
- New: `src/dvdml/ml_v2.py`, `scripts/01c_generate_edge_data.py`, `scripts/05d_train_per_current.py`, `scripts/05e_evaluate_v2.py`, `scripts/05f_compare_stages.py`, `tests/test_ml_v2.py`, `CHANGES.md`
- New data and models: `data/transistor_edge/` (9 MB), `models_v2/` (4 composite models, 15 MB; per-current metrics in `models_v2/parts/*.json`; training logs)
- New results: `results/models_v2/`, `results/gates_v2/`, `results/circuit_v2/`, `results/stage_comparison*.csv`, ablation summaries in `results/study_v2_wnormW/` and `results/study_v2_weff/`, ablation metrics and logs in `study/`
- Changed: `requirements.txt`, `.gitignore` (per-current model binaries and ablation run CSVs stay local), `README.md`, `docs/DECISIONS.md`, `docs/PROJECT_STATUS.md`

## Reproduce
See `README.md` → Run → "Phase 7". You need ngspice 47 (`NGSPICE_EXE`) for `01c`, and torch for training; a CUDA GPU is optional. Prediction needs numpy only.

## Caveats (stated openly)
- On the **uniform** transistor test split, OFF `id`/`is` of the final models are about as good as, or slightly worse than, the intermediate stages, because capacity moved to the rail corners where gates operate. ON `id`/`is` get a 1-member model and are weaker than Phase 3; leakage does not use them. OFF `ig` is below the 1e-15 A noise floor in every row and is not scored.
- The diagnosis (which operating points matter, the measured width ratio) looked at gate results, as in D-038. No gate or circuit value entered training.
- Tests: 101 passed with ngspice. 1 LightGBM test fails only on machines where lightgbm is not installed.
- Not done yet: the LaTeX report (`report/`) still shows the Phase 3 numbers. Updating it needs the team's decision on D-044.
