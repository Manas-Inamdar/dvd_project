# status.md: repo walkthrough (local notes, NOT tracked by git)

Written 2026-11-12 from a full read of `main` (f9cdaba) and `origin/feature/phase7-per-current-models` (1073579),
checked against the assignment PDF `context/DVD_ML_PROJECT.pdf`. Nothing was re-run for this note: ngspice and torch
are not installed on this Mac. All numbers below come from the CSVs committed in the repo.

---

## 0. TL;DR

* **The task:** predict CMOS leakage under PVT variation. Use ML models trained only on *single-transistor* SPICE data,
  then build up to 5 gates (18 input cases) and an 8-bit parity checker. Compare against full SPICE. Target: "up to 99 % mean accuracy".
* **`main`** holds the whole pipeline, Phases 1-6, and it is complete. It produced the datasets, 4 MLP transistor models,
  3,600 gate SPICE runs, 51,200 parity-checker SPICE runs, a LaTeX report and a rendered PDF.
  Headline accuracy: **gate 92.8 %, circuit 92.5 %**. The 99 % target is **not** met on `main`.
* **`feature/phase7-per-current-models`** (2 commits by a teammate, 2026-11-10, **not merged**) adds "Phase 7":
  one model per terminal current, effective-width (Weff) normalisation and extra training data at the voltage rails.
  Claimed result: **gate 99.65 %, circuit 99.73 %**. It is purely additive (new files plus doc edits). The report still shows the Phase 3 numbers.
* **Decision the team still owes:** D-044, i.e. whether `models_v2` becomes the headline. After that, the report has to be updated.
  `main` has not moved since the branch was cut, so a merge would be a clean fast-forward.

---

## 1. The assignment in one screen (from the PDF)

| Part | What | Our setting |
|---|---|---|
| A1 data | 4 cases (NMOS/PMOS x ON/OFF), 10,000 random samples each. Draw VDD first, then Vd, Vs ~ U(0, VDD), W ~ U(1, 8)·Lmin, T ~ U(-40, 125) °C, vth0/toxe/ndep/u0/xj ~ nominal ±10 %. Vg and Vb are fixed by the case | 22nm_LP PTM BSIM4, VDD = 1 V, L = 22 nm |
| A2 models | 70/15/15 split with a fixed seed. Compare ≥ 4 ML types per case, pick on validation, report on test | MLP won all 4 cases |
| B gates | INV, NAND2, NOR2, AND2, OR2 → 18 input cases × 200 PVT corners. ML uses the SPICE-recorded internal and output node voltages → terminal voltages → transistor models → gate leakage | 3,600 SPICE runs |
| C circuit | Full-netlist SPICE for every input vector × the same 200 corners. ML = sum of the gate-model leakages (no loading) | 8-bit parity, 256 × 200 = 51,200 runs |
| Netlists | Every netlist has `.options gmin=1e-18 abstol=1e-18 reltol=1e-6 vntol=1e-9`; in single-FET netlists each terminal gets its own voltage source | + AD = AS = W·Ldiff (from the course chat) |
| Deliverables | 10 items: CSVs, example netlists, data check, 4×4 comparison table, chosen models + plots, gate table, gate parity plot, circuit table + plot, code, report | checklist in `report/tables/deliverables.tex` |

Things the PDF leaves open, which the team settled as **its own assumptions (not TA-confirmed)**:
* **A1:** the definition of gate leakage.
* **A2:** transistor widths inside gates.
* **A3:** KCL-consistent composition.
* **A4:** enlarged training set.
* Also: the parity-checker architecture.

See §6.

---

## 2. Branches and history

```
1aa4ebc initial ─ … ─ PR#1..#8 (phase branches, all merged + deleted, D-040) ─ 8f6a72d ─ f9cdaba  ← main, origin/main
                                                                                       └─ 7f0c90a Phase 7 ─ 1073579 "Minor Fix"  ← origin/feature/phase7-per-current-models
```
* `main`: 23 commits. Up to PR #8 the work went through per-phase feature branches and PRs. After D-040 (2026-11-06) the rule became "single branch `main`, no PRs".
* The Phase 7 branch therefore **contradicts D-040 / CLAUDE.md**. That is fine as a review vehicle, but it needs a merge decision.
  "Minor Fix" only touches one line each in CHANGES.md and PROJECT_STATUS.md.
* There is **no local tracking branch** for Phase 7. Use `git switch -c phase7 origin/feature/phase7-per-current-models` to inspect it.
* Gotcha: on that branch, `docs/DECISIONS.md` was converted from **CRLF to LF**, so `git diff` shows the whole file as changed.
  The real change is only D-039 (relabelled) plus D-041 to D-044 (`git diff -w` shows it).

---

## 3. Repo map (main)

| Path | What it is |
|---|---|
| `CLAUDE.md`, `docs/` | Project memory: PROJECT_CONTEXT (requirements + Q1-Q17 + assumptions A1-A4), IMPLEMENTATION_PLAN, PROJECT_STATUS, DECISIONS (D-001..D-040), TEAM_WORKFLOW |
| `context/` | Frozen inputs: assignment PDF, annotated TA slides, 11 PTM model cards (only `22nm_LP.pm` is used), TA example netlist, anonymised chat |
| `config/project.yaml` | All assignment numbers: VDD, ranges, Lmin = 22 nm, Ldiff = 44 nm, the SPICE options, seed 20261105, split 70/15/15, I_FLOOR 1e-15 |
| `src/dvdml/` | Library (≈1,000 lines), §5 |
| `scripts/` | Numbered pipeline `00`..`09`, the `01b/05b/05c` extension, and `12-14` for the report |
| `data/transistor/` | **Deliverable 1**: 4 × 10,000-row CSVs + generation log |
| `data/transistor_extra/` | 4 × 30,000 extra training rows (gz), Phase 3b |
| `data/splits/` | Fixed train/val/test indices (npz) |
| `data/gates/` | `corners.csv` (200 PVT corners) and `gate_spice.csv` (3,600 runs) |
| `data/circuit/` | `circuit_spice.csv` (51,200 runs) |
| `models_saved/` | **Deliverable 5**: the 4 headline models (= `models_10k/`) |
| `models_enlarged/`, `models_selected/` | Phase 3b extension |
| `netlists/` | **Deliverable 2**: example single-FET, gate and circuit netlists |
| `results/` | data_check, models, gates, circuit (+ `_selected` variants): CSV tables + PNG plots |
| `report/` | LaTeX sources. `report/tables/*.tex` are **generated** by script 12 |
| `dist/` | `report.pdf` (rendered with PyMuPDF, not pdfLaTeX) and the Overleaf zip/bundle |
| `tests/` | 38 test functions (96 cases after parametrisation). ngspice tests auto-skip |

---

## 4. End-to-end flow

```
22nm_LP.pm ──► modelcard.nominals ──► sampling.sample_case ──► netlist.single_transistor_netlist ──► spice.run_netlist (ngspice -b, thread pool)
                                                                                                         │
                         01_generate_transistor_data.py ◄──────── dataset.generate_case (exactly N valid rows) ◄┘
                                     │  data/transistor/*.csv (4 × 10k)
                     ┌───────────────┼──────────────────────────────┐
              02_data_check     03_train_compare_models        (01b extra 30k rows)
       Kirchhoff, distributions, 4 families × grid × 4 cases       │
       3 trend sweeps (SPICE)   on validation → comparison_val     05b refit on 37k → 05c pick per case on val
                                     │                              │
                              04_select_and_evaluate  ─► models_saved/ (headline)      models_selected/ (extension)
                              05_learning_curves                    │
                                     │                              │
   06_gate_spice: corners.csv + 18 cases × 200 corners, each solved twice (mandated + tight) → gate_spice.csv
                                     │
   07_gate_ml: SPICE node voltages → per-transistor (Vd,Vg,Vs,Vb) → route to ON/OFF model → predict currents
               → KCL-consistent composition → leak_ml  vs leak_spice → gate tables, parity plot
                                     │
   08_circuit_spice: 28-NAND2 parity netlist, 256 vectors × 200 corners, cross-checked → circuit_spice.csv
                                     │
   09_circuit_ml: logic propagation → each NAND2's input case → look up its Part-B gate ML leakage at the same corner → sum of 28
                                     │
   12 tables → report/tables/*.tex   13 Overleaf bundle   14 PDF without LaTeX
```

### Phase by phase: logic and finer details

**Phase 1-2: transistor data (`scripts/01`, `02`)**
* `sampling.sample_case(case, n, seed, cfg, nominal, batch)`: the RNG is seeded with `[seed, case_index, batch]`.
  Batch 0 is the main draw. Batches 1..19 replace failed simulations (`dataset.generate_case`), so every CSV has exactly N rows.
  The Phase 3b extra data uses batch 101; Phase 7 edge data uses batch 102.
  Process values are multiplied by U(0.9, 1.1), which keeps the negative sign of PMOS vth0.
* `netlist.single_transistor_netlist`: builds one self-contained netlist per sample.
  * The process parameters of the device under test are substituted into the BSIM4 card with a whole-token regex (`modelcard.set_params`, which errors unless each parameter appears exactly once).
  * It sets `.temp`, gives each of the 4 terminals its own `V` source, uses AD = AS = W·Ldiff and no PD/PS (D-019; an A/B test showed only Ib changes, ~10 %).
  * A `.control op; print i(Vd) i(Vg) i(Vs) i(Vb)` block prints the currents.
* `spice.run_netlist`: runs `ngspice -b` in a temp dir with a 60 s timeout. Currents are parsed with a regex.
  **Sign convention:** terminal current = −I(Vsrc), i.e. positive INTO the device, so Id+Ig+Is+Ib = 0 (verified by smoke tests).
* Throughput: ~77 samples/s with 12 workers, about 2 min per 10k case.
* `02_data_check`:
  * Kirchhoff residual, reported absolute and relative.
  * Histograms of the target magnitudes.
  * Three trend plots from **controlled one-at-a-time SPICE sweeps** (not scatter from the dataset), each with an automatic monotonicity check. All three pass: OFF Id ×~400 from −40 to 125 °C, ×~40 over vth0 ±10 %, Ig ×~30 over toxe ±10 %.
* **Key data finding:** currents span ~10 decades. Below ~1e-15 A the values are BSIM4 floating-point noise.
  For example, PMOS-OFF `ig` is exactly 0 in 84.5 % of rows and otherwise sits on quantised 1.1e-16 steps.
  Hence **I_FLOOR = 1e-15 A** (D-027): metrics count only "resolved" samples, and currents with < 5 % resolved samples are not scored (OFF `ig` in both cases).

**Phase 3: transistor ML (`ml.py`, `metrics.py`, scripts `03`-`05`)**
* Features (`ml.featurize`, 15): log W, 1000/T[K], vdd, vd, vs, vds, vgs, vgd, vbs, vbd, |vth0|, toxe in nm, log ndep, u0, xj in nm.
* Target: **signed log** y = asinh(I / 1e-15) / ln10. This is ≈ sign·log10 above the floor and smoothly linear through 0, so it handles sign changes and 10 decades at once.
  Both x and y are standardised.
* Four families, each a 4-output regressor:
  * `_TorchMLP`: float64, tanh, Adam + cosine LR, keeps the best-validation epoch, then L-BFGS polish rounds that are kept only while validation improves.
    Loss weight 0.02 on currents that are almost pure noise.
  * `_LGBMMulti`: one LightGBM per target, with early stopping.
  * RBF kernel ridge.
  * Polynomial ridge.
* Selection score = 0.5·(median + P95) relative error, macro-averaged over the scored currents, on **validation**.
  **The MLP wins all four cases.**
  Test results (median / P95): NMOS ON 4.1 / 22.7 %, NMOS OFF 1.6 / 20.2 %, PMOS ON 1.9 / 11.3 %, PMOS OFF 4.2 / 22.7 %.
* `05_learning_curves`: the error drops by a third to a half per doubling of data, so it is **not saturated**. This motivated Phase 3b.

**Phase 3b: enlarged training set (`01b`, `05b`, `05c`), assumption A4**
* Training rows = 7k + 30k; validation and test unchanged.
* It improved 3 of the 4 transistor models, but **not** the gate level (6.6 % vs 5.5 % median). NMOS ON picked up a bias of several %, and bias does not average out in a sum.
* `05c` picks per case on validation using score + 2·|bias|. The bias term was added *after* seeing the gate effect, and the report says so openly.
* Decision D-038: the headline stays on the 10k models.

**Phase 4: gates (`gates.py`, `corners.py`, `refsolve.py`, `gate_ml.py`, scripts `06`, `07`)**
* `gates.GATES` is the **single source of truth** for topology and widths. The SPICE netlist builder and the ML side both read it.
  Widths in units of Lmin (A2): INV n1/p2, NAND2 2/2, NOR2 n1/p4. AND2 = NAND2 + INV, OR2 = NOR2 + INV.
* Corners (`make_corners`): 200 draws of VDD, T, one NMOS process draw and one PMOS process draw. Seed `[seed, 777]`. The circuit reuses them by index.
* Gate netlist details:
  * Ground goes through `Vgnd vss 0 dc 0` so the return current can be measured (D-032). Leakage is then measured twice: supply side and ground side.
  * The inputs are ideal sources at exactly 0 or VDD.
  * `.nodeset` provides start values only.
* **Reference cross-check (`refsolve.solve_with_crosscheck`, D-031):** with exactly the mandated tolerances, ngspice converged to *wrong* operating points in 59/3600 runs (e.g. leakage 200× too high or negative) and failed in 66.
  So every run is solved twice: tier 0 with the mandated options, and tier 1 with an extra `.options abstol=1e-15 reltol=1e-9 vntol=1e-12` line appended (the mandated line stays in the file).
  The mandated result is used if the two agree within 1 %; otherwise the tight one is used. This is logged in the `ref_source` column.
* **Leakage definition (A1, D-011):** total current delivered by every source sitting at VDD (the supply plus inputs held at 1). By KCL this equals the current absorbed at 0 V.
* **ML side (`gate_ml.predict_runs`)**:
  1. Map the SPICE node voltages (out, x/y/n) to (Vd, Vg, Vs, Vb) of each device. Inputs are ideal 0/VDD.
  2. Route each device to a model by its gate voltage (D-029): NMOS is ON if Vg > VDD/2, PMOS is ON if Vg < VDD/2.
  3. Predict id/ig/is/ib for every device.
  4. **KCL-consistent composition (A3, D-030), the most important non-obvious idea in the repo.**
     The naive sum of predicted currents at the rails gives ~100 % median error.
     The reason: an ON transistor in a gate sits at Vds ≈ 1e-7 V, and its true channel current equals whatever leakage the blocking (OFF) network lets through. That is tiny, and the ON model cannot resolve it from Vds alone.
     So for every ON device the channel current is treated as an **unknown J**, and its source current becomes is = −J − ig − ib.
     Gate and body currents still come from the models.
     The unknowns are found by least squares on the KCL equations at the internal nodes (`np.linalg.lstsq`).
     Then the leakage is summed at the VDD-level nodes and at the 0 V-level nodes, and the two sums are averaged.
  5. Consequence: **ON-model id/is never enter the leakage.** What matters is ON `ig`, OFF `id/is` and all `ib`.
* Result: median 5.5 %, P95 19.6 %, bias +1.5 %, **mean accuracy 92.8 %**. The worst cases are INV_1, NAND2_11, NOR2_10/11 (~8 % median).

**Phase 5: parity checker (`circuit.py`, scripts `08`, `09`)**
* Architecture: 7 XOR2 in a balanced tree. Each XOR2 is the classic 4-NAND2 XOR (n1 = NAND(a, b), n2 = NAND(a, n1), n3 = NAND(b, n1), y = NAND(n2, n3)).
  That gives **28 NAND2 and 112 transistors**, so every gate maps onto one of the 4 NAND2 Part-B cases.
* SPICE: 51,200 runs, each cross-checked, in resumable chunks of 20 corners. All converged at the mandated options, with the correct logic level in 100 % of runs.
* ML (`09`): propagate the logic values, count how many NAND2 instances fall in each of the 4 input cases for each vector, and compute
  leak_ml = Σ count × (Part-B NAND2 ML leakage at the same corner).
  This **reuses `results/gates/gate_runs_ml.csv`**, so script 07 must be re-run first whenever the models change.
* Diagnostic: summing the isolated-gate *SPICE* leakages reproduces the circuit SPICE to 1e-4. So loading between gates is negligible here, and **circuit error ≈ gate-model error**.
* Errors are corner-systematic: the std of the per-corner error is 9.9 %, but only 0.2 % across vectors.
* Result: median 6.4 %, P95 19.1 %, **mean accuracy 92.5 %**.

**Phase 6: report and reproducibility (`12`, `13`, `14`)**
* Every number in the report comes from the CSVs via `latex.tabular` (script 12), so nothing is hand-typed.
* Script 13 checks `\input`, images and refs, then builds the Overleaf zip.
* Script 14 renders a PDF via PyMuPDF because no LaTeX engine was available. Its fonts and math layout differ from pdfLaTeX.
* Reproducibility check: scripts 01 and 06 were re-run and gave byte-identical outputs. Training (03-05) and script 08 were *not* re-run.

**Phase 7 (feature branch only): getting to 99 %**

Diagnosis (CHANGES.md, D-041/D-043):
1. About 98 % of gate leakage on this card is **gate-oxide tunnelling of the ON devices**. OFF subthreshold leakage is about 2 % and body current about 0.1 %.
   The old 4-output MLP spent equal capacity on ON id/is, which the KCL composition never uses.
2. In gates, every terminal sits **at a rail**, i.e. in a corner of the (Vd, Vs) sampling box, where uniform data is sparse.
   The old model was 2-3× worse there than its average.
3. **BSIM4 scales channel and tunnelling currents with Weff = W − 2·wint** (wint = 5 nm, verified in `22nm_LP.pm`). At W = Lmin that is only 55 % of the drawn W.
   The gate-level width ratio is 2.833, not 2.
4. Single-FET SPICE at the exact gate operating points matches the gate SPICE to < 0.1 %, so the remaining error was in the model.

Fixes:
* `ml_v2.CurrentModel`: one MLP **ensemble per current** (3 seeds, 4×128 tanh, fp32 Adam + fp64 L-BFGS polish).
  * Constant-sign currents (ON ig, all ib) use a log10 target on resolved rows. id and is use the signed log.
  * 6 extra physics features: Vgs/toxe, Vgd/toxe, the two overdrives, vth0/kT, VDD/toxe.
  * Rail-emphasis sample weight 1 + 4·(e(Vd) + e(Vs)).
  * Targets divided by Weff/Lmin.
  * Prediction is pure numpy.
  * `CompositeTransistorModel` keeps the same `predict()` interface, so scripts 07 and 09 run unchanged with `--models-dir models_v2`.
* `01c_generate_edge_data.py`: 4 × 20k **rail-corner** rows (batch 102).
  Vd and Vs are each 40 % exactly at a rail, 40 % near a rail (0.1·VDD·u²) and 20 % uniform; W is log-uniform.
  Split: 16k train, 2k joins validation, 2k edge holdout.
* Training data = 7k + 25k extra + 16k edge. The extra rows 25k..30k serve as a holdout.
* Stages (gate / circuit mean accuracy):

  | Stage | Gate | Circuit |
  |---|---|---|
  | baseline | 92.8 % | 92.5 % |
  | per-current | 96.6 % | 97.9 % |
  | + Weff | 97.6 % | 97.8 % |
  | **+ edge data** | **99.65 %** | **99.73 %** |

  Gate median error 0.19 %, P95 1.2 %, max 5.7 %. Every one of the 18 cases is ≥ 99.4 %. Circuit P95 0.79 %.

---

## 5. Library module cheat-sheet (`src/dvdml/`)

| Module | Key API | Notes |
|---|---|---|
| `config.py` | `load_config()`, `model_path()`, `REPO_ROOT` | YAML loader |
| `modelcard.py` | `split_cards`, `get_param`, `set_params`, `nominals` | Whole-token regex, so `xj` never matches `xjbvs` |
| `sampling.py` | `CASES`, `sample_case`, `gate_body_voltages` | Seed `[seed, case_idx, batch]` |
| `netlist.py` | `single_transistor_netlist` | DUT card gets the sampled params; the other card stays nominal |
| `spice.py` | `run_netlist`, `parse_source_currents`, `terminal_currents`, `ngspice_exe` | `NGSPICE_EXE` env var overrides `cfg.spice.exe` |
| `dataset.py` | `simulate_samples` (thread pool), `generate_case` | Threads are enough because the work runs in subprocesses |
| `metrics.py` | `I_FLOOR`, `to/from_signed_log`, `summarize`, `macro` | "resolved" = \|true\| > 1e-15 |
| `ml.py` | `featurize`, `TransistorModel`, `_TorchMLP`, `_LGBMMulti`, `GRIDS` | `predict(df)` → DataFrame id/ig/is/ib in A |
| `corners.py` | `make_corners` | 200 corners, shared n_/p_ draws |
| `gates.py` | `GATES`, `gate_netlist`, `parse_values`, `leakage_from_values`, `leakage_ground_side`, `node_voltages`, `FALLBACK_OPTIONS` | One topology definition feeds both SPICE and ML |
| `refsolve.py` | `solve_with_crosscheck` | Mandated vs tight solve, 1 % agreement rule |
| `gate_ml.py` | `transistor_rows`, `route`, `predict_runs` | Naive sums + KCL composition |
| `circuit.py` | `INSTANCES`, `logic_values`, `instance_cases`, `circuit_netlist` | 28 NAND2 |
| `latex.py`, `plots.py` | Table/plot helpers | |
| `ml_v2.py` *(branch)* | `physics_features`, `edge_weight`, `CurrentModel`, `CompositeTransistorModel`, `MODES` | Pure-numpy inference |

---

## 6. Assumptions and decisions you should know about (not TA-confirmed)

| ID | Assumption | Why it matters |
|---|---|---|
| A1 / D-011 | Leakage = current from all VDD-level sources (supply + inputs at 1) | Includes the gate-tunnelling current drawn from the input drivers |
| A2 / D-012, D-029 | Widths INV 1/2, NAND2 2/2, NOR2 1/4 ×Lmin; ON/OFF routing by Vg vs VDD/2 | Gate results depend directly on these |
| A3 / D-030 | KCL composition instead of a plain sum | The plain sum gives ~100 % error. This is the method's core, and it should be defended in the report/viva |
| A4 / D-034, D-037 | Training data beyond 10k rows | The PDF allows "increased or decreased as needed". Phase 7 depends on it heavily (48k rows, a third of them non-uniform) |
| D-031 | Tight-tolerance cross-check of the SPICE reference | Deviates from "literal mandated tolerances" in 3.5 % of gate runs |
| D-035 | Parity = 28 NAND2 | Any of the 5 allowed gates would do; NAND2 converged most robustly |
| Q7 | "Internal node voltages from both": the ML side just copies the SPICE voltages | The ML never estimates node voltages itself (see improvement I-4) |

---

## 7. Review findings: issues and risks (ordered by importance)

1. **Phase 7 is unmerged and the report still shows 92.8 %.** The single biggest gap. It needs a D-044 decision, then a re-run of scripts 12/13/14 and new text in report sections 3-7.
2. **Phase 7 trade-off at transistor level (deliverable 5).** On the uniform test split, `models_v2` NMOS-ON id/is are much worse than Phase 3: median 12.7 / 14.7 % with **+22 % bias** on id and P95 ~100 %, vs 5.6 / 5.2 % before.
   The macro median for NMOS ON goes 4.1 % → 7.1 %.
   This is harmless for leakage (KCL ignores ON id/is), but deliverable 5 asks for test errors of the "four saved model files", so a reviewer will see a regression there.
   Options: ship different models per deliverable, or give ON id/is the 3-member ensemble too.
3. **Soft evaluation leakage in Phase 7, acknowledged in D-043/D-044.** No gate or circuit value entered training. But the *design* (Weff, rail emphasis) was found by looking at gate-level errors (the 2.833 vs 2.70 ratio).
   Weff is physics from the model card, so it is defensible. The rail sampling uses only "logic nodes sit at rails".
   Still, be ready to explain this to the TAs.
4. **Stale and contradictory docs.**
   * `CLAUDE.md:23,29,45` still say the folders and scripts "do not exist yet" and "no implementation until approved".
   * `docs/IMPLEMENTATION_PLAN.md` header still says "PROPOSED - not approved".
   * `docs/PROJECT_STATUS.md:63-64` still lists Phase 3b as "in progress".
   * On the branch, PROJECT_STATUS line 6 says both "target reached" and "target NOT reached".
5. **Platform assumptions.**
   * Every run instruction is Windows-only (`.venv\Scripts\python.exe`, `set NGSPICE_EXE=...`, `ngspice_con`).
   * `05d_train_per_current.py` defaults to `--device cuda`, which does not exist on a Mac. Apple MPS has no float64, and the L-BFGS polish needs it, so use `--device cpu`.
   * This Mac has Python 3.13 (Anaconda), no torch and no ngspice.
6. **Hard-coded constants in `ml_v2.py`** (branch, lines 25-26): `LMIN = 22e-9`, `WINT = 5e-9`. They belong in the config, or `wint` should be read from the model card with `modelcard.get_param`. This breaks the repo's own "no magic numbers" rule.
7. **`ml_v2` "log" mode sign** (branch line 100) is a single median sign per current. That is fine only if the current never changes sign. True for the chosen currents today, but nothing checks it. A guard or test would catch a future regression silently flipping sign.
8. **Code-quality nits (main)**
   * `gate_ml.py:71-76`: `rail_sums` uses `terminals_keys`, which is defined *after* the function. It works through the closure but is fragile. Each run also does its own Python-loop `lstsq`, which is slow but fine at 3,600 runs.
   * `summarize()` is copy-pasted in `07`, `09` and (as `stats`) `05f`.
   * `circuit._x_guess` duplicates part of `gates._nodeset_guess`.
   * `scripts/02_data_check.py:28` uses `FLOOR = 1e-16` while the rest of the repo uses `I_FLOOR = 1e-15` (D-027). It only affects the data-check table.
   * `09_circuit_ml.py:59` builds lookups with a Python list comprehension over 51,200 rows; a pandas merge would be cleaner and faster.
   * `ml.GRIDS` is tiny (2 MLP configs, 2 LightGBM configs), so the "4 families compared" table slightly favours the MLP, which got the most engineering.
9. **Reproducibility gaps.** Training (scripts 03-05, 05b, 05d) was never re-run from scratch, and multithreaded float sums can differ in the last digits.
   Script 08 (30 min) was not re-run either. Phase 7 training takes ~2.5 h on a GPU.
10. **Repo weight.** Big binaries are committed: datasets, 4 model dirs, `dist/` with a duplicate of `report/`, and on the branch ~15 MB of `models_v2` plus 51k-row result CSVs.
    That is acceptable for a course repo, but `dist/report_overleaf/` duplicates `report/` and has to be regenerated every time, or it drifts.

---

## 8. Improvement backlog (my suggestions, roughly by value/effort)

| # | Idea | Why | Effort |
|---|---|---|---|
| I-1 | **Decide D-044, merge Phase 7 (fast-forward), update the report** (sections 3-7, tables via script 12, re-render 13/14). Keep the 10k models as the "specified-setting baseline" and present both | The 99 % result is the deliverable that matters | M |
| I-2 | Fix deliverable 5 for `models_v2`: give ON id/is the same 3-member ensemble (and maybe edge data), or report the per-current choice explicitly | Removes the visible transistor-level regression | M (GPU hours) |
| I-3 | Clean the docs: CLAUDE.md "not created yet" lines, IMPLEMENTATION_PLAN status, PROJECT_STATUS "in progress" and the contradiction on the branch; normalise line endings (`.gitattributes` with `* text=auto`) | Stops future sessions and teammates from being misled | S |
| I-4 | Close the "node voltages from both" gap (Q7): solve the internal node voltages from the ML currents (Newton/KCL on x, y, n with the transistor models) instead of copying the SPICE values. Report the ML-predicted node voltages next to the SPICE ones | The PDF literally asks for both. It also makes the ML pipeline independent of SPICE node data, a strong report point | M-L |
| I-5 | Cross-platform run instructions + `Makefile`/`run_all.py` (`--device auto`: cuda → cpu), Python 3.12 venv on macOS, `brew install ngspice` | Lets the rest of the team (this Mac included) reproduce | S |
| I-6 | Move `LMIN`/`WINT` into config / read `wint` from the card; add a sign-consistency assertion in `CurrentModel.fit` | Robustness | S |
| I-7 | Deduplicate `summarize`; vectorise the gate KCL solve and the circuit lookup | Maintainability, speed | S |
| I-8 | Fair model comparison for Phase 7: also run LightGBM / kernel ridge on the per-current + Weff + edge setup (same targets and features), so the "4 types × 4 cases" table reflects the final method | The report's "reason for final choice" becomes stronger | M |
| I-9 | Error analysis beyond aggregates: errors vs T, vth0, VDD for `models_v2` (the plots exist in `results/gates_v2/gate_error_vs_corner.png`); explain the remaining INV_0 / INV_1 / NOR2_10 worst cases (~0.4 % median, max 5.7 %) | Required report section "Error analysis" | S-M |
| I-10 | Uncertainty from the ensemble spread (3 seeds), as a confidence band on the predicted leakage | Cheap, nice report addition | S |
| I-11 | Learning curve for Phase 7 (how much edge data is actually needed) | The PDF's "smallest dataset possible" goal | M |
| I-12 | Full clean-run reproducibility check including training, documented runtimes | Deliverable 9 | M-L |

---

## 9. How to run it on this Mac (untested here)

```bash
brew install ngspice                         # BSIM4 level 54 is built in; check: ngspice -v
python3.12 -m venv .venv && source .venv/bin/activate   # repo targets 3.12; this Mac has 3.13 (Anaconda) by default
pip install -r requirements.txt torch        # torch is missing from main's requirements.txt (added on the Phase 7 branch)
export NGSPICE_EXE=$(which ngspice)
python scripts/00_check_env.py
python -m pytest -q                          # ngspice-dependent tests skip if ngspice is missing
# Prediction-only paths (07, 09) need no ngspice: they read the committed CSVs + models.
python scripts/07_gate_ml.py                 # reproduces results/gates from models_saved/
# Phase 7 branch: python scripts/07_gate_ml.py --models-dir models_v2 --out-dir results/gates_v2
# Training on Mac: scripts/05d ... --device cpu  (no CUDA; MPS lacks float64)
```
Note: the ngspice 47 build used on Windows was the official KLU build. A Homebrew ngspice may differ in the last digits.
Datasets were shown bit-identical only between the two Windows machines.

---

## 10. Quick numbers reference

| | main headline (`models_saved`) | Phase 7 (`models_v2`, branch) |
|---|---|---|
| Gate: mean accuracy / median / P95 / max / bias | 92.8 % / 5.5 % / 19.6 % / 59 % / +1.5 % | 99.65 % / 0.19 % / 1.2 % / 5.7 % / +0.03 % |
| Circuit: mean accuracy / median / P95 / max | 92.5 % / 6.4 % / 19.1 % / 46 % | 99.73 % / 0.19 % / 0.79 % / 1.6 % |
| Transistor test macro median (NMOS ON / NMOS OFF / PMOS ON / PMOS OFF) | 4.1 / 1.6 / 1.9 / 4.2 % | 7.1 / 1.1 / 2.7 / 1.9 % |
| ON `ig` test median (NMOS / PMOS) | 2.8 % / 1.1 % | 0.59 % / 0.16 % |
| Training rows per case | 7,000 | 48,000 (7k + 25k uniform + 16k rail-corner) |
