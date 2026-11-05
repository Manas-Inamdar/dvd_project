# CLAUDE.md - dvd_project

## Who/what
* User = **Manas Inamdar** (address him as Manas). The Claude account belongs to a teammate - do not confuse identities, and never
  use the account e-mail for commits or anything else.
* 4-person university course project (Digital VLSI Design): **ML-driven PVT-variation-aware leakage estimation**.
* Our assignment: model file **22nm_LP**, nominal **VDD = 1 V**, test circuit **8-bit parity checker**, L = 22 nm, W = 1-8 x Lmin.

## READ FIRST, EVERY SESSION
1. `docs/PROJECT_STATUS.md` (where we are) -> 2. `docs/PROJECT_CONTEXT.md` (requirements, open questions) ->
3. `docs/IMPLEMENTATION_PLAN.md` (roadmap) -> `docs/DECISIONS.md` and `docs/TEAM_WORKFLOW.md` when relevant.
Then continue from the last recorded state. Update PROJECT_STATUS.md after every meaningful step.

## One-paragraph summary
Simulate single NMOS/PMOS (ON/OFF = 4 cases) in SPICE with random PVT -> 4 CSVs (10,000 rows) -> train/compare >= 4 ML techniques per case,
keep the best (4 final models predicting Id, Ig, Is, Ib) -> predict leakage of INV/NAND2/NOR2/AND2/OR2 (18 input cases x 200 corners)
using only those models + SPICE-recorded internal node voltages -> compose the 8-bit parity checker from gate models -> compare with SPICE.
Deliverables list: `docs/PROJECT_CONTEXT.md` section 6. Assignment PDF is authoritative: `context/DVD_ML_PROJECT.pdf`.

## Repository structure
* `context/` frozen inputs (assignment PDF, TA slides, models, example netlist, anonymized chat, specs). Do not edit except to add sanitized material.
* `docs/` persistent project memory (the six documents above).
* Planned (not created yet): `config/ src/dvdml/ scripts/ netlists/ data/ models_saved/ results/ report/ tests/` (see IMPLEMENTATION_PLAN section 1).

## Hard rules
* **Privacy**: never commit WhatsApp screenshots/images, phone numbers, personal names from chats, credentials, absolute personal paths.
  New chat context -> anonymized text only. Repo must be private while it holds course material (check with `gh repo view --json visibility`).
* **Git**: `main` stable; feature branches (`feature/pN-topic`); no direct pushes to main; meaningful commits; never force-push shared branches;
  commits end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. Ask before pushing, deleting source material or other irreversible actions.
* **No implementation until Manas approves the plan** (status: see PROJECT_STATUS.md).
* Do not invent requirements. Unknowns go to `PROJECT_CONTEXT.md` section 11 with a proposed default; confirm "ASK" items with TAs.
* Gate/circuit SPICE data is evaluation-only (never training data). Fixed seeds everywhere. All netlists need
  `.options gmin=1e-18 abstol=1e-18 reltol=1e-6 vntol=1e-9`; single-transistor netlists give every terminal its own voltage source; add AD = AS = W x Ldiff.
* Be honest: report failing tests and unverified results as such; verify outputs, do not assume.
* Explain technical decisions in beginner-friendly language; push back if a suggestion is technically wrong.

## Conventions
* Python 3.12, code in `src/dvdml/`, numbered scripts in `scripts/` runnable in order, tests with pytest, config in `config/project.yaml`.
* Terminal currents are positive INTO the device (Id+Ig+Is+Ib = 0) - see DECISIONS D-006.
* Units: SI in code (A, V, m, K only where required; temperature in degC as in SPICE `.temp`).

## How to run / test
* Env (Windows): `python -m venv .venv` then `.venv\Scripts\python.exe -m pip install -r requirements.txt` (pandas is pinned: Smart App Control blocks pandas 3.x binaries on the dev PC).
* Simulator: ngspice 47 (not installed permanently yet; set `NGSPICE_EXE` to `ngspice_con.exe`). Check: `.venv\Scripts\python.exe scripts/00_check_env.py`.
* Tests: `.venv\Scripts\python.exe -m pytest -q` (smoke tests auto-skip without ngspice).
* Pipeline scripts `scripts/01_..` to `12_..` do not exist yet (Phase 2+); they will run in numbered order.
