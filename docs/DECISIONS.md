# DECISIONS - Technical and process decisions log

Format: ID | status (Accepted / Proposed / Rejected) | decision | alternatives | reason. Add new entries at the bottom; never rewrite history (supersede instead).

## D-001 | Accepted | Branching: `main` is stable; work on feature branches; initial upload on `initial-context`
Alternative: commit straight to `main`. Reason: Manas's requirement; protects a stable baseline in a 4-person project.

## D-002 | Accepted | WhatsApp screenshots are NOT stored in the repo; replaced by an anonymized transcript
Alternatives: commit the screenshots; blur them. Reason: they contain names and phone numbers. Text keeps all technical content (`context/whatsapp_messages.txt`).
Originals were deleted on 2026-11-06 after Manas confirmed the transcript.

## D-003 | Accepted | Sanitize third-party files in the repo copy, leave local originals untouched
* PDF metadata (author name) stripped from the repo copy of the annotated slides.
* Absolute `/home/<user>/...` include paths in the example netlist replaced by a redaction comment.
* Team member names removed from `Project_specs.txt` (team number/name and assignment kept).
Reason: public-repo hygiene; costs nothing.

## D-004 | Accepted | Model files taken from the zip (`Model Files-*.zip -> models.zip`), not the tar
The tar lacks `22nm_LP.pm` (our assigned file). Common files are identical (whitespace aside). Only `22nm_LP.pm` is needed by the code.

## D-005 | Accepted | Nominal VDD = 1 V (range 0.9-1.1 V)
Alternatives: 0.95 V (model header), 0.9 V (slide example). Reason: assignment states VDD as assigned by TAs: 1 V.

## D-006 | Proposed | Current sign convention: all terminal currents positive when flowing INTO the device
Reason: matches slide 1 and gives Id+Ig+Is+Ib = 0. In ngspice a source's `I(V)` is positive into its + node, so with + on the transistor node,
`I_terminal = -I(Vsrc)` - **must be verified by the smoke test** before use.

## D-007 | Proposed | Simulator: ngspice (>= 40) with BSIM4 level 54
Alternatives: Xyce, commercial SPICE (unavailable). Reason: the TA example uses ngspice `.control`; free; BSIM4 supported. Pending install and spike (plan task 1.2).

## D-008 | Proposed | Python 3.12 stack: numpy, pandas, scikit-learn, matplotlib, PyTorch or LightGBM
Python 3.12.10 is installed. Pending env check.

## D-009 | Proposed | ML targets: sign + log10|I| (or asinh), inputs scaled; metrics in linear domain
Reason: currents span ~10 decades and change sign; plain MSE on raw current would only fit the largest values. Revisit after looking at the real data (plan 2.5).

## D-010 | Proposed | Four candidate model families per case: MLP, gradient boosting, polynomial/kernel ridge (or SVR), random forest/k-NN
Reason: WhatsApp T3 (>= 4 techniques per case, finalize 1); mix of smooth (MLP, ridge) and tree-based families. Final list after pilot data.

## D-011 | Accepted (team assumption A1, not TA-confirmed) | Gate leakage = total current delivered by all sources at VDD (supply + inputs held high)
Alternatives: supply current only; sum of |I| of all terminals (double counts, as in slide 15's partial equations). Reason: physically total static current; consistent between SPICE and ML. **Needs TA confirmation (Q1).**

## D-012 | Accepted (team assumption A2, not TA-confirmed) | Gate sizing: INV Wn=1, Wp=2; NAND2 Wn=2, Wp=2; NOR2 Wn=1, Wp=4 (x Lmin)
Reason: slide 15 hints (INV P=2/N=1, NAND2 all 2) + NOR2 compensation; all in training range 1-8 x Lmin. **Needs TA confirmation (Q2).**

## D-013 | Proposed | Parity checker = tree of 7 XOR2 cells; each XOR2 composed only of the five allowed gates
Candidates: 4x NAND2 (28 NAND2 total); AND2(OR2, NAND2) (21 cells); INV + 2xAND2 + OR2. Final pick after Phase 4 results show which cells are most accurate.

## D-014 | Accepted | Git identity for commits in this clone (repo-local only)
`user.name = Manas Inamdar`, email = GitHub noreply address of Manas-Inamdar. Global git config untouched. Reason: no identity was configured; the Claude account used belongs to a teammate and must not be the commit author.
Commits made with Claude's help carry a `Co-Authored-By: Claude` trailer.

## D-015 | Proposed | Commit the 4 dataset CSVs and small result tables; do not commit raw SPICE logs or virtualenvs
Reason: CSVs are small (10,000 rows) and are deliverables; `.gitignore` excludes bulk/temporary files.

## D-016 | Accepted | Do not push to GitHub while the repo is public (resolved 2026-11-06: repo is now private)
Reason: course material + privacy. Repo found PUBLIC on 2026-11-05; waiting for Manas to make it private or explicitly accept publishing.

## D-017 | Accepted | Parameter injection by inlining the sampled model card in each netlist
Per-sample netlists contain the full `.model nmos/pmos` cards with vth0/toxe/ndep/u0/xj replaced (regex on whole tokens, unit-tested). Self-contained netlists double as the "example netlists" deliverable.
Alternative: one ngspice session with `altermod`. Not needed: benchmark gives ~77 samples/s with 12 parallel ngspice processes (10,000 samples ~2.2 min).

## D-018 | Accepted | Pin pandas 2.3.3
pandas 3.1.1 compiled extension (`tslib`) is blocked by Windows Smart App Control on the development PC; 2.3.3 works. Pinned in `requirements.txt`.

## D-019 | Proposed | AD/AS only, no PD/PS, until TAs answer (Q3)
Follows the course chat literally. Risk noted in PROJECT_STATUS (sidewall junction term dominates by ~100x with this model). A/B done (2026-11-06): PD/PS changes only Ib, by ~10 % at the 1e-12 A level; keep AD/AS only and ask the TAs.

## D-020 | Accepted | One-sample-per-netlist `.op` runs; printed `i(Vd) i(Vg) i(Vs) i(Vb)` parsed from stdout
Simple and robust; speed to be benchmarked (task 1.3). Terminal current = -I(Vsrc) (D-006, to be verified).

## D-021 | Proposed | Error metrics get an absolute noise floor in addition to the plain relative error
Finding: with the mandated tolerances the OFF-case currents below ~1e-17 A (and quantisation at ~1e-16 A) are solver noise (see PROJECT_STATUS findings).
Plain relative error |pred-true|/|true| would be dominated by such samples although they are irrelevant for leakage (gate leakage ~1e-14 A and up).
Proposal: report BOTH plain relative error and floored relative error |pred-true| / max(|true|, I_floor) with I_floor = 1e-16 A (to be tuned/confirmed), plus R2 on log10|I| for |I| above the floor.
Kirchhoff check reported as absolute residual and relative residual. Needs confirmation of what "accuracy" means (Q5).

## D-022 | Accepted | ngspice 47 installed at C:\Users\HP\tools\ngspice47 (outside the repo); `NGSPICE_EXE` user environment variable points to `bin\ngspice_con.exe`
Source: official ngspice SourceForge build `ngspice-47_64.7z`. Version is recorded by `scripts/00_check_env.py` for the report.

## D-023 | Accepted | Failed simulations are replaced from deterministic extra batches (seed, case, batch), never re-tried with changed settings
So each CSV has exactly N valid rows and the failure count is reported.

## D-024 | Proposed | Handling of noise-level targets in the ML models (Phase 3)
Finding: some targets (PMOS OFF ig/ib, parts of NMOS ON ig, PMOS ON ib, OFF currents below ~1e-16 A) are BSIM4 arithmetic noise, not learnable physics.
Proposal: (1) targets are modelled as sign + log10(max(|I|, I_floor)) with I_floor = 1e-16 A (anything below the floor is "at the floor"), (2) predictions below the floor are reported as 0 / floor, (3) metrics: R2 and median/P95 error computed on samples above the floor, plus the floored relative error of D-021 on all samples, plus the fraction of rows below the floor, so the reader sees exactly what is and is not predictable.
Alternative considered: train on raw currents (dominated by the largest values, poor on 10 decades) - rejected. To be validated empirically in Phase 3 and confirmed by Manas/TAs (Q5).

## D-025 | Accepted | Keep the single-source-per-terminal netlist; TA-style "0 V series source" topology rejected
Tested 2026-11-06: identical quantised values and no improvement, so there is nothing to gain; the assignment's wording (each terminal has its own voltage source) is followed literally.

## D-026 | Accepted | Commit the four dataset CSVs (~11.7 MB total), netlists and data-check results
They are deliverables 1-3 and small enough for Git; they are regenerated bit-for-bit by `scripts/01_*.py` and `02_*.py` (seeded). Raw ngspice logs are not stored.

## D-027 | Accepted | Noise floor I_FLOOR = 1e-15 A (supersedes the 1e-16 A proposal in D-021/D-024)
The quantised arithmetic noise reaches ~9e-16 A, so 1e-16 would still count noise as error. Metrics are computed on resolved samples (|I| > floor); currents with < 5 % resolved samples are not scored; target transform y = asinh(I/floor)/ln10.

## D-028 | Accepted | MLP (PyTorch, float64, tanh) is the MLP implementation; scikit-learn L-BFGS MLP kept only as round-1 reference
Round 1 (sklearn) under-trained and weighted noise-only currents like the others. Fixes: loss weight 0.02 for currents with < 5 % resolved samples, Adam + cosine schedule + L-BFGS polish, best-validation epoch. tanh clearly beat SiLU in tests. Families compared: MLP, LightGBM, kernel ridge (RBF), polynomial ridge. MLP selected in all 4 cases.

## D-029 | Accepted (team assumption A2, not TA-confirmed) | Gate transistors are routed to the ON/OFF model by gate voltage (NMOS ON if Vg > VDD/2, PMOS ON if Vg < VDD/2); widths INV 1/2, NAND2 2/2, NOR2 1/4 x Lmin (= D-012)

## D-030 | Accepted (team assumption A3, not TA-confirmed) | Gate leakage from ML = KCL-consistent composition, not the plain terminal-current sum
Evidence: plain sums have median error ~100 % (ON transistors at Vds ~ 1e-7 V). Method: ON channel current = unknown J (is = -J - ig - ib), gate/body currents from the models, internal-node KCL solved by least squares, summed at the rails; reported value = mean of supply-side and ground-side sums (chosen a priori: both are estimates of the same quantity; median disagreement 0.06 %). The plain-sum baseline stays in the report (Table gate_estimators). Our assumption, not TA-confirmed: the assignment only says "use these predicted currents to calculate the logic gate leakage".

## D-031 | Accepted | Cross-checked SPICE reference (mandated solve vs tight solve)
With exactly the mandated options ngspice gave invalid operating points in 59/3600 gate runs and no convergence in 66. Each run is solved with the mandated options and with an extra later `.options abstol=1e-15 reltol=1e-9 vntol=1e-12` line (gmin unchanged); the mandated result is the reference if the two agree within 1 %, else the tight one. The mandated `.options` line is kept in every netlist. Logged per run (`ref_source`). To be reused in Phase 5. TA question: confirm that a valid operating point is preferred over literal tolerances.

## D-032 | Accepted | 0 V source in the ground rail of gate netlists (node `vss`, source `Vgnd`)
Makes the return current measurable: all source currents sum to zero (Kirchhoff check per run) and gives a second measurement of the leakage. (`gnd` is a reserved alias of node 0 in SPICE, hence `vss`.)

## D-033 | Accepted | Report in LaTeX under report/, tables generated from result CSVs by scripts/12_build_report_tables.py
So that numbers in the report can never go stale or be mistyped; each phase fills its sections (Manas, 2026-11-06).

## D-034 | Accepted (team assumption A4, not TA-confirmed) | Phase 3b: enlarge the transistor datasets
Learning curves are not saturated. The assignment allows increasing the sample count ("number of samples may be increased or decreased as needed"). Plan: ~40,000 samples per case (~9 min simulation per case), retrain, re-evaluate. Deliverable 1 asks for 10,000-row CSVs; both the 10,000-row (first block) and the larger file would be delivered and the report states which one the models use.

## D-035 | Accepted (team assumption) | 8-bit parity checker = balanced tree of 7 XOR2, each XOR2 = 4 NAND2 (28 NAND2, 112 transistors)
Reason: simplest classic XOR from the allowed gates; NAND2 converged robustly in Phase 4 (AND2/OR2 did not); every gate instance maps onto one of the 18 Part-B cases. In the circuit-level ML step each NAND2 instance uses the Part-B record of its input combination at the same corner (assignment step 7: "call the corresponding gate model"). Netlist requirement `.options` line and own-source rules unchanged; MOSFET instance names start with `M_` (SPICE would read `x...` as a sub-circuit).

## D-036 | Accepted | The four former TA questions are settled by OUR assumptions A1-A4 (gate-leakage definition, gate widths, KCL composition, dataset size)
Recorded with justification in docs/PROJECT_CONTEXT.md ("Team assumptions") and report Appendix B. They are assumptions made by the team (Manas's instruction on 2026-11-06: do not investigate further, pick the simplest defensible option, do not create new open questions); they are NOT TA-confirmed facts. D-011, D-012, D-029, D-030 and D-034 are accordingly relabelled.

## D-037 | Accepted | Phase 3b data: base 10,000 rows per case + 30,000 extra training-only rows (A4)
Extra rows: `sample_case(..., batch=101)` stream (independent of batches 0..99 used for failure replacement), stored in `data/transistor_extra/`. Training set = original train split (7,000) + all 30,000 extra rows; validation and test indices are the original ones, so earlier and new results are directly comparable.

## D-038 | Accepted | Headline = models trained on the specified 10,000-row datasets; enlarged-training-set models are a reported extension (A4)
Result of the extension (2026-11-06): refitting the MLPs on 37,000 training rows (7,000 + 30,000 extra) improved the transistor-level test errors of NMOS OFF (P95 20.2 -> 7.7 %), PMOS ON (11.3 -> 6.3 %) and PMOS OFF (22.7 -> 14.6 %), but NOT NMOS ON (median 4.1 -> 7.2 %, systematic bias of several %). A first attempt with 500 epochs was under-trained (NMOS ON worse; gate level 9.7 % median).
Per-case choice between the 10k and the enlarged model uses VALIDATION data only: score = 0.5 (median + P95) + 2 mean|bias| (the bias term, justified because gate/circuit leakage are sums of currents, was added AFTER seeing the gate-level effect of the NMOS ON bias; this is stated openly in the report) -> NMOS ON keeps the 10k model, the other three use the enlarged models ("enlarged-set selection").
Gate level: headline 10k models median 5.5 % / P95 19.6 % / bias +1.5 % / mean accuracy 92.8 %; enlarged selection median 6.6 % / P95 22.6 % / bias -0.5 % / 91.6 %. Circuit: 6.4 % vs 6.8 % median. So more data did NOT improve the gate-level accuracy. Untested hypothesis: gate operating points sit on the edges of the sampled (Vd, Vs) range while validation error is averaged over interior points.
Decision: because the assignment's specified setting is the 10,000-row dataset, the headline numbers (report sections 3-6, deliverables) are those of the 10k models in `models_saved/` and `results/gates`, `results/circuit`; the extension is reported next to them (`models_enlarged/`, `models_selected/`, `results/gates_selected`, `results/circuit_selected`, report Section 3.5). Gate-level data was NOT used to choose between sets; the headline follows the assignment's specified setting. (Both sets are shown so the reader can judge.)
Scripts: 01b (extra data), 05b (refit, non-destructive), 05c (validation-based selection), 07/09 take `--models-dir/--out-dir` and `--gate-runs/--out-dir`.

## D-039 | Proposed (not done) | Further accuracy idea: oversample the edges of the (Vd, Vs) domain in the extra training data
Would address the untested hypothesis of D-038 (gate operating points lie at Vs = 0, Vd = VDD, Vds ~ 0). The specified 10,000-row datasets must stay uniform; only extra training rows could be non-uniform. Not pursued: Manas asked not to over-engineer; the 99 % target remains unmet (headline mean accuracy 92.8 % gates / 92.5 % circuit).
