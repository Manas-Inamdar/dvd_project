# DECISIONS - Technical and process decisions log

Format: ID | status (Accepted / Proposed / Rejected) | decision | alternatives | reason. Add new entries at the bottom; never rewrite history (supersede instead).

## D-001 | Accepted | Branching: `main` is stable; work on feature branches; initial upload on `initial-context`
Alternative: commit straight to `main`. Reason: Manas's requirement; protects a stable baseline in a 4-person project.

## D-002 | Accepted | WhatsApp screenshots are NOT stored in the repo; replaced by an anonymized transcript
Alternatives: commit the screenshots; blur them. Reason: they contain names and phone numbers. Text keeps all technical content (`context/whatsapp_messages.txt`).
Originals are deleted only after Manas confirms the transcript (see PROJECT_STATUS).

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

## D-016 | Accepted | Do not push to GitHub while the repo is public
Reason: course material + privacy. Repo found PUBLIC on 2026-11-05; waiting for Manas to make it private or explicitly accept publishing.
