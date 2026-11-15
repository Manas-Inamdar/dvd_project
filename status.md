# status.md: repo walkthrough (branch `clean`)

Updated 2026-11-15. It covers branch **`clean`** (`origin/clean`), the cleaned Phase 7 pipeline. `main` and
`feature/phase7-per-current-models` appear only where they explain where something came from.
Everything under "verified" was re-run on macOS in this session; the other numbers come from the committed CSVs.
The assignment is `DVD_ML_PROJECT.pdf` (kept on `main` under `context/`).

---

## 0. TL;DR

* **The task:** predict CMOS leakage under PVT variation.
  * Train ML models only on *single-transistor* SPICE data.
  * Use them to predict 5 logic gates (18 input cases) and an 8-bit parity checker.
  * Compare with full SPICE. Target: "up to 99 % mean accuracy".
* **`clean` contains exactly the Phase 7 pipeline:**
  * data generation;
  * 4 transistor models, each made of one small MLP ensemble per terminal current (16 networks);
  * gate-level and circuit-level ML vs SPICE.
* **Results:**
  * Gate level: **99.65 %** mean accuracy (median error 0.19 %).
  * Parity checker: **99.73 %** (median 0.19 %).
  * The target is reached.
* **How `clean` was made:** it was cut from `feature/phase7-per-current-models` (commit 1073579). Unused material was deleted, the
  folders were reorganised (src / models / data / results), and a uv environment was added. Only paths changed in the code. Every
  model and result file is byte-identical to the Phase 7 original.
* **Still open:**
  * NMOS-ON id/is are worse than on `main` at transistor level (deliverable 5).
  * Some Phase 7 design choices were made while looking at gate results.
  * The report on `main` still shows the old 92.8 %.
  * Details in §11.

---

## 1. The assignment in one screen (from the PDF)

| Part | What the PDF asks | Our setting |
|---|---|---|
| A1 data | 4 cases (NMOS/PMOS x ON/OFF), 10,000 random samples each. Draw VDD first; Vd, Vs ~ U(0, VDD); W ~ U(1, 8)·Lmin; T ~ U(-40, 125) °C; vth0/toxe/ndep/u0/xj ~ nominal ±10 %. Vg and Vb are fixed by the case. "The number of samples may be increased" | PTM 22nm_LP (BSIM4), VDD = 1 V, L = 22 nm (team 26 row of the TA allocation sheet) |
| A2 models | Random 70/15/15 split with a fixed seed. "Train and compare different ML models for each case", pick on validation, report on test | Comparison: `results/model_comparison.md` (MLP won). Final: per-current MLP ensembles |
| B gates | INV, NAND2, NOR2, AND2, OR2: 18 input cases x 200 PVT corners. ML uses the SPICE node voltages → terminal voltages → the 4 transistor models → gate leakage | 3,600 SPICE runs |
| C circuit | Full SPICE netlist for every input vector x the same 200 corners. ML = sum of gate leakages (no loading) | 8-bit parity checker, 256 x 200 = 51,200 runs |
| Netlists | `.options gmin=1e-18 abstol=1e-18 reltol=1e-6 vntol=1e-9` in every netlist; single-FET netlists give every terminal its own source | + AD = AS = W·Ldiff (course chat) |
| Deliverables | 10 items: CSVs, example netlists, data check, model comparison, chosen models + plots, gate table + parity plot, circuit table + plot, code, report | Items 1-9 are on `clean` (§3). The report (10) is only on `main` and is outdated |

---

## 2. Branches

```
main ─ … ─ f9cdaba (Phases 1-6, report)                                    ← origin/main
             └─ 7f0c90a Phase 7 ─ 1073579 Minor Fix                          ← origin/feature/phase7-per-current-models
                                     └─ c19e61a cleanup ─ 884a37a status     ← clean, origin/clean
```
* **`clean`** (this file): only what the Phase 7 pipeline uses.
* **`main`** has:
  * the original pipeline: one multi-output MLP per case, 92.8 % gate / 92.5 % circuit;
  * the 4-family model comparison (scripts 03/04);
  * learning curves;
  * the 37k-row refit;
  * the LaTeX report and PDF;
  * `docs/` (decision log D-001..D-040, assumptions);
  * `context/` (assignment PDF, TA slides, PTM cards, chat).
* **`feature/phase7-per-current-models`** = `main` + Phase 7. It also holds the Phase 7 ablation study (`study/`,
  `results/study_*`, `scripts/05f`) and the decisions D-041..D-044.
* **Team rule:** CLAUDE.md on `main` (D-040) says "one branch only: `main`". `clean` and the Phase 7 branch go against it, so the team must
  decide what gets merged.

---

## 3. Repo map (`clean`)

| Path | What it is |
|---|---|
| `22nm_LP.pm` | The assigned SPICE model card (NMOS + PMOS BSIM4, level 54). Path set in `config/project.yaml` (`assignment.model_file`) |
| `config/project.yaml` | Every assignment number: VDD 1 V ±10 %, Lmin 22 nm, Ldiff 44 nm, W 1-8·Lmin, T range, process ±10 %, SPICE options, seed 20261105, split 70/15/15, I_FLOOR 1e-15 A. ngspice exe `ngspice_con` (Windows name; override with `NGSPICE_EXE`) |
| `pyproject.toml`, `uv.lock`, `.python-version` | uv project: Python 3.12, locked package versions (torch 2.15, pandas 2.3.3 pinned, numpy 2.5, scikit-learn 1.9, lightgbm 4.7) |
| `src/dvdml/` | Library, 16 modules, ~1,200 lines (§8) |
| `scripts/` | `00`, `01`, `01b`, `01c`, `02`, `05d`, `05e`, `06`-`09` (~930 lines). Original numbering kept so they match `main` |
| `data/transistor/` | **Deliverable 1**: 4 x 10,000-row CSVs (`vdd, temp, w, vd, vs, vg, vb, vth0, toxe, ndep, u0, xj, id, ig, is, ib`) + generation log |
| `data/transistor_extra/` | 4 x 30,000 extra uniform rows (gz). Rows 0-24,999 train, 25,000-29,999 holdout |
| `data/transistor_edge/` | 4 x 20,000 rail-corner rows (gz). 16k train, 2k join validation, 2k "edge holdout" |
| `data/splits/` | Fixed train/val/test row indices of the 10k datasets (npz; created by `main`'s script 03) |
| `data/gates/` | `corners.csv` (200 PVT corners), `gate_spice.csv` (3,600 cross-checked runs) |
| `data/circuit/` | `circuit_spice.csv` (51,200 runs) |
| `data/netlists/` | **Deliverable 2**: example single-FET (4), gate (18) and parity-checker (4) netlists |
| `models/` | **Deliverable 5**: `<case>.joblib` (4 `CompositeTransistorModel`s), `manifest.json` (settings + test metrics per current), `params.json`, `parts/*.json` (validation/holdout errors per current), `logs/` |
| `results/data_check/` | **Deliverable 3**: Kirchhoff check, current distributions, 3 trend plots |
| `results/model_comparison.md` | **Deliverable 4**: 4 families x 4 cases validation table (from `main`) and why the MLP was chosen |
| `results/models/` | Transistor test metrics (`test_results.csv`), rail-corner errors (test / holdout / edge holdout), predicted-vs-SPICE plots |
| `results/gates/` | **Deliverables 6-7**: `gate_results.csv` (18 cases), `gate_by_gate.csv`, `gate_estimators.csv` (naive vs KCL), per-run/per-device CSVs, parity + error-vs-corner plots |
| `results/circuit/` | **Deliverable 8**: `circuit_results.csv` (overall + by number of 1s), loading-effect decomposition, parity + error-vs-corner plots |
| `tests/` | pytest, 101 tests (ngspice tests run if `NGSPICE_EXE` is found, otherwise skip) |
| `status.md` | This file |

Size: data 43 MB, models 15 MB, results 17 MB. Removed compared with the Phase 7 branch: `context/`, `docs/`, `report/`, `dist/`,
`CLAUDE.md`, `CHANGES.md`, `requirements.txt`, `study/`, `models_saved/10k/enlarged/selected`, their results, scripts 03-05c, 05f, 12-14 and `latex.py`.

---

## 4. Setup and run

```bash
# once
brew install ngspice                      # ngspice 47 (Linux: package manager; Windows: official build, ngspice_con.exe)
uv sync                                   # .venv with Python 3.12 + locked packages
export NGSPICE_EXE=ngspice
uv run python scripts/00_check_env.py
uv run pytest -q --deselect "tests/test_ml.py::test_each_family_fits_and_predicts_a_toy_problem[lightgbm]"   # macOS, see §11

# pipeline (README.md has the same list)
uv run python scripts/01_generate_transistor_data.py   # ~2.5 min on this Mac
uv run python scripts/01b_generate_extra_data.py
uv run python scripts/01c_generate_edge_data.py
uv run python scripts/02_data_check.py
# 5 training runs (resumable; existing models/parts/*.joblib are skipped). Use --device cpu unless you have CUDA:
uv run python -u scripts/05d_train_per_current.py --device cpu --cases nmos_on pmos_on   --currents ig    --params '{"wnorm": "weff", "edge_data": true}'
uv run python -u scripts/05d_train_per_current.py --device cpu --cases nmos_off pmos_off --currents id is --params '{"wnorm": "weff", "edge_data": true}'
uv run python -u scripts/05d_train_per_current.py --device cpu --cases nmos_on pmos_on   --currents id is --params '{"wnorm": "weff", "n_members": 1}'
uv run python -u scripts/05d_train_per_current.py --device cpu --currents ib
uv run python -u scripts/05d_train_per_current.py --device cpu --cases nmos_off pmos_off --currents ig    --params '{"n_members": 1}'
uv run python scripts/05e_evaluate_v2.py               # test split → results/models/, rewrites models/manifest.json
uv run python scripts/06_gate_spice.py                 # ~40 s on this Mac
uv run python scripts/07_gate_ml.py                    # → results/gates/
uv run python scripts/08_circuit_spice.py              # ~30 min (51,200 runs)
uv run python scripts/09_circuit_ml.py                 # → results/circuit/  (needs 07's gate_runs_ml.csv)
```
* To reproduce only the ML results from the committed data and models, run `05e`, `07` and `09`. They need no torch and no ngspice.
* `models/parts/*.joblib` is git-ignored. To retrain one current, delete that part file, re-run its 05d command, then run 05e/07/09.

---

## 5. End-to-end flow (`clean`)

```
22nm_LP.pm ─► modelcard.nominals ─► sampling.sample_case ─► netlist.single_transistor_netlist ─► spice.run_netlist (ngspice -b, thread pool)
                                                                                                    │
  01  data/transistor/*.csv (4 × 10k, batch 0) ◄── dataset.generate_case (exactly N valid rows) ◄──┘
  01b data/transistor_extra (4 × 30k, batch 101)      01c data/transistor_edge (4 × 20k rail corners, batch 102)
  02  results/data_check (Kirchhoff, distributions, 3 SPICE trend sweeps)
                                        │
  05d ml_v2.CurrentModel per (case, current): features → width-normalised log/asinh target → MLP ensemble (Adam + L-BFGS)
      train = 7k split + 25k extra (+16k edge for some currents) │ val = 1.5k split (+2k edge) → models/parts/*.joblib
      → CompositeTransistorModel per case → models/<case>.joblib
  05e test split (1.5k) + holdouts → results/models/, models/manifest.json
                                        │
  06  corners.csv (200) + 18 gate cases × 200 corners, each solved twice (mandated + tight) → data/gates/gate_spice.csv
  07  SPICE node voltages → (Vd,Vg,Vs,Vb) per transistor → ON/OFF routing → models predict id/ig/is/ib
      → KCL solve for ON channel currents → leak_ml (mean of supply- and ground-side sums) vs leak_spice → results/gates/
  08  28-NAND2 parity netlist, 256 vectors × 200 corners, cross-checked → data/circuit/circuit_spice.csv
  09  logic propagation → each NAND2's input case → that case's gate ML leakage at the same corner → sum of 28 → results/circuit/
```

---

## 6. Phase by phase: logic and finer details

**Transistor data (`01`, `01b`, `01c`)**
* `sampling.sample_case(case, n, seed, cfg, nominal, batch)` seeds its RNG with `[seed, case_index, batch]`. Batch 0 is the main draw,
  batches 1-19 replace failed simulations (so each CSV has exactly N rows), 101 is the extra data and 102 the edge data.
  Each column is drawn as a vector, so a run with n = 20 is *not* the first 20 rows of an n = 10,000 run.
  Process values are multiplied by U(0.9, 1.1), which keeps PMOS vth0 negative.
* Vg and Vb are fixed per case: NMOS ON Vg = VDD, NMOS OFF Vg = 0, Vb = 0; PMOS mirrored with Vb = VDD.
* `netlist.single_transistor_netlist` builds one netlist per sample:
  * it puts the sampled process values into the device's BSIM4 card with a whole-token regex (`modelcard.set_params`; the other card stays nominal);
  * it sets `.temp`, gives each of the 4 terminals its own V source, uses AD = AS = W·Ldiff and no PD/PS;
  * it prints the currents with `print i(Vd) i(Vg) i(Vs) i(Vb)`.
* `spice.run_netlist` runs `ngspice -b` in a temp dir (60 s timeout).
  **Sign convention:** terminal current = −I(source), positive INTO the device, so Id + Ig + Is + Ib = 0.
* `01c` (edge data): VDD, T and process as usual; Vd and Vs are independently 40 % exactly at a rail, 40 % within 0.1·VDD·u² of a
  rail and 20 % uniform; W is log-uniform. Gate operating points sit at the rails, where uniform data is sparse.
  This uses only the fact that logic nodes are at 0 or VDD; no gate SPICE value is used.

**Data check (`02`)**
* It computes the Kirchhoff residual |Id + Ig + Is + Ib| per sample, histograms of current magnitudes, and three controlled
  one-at-a-time SPICE sweeps with automatic trend checks. All three pass:
  * OFF Id goes up ~400x from −40 to 125 °C;
  * OFF Id changes ~40x over vth0 ±10 %;
  * ON Ig goes down ~30x as toxe goes from −10 % to +10 %.
* **Key data fact:** currents span ~10 decades. Below ~1e-15 A the values are BSIM4/ngspice floating-point noise; for example,
  OFF-state ig is never above it. Hence **I_FLOOR = 1e-15 A**: metrics only count "resolved" samples (|I| > floor), and
  currents with < 5 % resolved samples are not scored (OFF ig).

**Transistor models (`ml_v2.py`, `05d`, `05e`)**
* Why one model per current: about 98 % of gate leakage on this card is **gate-oxide tunnelling of ON transistors** (OFF
  subthreshold ~2 %, body ~0.1 %). A shared 4-output network spends capacity on ON id/is, which the gate composition never uses (§6, gates).
* Each `CurrentModel`:
  * **Features** (`physics_features`, 21): the 15 from `ml.featurize` (log W, 1000/T, vdd, vd, vs, vds, vgs, vgd, vbs, vbd,
    |vth0|, toxe nm, log ndep, u0, xj nm) plus Vgs/toxe, Vgd/toxe, |Vgs|−Vth, |Vgd|−Vth, Vth/kT, VDD/toxe. All are standardised.
  * **Width normalisation:** the current is divided by Weff/Lmin with Weff = W − 2·wint (wint = 5 nm, from the card), or by W/Lmin
    for ib (junction area) and the settings marked "W" below. BSIM4 scales channel and tunnelling current with Weff, which is
    only 55 % of W at W = Lmin.
  * **Target:** `log` mode = log10(|I|), trained only on resolved rows, for currents that never change sign (ON ig, all ib).
    The sign is stored as the median sign. `asinh` mode = asinh(I / 1e-15) / ln10 (signed log) for id, is and OFF ig.
  * **Network:** 21 → 4 x [128, tanh] → 1 (~52k weights).
  * **Loss:** mean squared error with weight 1 + 4·(e(Vd) + e(Vs)), where e = exp(−distance to nearest rail / 0.05·VDD).
  * **Training:** Adam in float32 (1500 epochs, batch 512, lr 3e-3 with cosine decay, keeps the best validation state checked every
    10 epochs), then up to 6 full-batch L-BFGS rounds in float64, each kept only if validation improves.
  * **Ensemble:** n_members seeds; the prediction is their mean in target space.
  * **Prediction is pure numpy** (`h @ W.T + b`, tanh), so torch is only needed for training.
* `CompositeTransistorModel` = the 4 `CurrentModel`s of a case. Its `predict(df)` returns id, ig, is and ib in A, the same interface
  as `main`'s models, so 07/09 did not need changes. **So the setup is 16 networks inside 4 model files.**
* The final settings per current (`models/manifest.json`) come from 5 separate 05d runs:

  | Current | Target | Members | Edge data | Width |
  |---|---|---|---|---|
  | ON ig | log | 3 | yes | Weff |
  | OFF id, is | asinh | 3 | yes | Weff |
  | ON id, is | asinh | 1 | no | Weff |
  | all ib | log | 3 | no | W |
  | OFF ig | asinh | 1 | no | W |

* **Training rows per case:** 32,000 uniform (7,000 split + 25,000 extra), plus 16,000 rail-corner rows for the "edge" currents (48,000).
  Validation is 1,500 rows (+2,000 rail-corner). Test is the original 1,500-row split, the same as on `main`.
* `05e` evaluates once on the test split and on the uniform and rail-corner holdouts, broken down by (Vd, Vs) rail-corner region.

**Gates (`gates.py`, `corners.py`, `refsolve.py`, `gate_ml.py`, `06`, `07`)**
* `gates.GATES` is the single definition of topology and widths, and both SPICE and ML read it.
  * Widths in Lmin: INV n1/p2, NAND2 2/2, NOR2 n1/p4.
  * AND2 = NAND2 + INV and OR2 = NOR2 + INV, simulated as complete gates.
* **Corners** (`make_corners`): 200 draws of VDD, T, one NMOS process draw and one PMOS process draw, seed `[seed, 777]`. All NMOS in a gate share
  one draw and all PMOS share another. The circuit reuses the same corners by index.
* **Gate netlists:**
  * ground goes through `Vgnd vss 0 dc 0`, so the return current is measurable;
  * the inputs are ideal sources at exactly 0 or VDD;
  * `.nodeset` gives starting values only.
* **Reference cross-check (`refsolve.solve_with_crosscheck`, D-031):** with exactly the mandated tolerances, ngspice converged to wrong
  operating points in 59 of 3,600 runs and failed in 66. So every run is solved twice:
  * with the mandated options;
  * with an extra `.options abstol=1e-15 reltol=1e-9 vntol=1e-12` line.

  If the two agree within 1 %, the mandated result is used; otherwise the tight one. The choice is logged in `ref_source`.
* **Leakage definition (A1):** total current delivered by every source at VDD (the supply plus inputs held at 1). It equals the current absorbed at 0 V.
* **ML side (`gate_ml.predict_runs`):**
  1. Copy the SPICE node voltages (out, internal x/y/n) to each transistor's (Vd, Vg, Vs, Vb). The inputs are ideal 0/VDD.
  2. Route each device to a model by its gate voltage: NMOS is ON if Vg > VDD/2, PMOS is ON if Vg < VDD/2.
  3. Predict id, ig, is and ib.
  4. **KCL-consistent composition (A3, D-030):**
     * An ON transistor in a gate has Vds ≈ 1e-7 V. Its channel current is tiny and is set by whatever the OFF network leaks, so
       a model cannot predict it.
     * So for each ON device the channel current is an unknown J, with is = −J − ig − ib.
     * KCL at every internal node gives equations, which are solved by least squares (`np.linalg.lstsq`).
     * The currents are then summed at the VDD-level nodes and at the 0 V nodes, and the two sums are averaged.
  5. **Consequence:** ON-model id/is never enter the leakage. What matters is ON ig, OFF id/is and all ib.
* The naive sum of model currents (`gate_estimators.csv`) is off by up to ~3000x (median error 180 % / 97 %), which is why the KCL method is needed.

**Parity checker (`circuit.py`, `08`, `09`)**
* **Architecture (D-035):** 7 XOR2 in a balanced tree. Each XOR2 is the classic 4-NAND2 XOR: n1 = NAND(a,b), n2 = NAND(a,n1),
  n3 = NAND(b,n1), y = NAND(n2,n3). That makes 28 NAND2 and 112 transistors, so every gate maps to one of the 4 Part-B NAND2 cases.
* **SPICE:** 51,200 runs, cross-checked, in resumable chunks of 20 corners. The output is at the correct logic rail in 100 % of runs.
* **ML (`09`):** propagate the logic values (`instance_cases`), count the NAND2s per input case for each vector, then
  leak_ml = Σ count × (Part-B NAND2 ML leakage at the same corner). It reads `results/gates/gate_runs_ml.csv`, so run 07 first.
* **Diagnostic:** the sum of isolated-gate SPICE leakages reproduces circuit SPICE to within 1e-4, so loading between gates is
  negligible and circuit error ≈ gate-model error.

---

## 7. Results (`clean`, committed CSVs)

**Transistor test split** (`results/models/test_results.csv`): median / P95 relative error on resolved samples.

| Case | id | ig | is | ib | Macro median / P95 | R² (signed log) |
|---|---|---|---|---|---|---|
| NMOS ON | **12.7 / 99.8 %** (bias +22 %) | 0.59 / 7.2 % | **14.7 / 46.3 %** (bias +7 %) | 0.27 / 1.6 % | 7.1 / 38.7 % | 0.997 |
| NMOS OFF | 1.9 / 9.4 % | noise | 1.3 / 9.6 % | 0.15 / 0.86 % | 1.1 / 6.6 % | 0.989 |
| PMOS ON | 3.9 / 14.1 % | 0.16 / 0.75 % | 6.5 / 27.9 % | 0.33 / 2.5 % | 2.7 / 11.3 % | 0.999 |
| PMOS OFF | 2.6 / 15.2 % | noise | 2.9 / 13.8 % | 0.19 / 2.2 % | 1.9 / 10.4 % | 0.975 |

**Gates** (`results/gates/`): 3,600 runs. Mean accuracy **99.65 %**, median error 0.19 %, P95 1.2 %, max 5.7 %, bias +0.03 %.
* By gate (mean accuracy): INV 99.43 %, NAND2 99.75 %, NOR2 99.58 %, AND2 99.70 %, OR2 99.66 %.
* All 18 cases are ≥ 99.4 %. The worst are INV_0 / INV_1 (99.44 / 99.41 %) and NOR2_10 (99.42 %).
* Supply-side and ground-side estimates agree (median 0.20 % vs 0.20 % error).

**Parity checker** (`results/circuit/`): 51,200 runs, typical leakage ≈ 2.9 nA.
* Mean accuracy **99.73 %**, median 0.19 %, P95 0.79 %, max 1.6 %, bias +0.14 %.
* It is flat across the number of 1s in the input (99.72-99.75 %).

**Model comparison** (`results/model_comparison.md`, from `main`): the MLP wins all 4 cases on validation, with a score 2.5-5x
better than LightGBM. Kernel ridge and polynomial ridge have P95 errors from hundreds to tens of thousands of percent.

**How Phase 7 got there** (from the Phase 7 branch's stage comparison):

| Stage | Gate | Circuit |
|---|---|---|
| `main` (one 4-output MLP per case, 7k rows) | 92.8 % | 92.5 % |
| one model per current, W-normalised | 96.6 % | 97.9 % |
| + Weff | 97.6 % | 97.8 % |
| **+ rail-corner data (final)** | **99.65 %** | **99.73 %** |

---

## 8. Library cheat-sheet (`src/dvdml/`)

| Module | Key API | Notes |
|---|---|---|
| `config.py` | `load_config()`, `model_path()`, `REPO_ROOT` | `model_path` = REPO_ROOT / `assignment.model_file` (= `22nm_LP.pm`) |
| `modelcard.py` | `split_cards`, `get_param`, `set_params`, `nominals` | Whole-token regex, so `xj` never matches `xjbvs` |
| `sampling.py` | `CASES`, `INPUT_COLUMNS`, `sample_case`, `device_type` | Seed `[seed, case_idx, batch]` |
| `netlist.py` | `single_transistor_netlist` | The tested device's card gets the sampled values; the other card stays nominal |
| `spice.py` | `run_netlist`, `parse_source_currents`, `terminal_currents`, `ngspice_exe` | `NGSPICE_EXE` overrides `cfg.spice.exe` |
| `dataset.py` | `simulate_samples` (thread pool), `generate_case` | Threads are enough because ngspice runs as subprocesses |
| `metrics.py` | `I_FLOOR`, `to/from_signed_log`, `summarize`, `macro` | "Resolved" = \|true\| > 1e-15 |
| `ml.py` | `featurize` (used by `ml_v2`); also `TransistorModel`, `GRIDS`, `FAMILIES` of the old comparison | Kept whole because `ml_v2` imports `featurize`. Its LightGBM family causes the macOS hang (§11) |
| `ml_v2.py` | `physics_features`, `edge_weight`, `CurrentModel`, `CompositeTransistorModel`, `MODES` | The Phase 7 models; pure-numpy prediction |
| `corners.py` | `make_corners` | 200 corners, shared NMOS/PMOS process draws |
| `gates.py` | `GATES`, `gate_netlist`, `parse_values`, `leakage_from_values`, `node_voltages`, `case_name` | One topology definition feeds both SPICE and ML |
| `refsolve.py` | `solve_with_crosscheck` | Mandated vs tight solve, 1 % agreement rule |
| `gate_ml.py` | `transistor_rows`, `route`, `predict_runs` | Naive sums + KCL composition |
| `circuit.py` | `INSTANCES`, `logic_values`, `instance_cases`, `circuit_netlist`, `parity` | 28 NAND2 |
| `plots.py` | `plot_case` | Predicted-vs-SPICE plots (05e) |

---

## 9. Assumptions (team decisions, NOT confirmed by the TAs)

The full decision log is on `main` (`docs/DECISIONS.md`, `docs/PROJECT_CONTEXT.md`); D-041..D-044 are on the Phase 7 branch.

| ID | Assumption | Why it matters |
|---|---|---|
| A1 / D-011 | Leakage = current from all VDD-level sources (supply + inputs at 1) | Includes the gate current drawn from the input drivers |
| A2 / D-012, D-029 | Widths INV 1/2, NAND2 2/2, NOR2 1/4 x Lmin; ON/OFF routing by Vg vs VDD/2 | Gate results depend directly on these |
| A3 / D-030 | KCL composition instead of a plain sum | The plain sum is off by orders of magnitude. This is the core of the method; be ready to defend it |
| A4 / D-034, D-037, D-043 | Training beyond the 10k rows: +25k uniform, +16k rail-corner rows (non-uniform Vd/Vs) | The PDF allows more samples, but the rail-corner rows deliberately bend "draw uniformly". Disclose it |
| D-031 | Tight-tolerance cross-check of the SPICE reference | Departs from the literal mandated tolerances in ~3.5 % of gate runs |
| D-035 | Parity checker = 28 NAND2 | Any of the 5 allowed gates would do |
| Q6/Q7 | The ML side copies SPICE node voltages; circuit ML uses the isolated-gate voltages at the same corner | The ML never estimates node voltages itself |

---

## 10. Verification done on `clean` (macOS, 2026-11-15)

Environment: `uv sync` (Python 3.12.x, torch 2.15, numpy 2.5.4, pandas 2.3.3), Homebrew ngspice 47.

| Check | Result |
|---|---|
| pytest | **100 of 101 pass**, including the ngspice tests. The LightGBM toy test hangs only when the whole suite runs on macOS; it passes on its own |
| `05e`, `07`, `09` re-run | Identical to the committed CSVs up to 1.7e-10 relative. 99.65 % / 99.73 % reproduced. PNGs differ only in rendering |
| `02` re-run | Tables identical (apart from CRLF line endings). One trend ratio differs in the 7th digit (ngspice build) |
| `01` full re-run (40k sims, 2.5 min) | Inputs identical; id and is identical. Only currents within ~10x of 1e-15 A differ (noise floor) |
| `01b`, `01c` (20 rows) | Run fine |
| `06` full re-run (3,600 runs, 40 s) | Corners identical (apart from CRLF and last digits). Leakage within 1e-3 (median 3e-6); `ref_source` differs in 92 runs. **Gate ML accuracy against this reference: 99.647 %, unchanged** |
| `08` (2 corners x 256 vectors) | Leakage within 1e-5 of the committed runs; parity correct |
| `05d` (3 epochs, CPU) | Trains and writes the part file. With the default `--device cuda`: `Torch not compiled with CUDA enabled` |
| File moves | Every model, result and netlist file is byte-identical to its Phase 7 original (git blob hashes) |

Not done: full training (several hours on CPU), full `08` (30 min), regenerating `data/splits` (its script is on `main`).

---

## 11. Known issues and review findings (`clean`)

1. **Deliverable 5 regression (NMOS ON id/is).**
   * On the test split, median id is 12.7 % (`main`: 5.6 %) with a +22 % bias, and is is 14.7 % (`main`: 5.2 %).
   * Leakage doesn't suffer, because KCL never uses ON id/is.
   * The deliverable asks for test errors of the saved models, so a reviewer will see it.
   * Cause: ON id/is use 1 member and no edge data. The ON-id error at the rails is large: on the test split, the median at Vd,Vs > 0.9·VDD is ~120 % (n = 10).
2. **Design guided by gate results (soft evaluation leakage).**
   * No gate or circuit SPICE value entered training.
   * But Weff normalisation, rail emphasis and which currents get edge data were chosen after looking at gate-level errors.
   * Weff is physics read from the card, and the edge sampling uses only "logic nodes sit at rails". Still, the 99.65 % is somewhat optimistic; disclose it.
3. **Rail-corner data departs from uniform sampling.** The PDF says to draw inputs independently from the Section 4 distributions.
   The deliverable CSVs stay uniform; the 16k rail rows are extra training data. Ask the TA.
4. **The report is not on `clean`, and the one on `main` still shows 92.8 % / 92.5 %.** Deliverable 10 needs new numbers.
5. **`05d` defaults to `--device cuda`.** It fails without an NVIDIA GPU, so pass `--device cpu`. Apple MPS has no float64, which L-BFGS needs.
6. **`config/project.yaml` names ngspice `ngspice_con`** (Windows). Set `NGSPICE_EXE` everywhere else.
7. **macOS: torch + LightGBM in one process.** Both torch and scikit-learn bundle their own `libomp`. After torch runs, LightGBM fails with
   `OMP: System error #22` and hangs. This only affects `ml.py`'s comparison code and `tests/test_ml.py[lightgbm]`; Phase 7 doesn't use LightGBM.
8. **`data/splits/` cannot be regenerated on `clean`.** `make_split` lives in `main`'s `scripts/03_train_compare_models.py`.
9. **Building the models takes 5 separate 05d runs.** A single default run does not reproduce them. 05d skips existing parts, so stale
   `models/parts/*.joblib` files are silently reused.
10. **Hard-coded constants:** `ml_v2.py:25-26` `LMIN = 22e-9`, `WINT = 5e-9`. They should come from the config or the card (`modelcard.get_param`).
11. **`log` mode sign** (`ml_v2.py:100`): one median sign per current, with no check that the current never changes sign.
12. **Code nits:**
    * `gate_ml.py:74-76`: `rail_sums` uses `terminals_keys`, which is defined after it (works through the closure, but fragile).
    * `summarize` is duplicated in `07` and `09`.
    * `02_data_check.py:28` uses `FLOOR = 1e-16` while the rest uses 1e-15.
    * `09_circuit_ml.py:59-60` builds lookups with a Python list comprehension over 51,200 rows.
    * Dropped docs are still referenced in docstrings (D-0xx numbers, `docs/...`); they live on `main`.
13. **Line endings:** the committed text files are CRLF (made on Windows) and there is no `.gitattributes`. Files regenerated on Mac/Linux show as fully changed in `git diff`.
14. **Branch policy:** `clean` and the Phase 7 branch go against the team's "main only" rule (D-040). Agree on what becomes `main`.

---

## 12. Improvement backlog (rough value/effort order)

| # | Idea | Why | Effort |
|---|---|---|---|
| I-1 | Fix deliverable 5: retrain ON id/is with 3 members + edge data (or with a bias check), then re-run 05e/07/09 | Removes the visible transistor-level regression | M (CPU hours) |
| I-2 | Team decision: make `clean` (or Phase 7) the main line, then update the report with the new numbers and disclosures (§11.2-3) | The 99 % result is what will be graded | M |
| I-3 | Add `scripts/02b_make_splits.py` (exact copy of `make_split`) so `clean` rebuilds from scratch; check that it reproduces the npz byte for byte | Self-contained pipeline | S |
| I-4 | A single `--recipe` / config file for the 5 training runs (instead of 5 command lines), and `--device auto` (cuda → cpu) | Reproducible training with one command | S |
| I-5 | `.gitattributes` (`* text=auto`), and default `spice.exe` to `ngspice` with the Windows name only in an override | Cross-platform | S |
| I-6 | Move `LMIN`/`WINT` to config or read `wint` from the card; assert the sign is constant in `log` mode | Robustness | S |
| I-7 | Solve the internal node voltages from the ML currents (Newton/KCL) instead of copying SPICE (Q7: "node voltages from both") | Makes the ML pipeline independent of SPICE node data; strong report point | M-L |
| I-8 | Fair comparison for the final setup: LightGBM / kernel ridge on the per-current + Weff + edge targets | Stronger "reason for final choice" | M |
| I-9 | Error analysis for the report: errors vs T, vth0, VDD (`results/gates/gate_error_vs_corner.png`); explain the INV / NOR2_10 worst cases | Required report section | S-M |
| I-10 | Ensemble spread as an uncertainty band on predicted leakage | Cheap report addition | S |
| I-11 | Learning curve for Phase 7 (how much edge data is needed) | The PDF's "smallest dataset possible" goal | M |
| I-12 | Full clean-run reproducibility including training and `08`, with runtimes | Deliverable 9 | M-L |
| I-13 | Deduplicate `summarize`; vectorise the gate KCL solve and the circuit lookup; fix the 02 floor constant | Maintainability, speed | S |

---

## 13. Quick numbers reference

| | `clean` (Phase 7, `models/`) | `main` baseline (for comparison) |
|---|---|---|
| Gate: mean accuracy / median / P95 / max / bias | **99.65 %** / 0.19 % / 1.2 % / 5.7 % / +0.03 % | 92.8 % / 5.5 % / 19.6 % / 59 % / +1.5 % |
| Circuit: mean accuracy / median / P95 / max | **99.73 %** / 0.19 % / 0.79 % / 1.6 % | 92.5 % / 6.4 % / 19.1 % / 46 % |
| Transistor test macro median (NMOS ON / NMOS OFF / PMOS ON / PMOS OFF) | 7.1 / 1.1 / 2.7 / 1.9 % | 4.1 / 1.6 / 1.9 / 4.2 % |
| ON ig test median (NMOS / PMOS) | 0.59 % / 0.16 % | 2.8 % / 1.1 % |
| Networks | 16 (4 per case) in 4 files | 4 (one 4-output MLP per case) |
| Training rows per case | 32,000-48,000 (7k + 25k uniform [+ 16k rail-corner]) | 7,000 |
| Data sizes | 4 x 10k + 4 x 30k extra + 4 x 20k edge transistor rows; 3,600 gate runs; 51,200 circuit runs | 4 x 10k (+ 4 x 30k extension) |
