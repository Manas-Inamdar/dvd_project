# PROJECT_STATUS - Living status (update after every meaningful step)

Last updated: 2026-11-06 (Session 1, Phase 1 started).

## Current phase
**Phase 1 - Environment and SPICE plumbing** (branch `feature/p1-spice-plumbing`). Plan + docs approved by Manas on 2026-11-06.
**BLOCKED on running ngspice** (see Blockers). Everything that does not need the simulator is done and unit-tested.

## Completed
- [x] Phase 0: repo cloned, context sanitized, WhatsApp screenshots transcribed (anonymized) and permanently deleted after Manas's confirmation, repo made private by Manas (verified), `initial-context` pushed, **PR #1** open (https://github.com/Manas-Inamdar/dvd_project/pull/1) - not merged yet.
- [x] Docs written and approved: CLAUDE.md, PROJECT_CONTEXT, IMPLEMENTATION_PLAN, DECISIONS, TEAM_WORKFLOW, this file.
- [x] Phase 1 tasks done without the simulator:
  - task 1.1 (partly): project venv `.venv/` (git-ignored) with numpy, scipy, pandas 2.3.3, scikit-learn, matplotlib, pyyaml, joblib, lightgbm, pytest. PyTorch NOT installed (not needed yet; sklearn MLP/LightGBM are available).
  - ngspice 47 (64-bit, official SourceForge build `ngspice-47_64.7z`, 13.8 MB) downloaded and extracted to the session scratch folder (not installed anywhere permanent).
  - `config/project.yaml`: all assignment parameters in one place.
  - `src/dvdml/`: `config.py`, `modelcard.py` (read nominal values from `22nm_LP.pm`; override vth0/toxe/ndep/u0/xj in a model card), `sampling.py` (Section-4 sampler, VDD first, 4 cases, seeded), `netlist.py` (single-transistor netlist: own source per terminal, required `.options`, AD=AS=W*Ldiff, sampled model card inlined), `spice.py` (ngspice batch runner + output parser + sign convention).
  - `scripts/00_check_env.py` (prints versions incl. simulator).
  - `tests/`: `test_sampling.py`, `test_netlist.py`, `test_spice_smoke.py` (needs ngspice; skipped until available).

## In progress
- [ ] Run ngspice: spike on the TA example (task 1.2), run the smoke tests (task 1.4 acceptance), benchmark parameter-injection approach (task 1.3).

## Remaining (next)
- [ ] Task 1.2 spike, 1.3 benchmark (per-sample netlist in a process pool vs. one ngspice session with `altermod`), 1.5 failure handling/resampling.
- [ ] Phase 2 onward (see IMPLEMENTATION_PLAN.md).
- [ ] Manas: send TAs the ASK questions in PROJECT_CONTEXT section 11 (Q1, Q2, Q3, Q5, Q6, Q7).
- [ ] Merge PR #1 (docs/context) when Manas is happy; Phase 1 gets its own PR.

## Git state
| Item | Value |
|---|---|
| Remote | `origin` = https://github.com/Manas-Inamdar/dvd_project.git (PRIVATE) |
| Branches | `main` (1 commit), `initial-context` (pushed, PR #1), `feature/p1-spice-plumbing` (local, branched from `initial-context`) |
| Commit identity | repo-local: Manas Inamdar + GitHub noreply email |

## Known bugs / blockers
1. **ngspice cannot be run yet.** Claude Code's auto-mode permission check denied executing the downloaded `ngspice_con.exe` ("code from external"). Manas must either (a) approve running it, or (b) install ngspice himself and tell Claude the path (then set `NGSPICE_EXE`, e.g. `setx NGSPICE_EXE "C:\path\to\ngspice_con.exe"`). Possible second hurdle: **Windows Smart App Control is ON** on this PC (registry `VerifiedAndReputablePolicyState = 1`); it already blocked the compiled `pandas 3.1.1` extension (worked around by pinning pandas 2.3.3) and may block the unsigned ngspice binaries. If it does, options: run ngspice inside WSL, or build/obtain a signed build, or turn SAC off (irreversible on Windows 11 - Manas's call, not recommended).
2. `PD`/`PS` (junction perimeters) are not set (chat only mentions AD/AS). With the model's parameters the sidewall junction terms (jswgs 1e-10 A/m x perimeter ~2e-7 m = ~2e-17 A) are ~100x larger than the area term (jss 1e-4 A/m2 x AD ~1e-15 m2 = ~1e-19 A). Body-current accuracy may depend on this; see Q3 in PROJECT_CONTEXT.
3. Open TA questions Q1/Q2/Q6 (they affect Phase 4-5, not Phase 1-3).

## Tests performed and results
| Test | Result |
|---|---|
| Phase 0 checks (clone, remote, duplicate PDFs, metadata strip, privacy scan of whole tree, `.gitignore` for screenshots) | all PASS (details in git history of this file) |
| `pytest` (no simulator): sampler ranges, fixed Vg/Vb per case, reproducibility/independence; nominals read from model file; model-card override touches only the 5 requested parameters (no collateral change to xjbvs, ua, ...); netlist contains required `.options`, own source per terminal, AD/AS, sampled model card; output parser + sign convention | **12 passed** |
| `pytest` smoke tests against real ngspice (NMOS ON conducts, Kirchhoff, PMOS ON, OFF leakage rises with T) | **4 skipped - not run yet** (no simulator access) |
| Sign convention (D-006), convergence at gmin=1e-18 / reltol=1e-6 / vntol=1e-9, whether BSIM4 v4.0 card loads in ngspice 47 | **UNVERIFIED** until ngspice runs |

## Immediate next steps
1. Manas: allow Claude to run the downloaded ngspice (preferred) or install it himself and give the path.
2. Claude: run `scripts/00_check_env.py` and the smoke tests, do the example-netlist spike, benchmark injection approaches, then finish Phase 1 and open its PR.
3. Manas: send the TA questions.

## Session log
* 2026-11-05 Session 1: setup, sanitization, understanding, documentation, plan.
* 2026-11-06 Session 1 (cont.): screenshots deleted, repo private, `initial-context` pushed + PR #1, Phase 1 scaffold written and unit-tested; blocked on running ngspice.
