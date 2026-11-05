# PROJECT_STATUS - Living status (update after every meaningful step)

Last updated: 2026-11-06 (Session 1, Phase 1 complete).

## Current phase
**Phase 1 - Environment and SPICE plumbing: technically COMPLETE** (branch `feature/p1-spice-plumbing`, PR pending review). Plan + docs approved by Manas on 2026-11-06.
Next: Phase 2 (transistor datasets + data check). Manas has given broad permission to continue.

## Completed
- [x] Phase 0: repo, sanitized context, anonymized transcript (screenshots deleted after confirmation), repo private, `initial-context` pushed, **PR #1** open (docs/context) - not merged yet.
- [x] Docs written and approved: CLAUDE.md, PROJECT_CONTEXT, IMPLEMENTATION_PLAN, DECISIONS, TEAM_WORKFLOW, this file.
- [x] Phase 1:
  - 1.1 Environment: project venv `.venv/` (git-ignored): numpy, scipy, pandas 2.3.3, scikit-learn, matplotlib, pyyaml, joblib, lightgbm, pytest. **ngspice 47 (official 64-bit build, KLU) installed at `C:\Users\HP\tools\ngspice47`, user env var `NGSPICE_EXE` set** (new terminals pick it up). Windows Smart App Control did NOT block ngspice. PyTorch not installed (not needed yet).
  - 1.2 Spike: the TA example netlist runs unmodified on `22nm_LP.pm` (include path aside).
  - 1.3 Injection approach decided: per-sample self-contained netlists, run in a thread pool of ngspice processes. Benchmark: ~77 samples/s with 12 workers -> **10,000 samples in ~2.2 min** (serial: ~80 ms/run). The `altermod` approach is not needed.
  - 1.4 Netlist builder + parser + sign convention **verified**: 4 smoke tests pass (NMOS ON current enters drain/leaves source, Kirchhoff, PMOS ON, OFF leakage grows with T).
  - 1.5 Failure handling: `dataset.generate_case` returns exactly N valid rows, replacing failed sims from fresh deterministic batches (unit-tested with a fake simulator; 0 real failures in ~1100 real runs so far).
  - Code: `config/project.yaml`, `src/dvdml/{config,modelcard,sampling,netlist,spice,dataset}.py`, `scripts/00_check_env.py`, tests.

## Findings from the first real simulations (important for Phases 2-3)
1. **Speed is fine** (see 1.3).
2. **Label noise floor in OFF cases.** With the mandated `gmin=1e-18 abstol=1e-18 reltol=1e-6 vntol=1e-9`, 30-40 % of NMOS/PMOS OFF samples differ by >1 % from a run with tight tolerances (`gmin=abstol=1e-22, reltol=1e-9`), up to thousands of times - but only where the true current is below ~1e-17 A (Vds near 0 / deep cut-off). ON cases are clean (median difference 0, max 6e-6). Source currents also show solver quantisation at ~1e-16..4e-16 A. The mandated settings stay the reference (gate/circuit references use them too), but plain relative error on per-transistor OFF currents will be dominated by these tiny currents. See DECISIONS D-021 (error metrics with a noise floor) and Q5/Q13.
3. **Kirchhoff check**: relative residual |sum|/max|I| median 4e-11 (NMOS OFF) to 3e-3 (PMOS OFF); large only when all currents are ~1e-18 (noise floor). Report absolute and relative residual (D-021).
4. **toxe works**: Ig changes ~30x for toxe +/-10 % even though ngspice prints "toxe, toxp and dtox all given and toxe != toxp + dtox; dtox ignored" for non-nominal toxe. The trend plot will confirm.
5. **PD/PS**: adding PD=PS=W+2*Ldiff changes Ib by ~10 % at the 1e-12 A level (NMOS OFF, 125 C, Vd=1 V) and nothing else - much smaller than feared; keep AD/AS only (D-019) and ask TAs.
6. BSIM4 instance currents `@m1[ig]/[is]/[ib]` are not available in this ngspice build; only source currents are usable (consistent with the assignment's "own voltage source per terminal").
7. Observed magnitudes (median |I|): ON: id ~1e-6..5e-7 A, ig ~1e-12, ib ~1e-14; OFF: id ~5e-15, ig ~1e-20 or exactly 0, ib ~4e-16 -> targets span ~10 decades and `ig` is sometimes exactly 0 (needs special handling in log-space models).

## In progress
- [ ] Review of the Phase 1 PR by Manas.

## Remaining (next)
- [ ] Phase 2: script `01_generate_transistor_data.py` (4 x 10,000 rows), Kirchhoff check, 3 trend plots, target-distribution inspection.
- [ ] Phase 3+ (see IMPLEMENTATION_PLAN.md).
- [ ] Manas: send TAs the ASK questions in PROJECT_CONTEXT section 11 (Q1, Q2, Q3, Q5, Q6, Q7).
- [ ] Merge PR #1 (docs/context) and the Phase 1 PR when Manas is happy.

## Git state
| Item | Value |
|---|---|
| Remote | `origin` = https://github.com/Manas-Inamdar/dvd_project.git (PRIVATE) |
| Branches | `main` (1 commit), `initial-context` (pushed, PR #1), `feature/p1-spice-plumbing` (branched from `initial-context`; Phase 1 PR) |
| Commit identity | repo-local: Manas Inamdar + GitHub noreply email |

## Known bugs / blockers
* No blockers for Phase 2. Resolved: ngspice execution (permission granted by Manas), Smart App Control (did not affect ngspice; pandas 3.x pinned away).
* Open TA questions Q1/Q2/Q6 (affect Phase 4-5, not Phase 1-3).
* Label noise floor in OFF cases (see Findings 2) - a metric/design issue, handled in Phase 3 (D-021).

## Tests performed and results
| Test | Result |
|---|---|
| Phase 0 checks (clone, remote, duplicate PDFs, metadata strip, privacy scan, `.gitignore` for screenshots) | all PASS |
| `pytest` full suite (sampler, model-card override, netlist rules, parser, dataset/failure handling, 4 real-ngspice smoke tests) | **19 passed** |
| Real-ngspice random-sample runs (30 x 4 cases, 60 x 4 tolerance study, 2 x 300 benchmark, misc.) | 0 failures in ~1100 runs |
| Tolerance study (mandated vs tight) | see Findings 2 |
| Throughput benchmark | 77 samples/s (12 workers) |
| TA example netlist on 22nm_LP | runs, prints currents - PASS |

## Immediate next steps
1. Manas: review/merge PR #1 and the Phase 1 PR (or just say continue).
2. Claude: Phase 2 on branch `feature/p2-datasets`.
3. Manas: send the TA questions.

## Session log
* 2026-11-05 Session 1: setup, sanitization, understanding, documentation, plan.
* 2026-11-06 Session 1 (cont.): screenshots deleted, repo private, `initial-context` pushed + PR #1, Phase 1 scaffold written and unit-tested; blocked on running ngspice.
* 2026-11-06 (cont.): ngspice 47 installed and verified, Phase 1 completed, first findings about the numerical noise floor recorded.
