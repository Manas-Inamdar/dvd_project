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

## D-011 | Proposed | Gate leakage = total current delivered by all sources at VDD (supply + inputs held high)
Alternatives: supply current only; sum of |I| of all terminals (double counts, as in slide 15's partial equations). Reason: physically total static current; consistent between SPICE and ML. **Needs TA confirmation (Q1).**

## D-012 | Proposed | Gate sizing: INV Wn=1, Wp=2; NAND2 Wn=2, Wp=2; NOR2 Wn=1, Wp=4 (x Lmin)
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
