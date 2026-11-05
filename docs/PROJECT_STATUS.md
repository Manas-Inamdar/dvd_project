# PROJECT_STATUS - Living status (update after every meaningful step)

Last updated: 2026-11-06 (Session 1, Phase 2 complete).

## Current phase
**Phase 2 - Transistor datasets and data check: COMPLETE** (branch `feature/p2-datasets`, stacked PR). Next: **Phase 3 - ML models**, which needs one design decision about noise-floor targets (see Findings 8-9 and D-021/D-024).

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

- [x] Phase 2 (2026-11-06):
  - `scripts/01_generate_transistor_data.py`: four datasets `data/transistor/{nmos_on,nmos_off,pmos_on,pmos_off}.csv`, **10,000 valid rows each, 0 failed simulations**, columns exactly as the assignment, ~125 s per case (8.5 min total), seed 20261105, simulator ngspice-47 (recorded in `generation_log.json`). Example netlists in `netlists/single_transistor/`.
  - `scripts/02_data_check.py`: Kirchhoff check (`results/data_check/kirchhoff.csv|md`), target distributions (`distributions.png|csv`), three trend plots + automatic checks (`trend_*.png`, `trend_checks.json`).
  - Trend checks all PASS: |OFF Id| rises monotonically with T (x415 NMOS / x389 PMOS from -40 to 125 C); |OFF Id| falls monotonically with |vth0| (x46 / x35 across +/-10 %); |Ig| falls monotonically with toxe (x30 / x32 across +/-10 %).
  - `tests/test_transistor_data.py`: schema, ranges, fixed Vg/Vb per case, Kirchhoff where currents are resolvable, generation log.

## Findings from the first real simulations (important for Phases 2-3)
1. **Speed is fine** (see 1.3).
2. **Label noise floor in OFF cases.** With the mandated `gmin=1e-18 abstol=1e-18 reltol=1e-6 vntol=1e-9`, 30-40 % of NMOS/PMOS OFF samples differ by >1 % from a run with tight tolerances (`gmin=abstol=1e-22, reltol=1e-9`), up to thousands of times - but only where the true current is below ~1e-17 A (Vds near 0 / deep cut-off). ON cases are clean (median difference 0, max 6e-6). Source currents also show solver quantisation at ~1e-16..4e-16 A. The mandated settings stay the reference (gate/circuit references use them too), but plain relative error on per-transistor OFF currents will be dominated by these tiny currents. See DECISIONS D-021 (error metrics with a noise floor) and Q5/Q13.
3. **Kirchhoff check**: relative residual |sum|/max|I| median 4e-11 (NMOS OFF) to 3e-3 (PMOS OFF); large only when all currents are ~1e-18 (noise floor). Report absolute and relative residual (D-021).
4. **toxe works**: Ig changes ~30x for toxe +/-10 % even though ngspice prints "toxe, toxp and dtox all given and toxe != toxp + dtox; dtox ignored" for non-nominal toxe. The trend plot will confirm.
5. **PD/PS**: adding PD=PS=W+2*Ldiff changes Ib by ~10 % at the 1e-12 A level (NMOS OFF, 125 C, Vd=1 V) and nothing else - much smaller than feared; keep AD/AS only (D-019) and ask TAs.
6. BSIM4 instance currents `@m1[ig]/[is]/[ib]` are not available in this ngspice build; only source currents are usable (consistent with the assignment's "own voltage source per terminal").
7. Observed magnitudes (median |I|): ON: id ~1e-6..5e-7 A, ig ~1e-12, ib ~1e-14; OFF: id ~5e-15, ig ~1e-20 or exactly 0, ib ~4e-16 -> targets span ~10 decades and `ig` is sometimes exactly 0 (needs special handling in log-space models).

8. **Kirchhoff on the real datasets** (|id+ig+is+ib|, `results/data_check/kirchhoff.csv`): NMOS OFF residual is tiny everywhere (max 5e-21 A absolute, 5e-10 relative). ON cases: median relative residual 2e-10, p95 2e-4 (NMOS) / 1e-4 (PMOS); the worst samples are those with near-zero gate overdrive where all four currents are ~1e-15 A or less. PMOS OFF: relative residual is large (median 1e-2, p95 1.6) but the ABSOLUTE residual is tiny (median 3e-17 A, max 1.8e-15 A) because the currents themselves are ~1e-16 A or less. Conclusion: the netlists conserve current wherever currents are above ~1e-15 A.
9. **Some targets are numerical noise, not physics.** Distributions (`results/data_check/distributions.png`): PMOS OFF `ig` is exactly 0 in 84.5 % of rows and otherwise sits on a few discrete values (1.1e-16, 2.2e-16, 4.4e-16, ... = double-precision rounding steps); NMOS ON `ig` is exactly 0 in 7.5 %, and NMOS ON `ig` / PMOS ON `ib` show quantised spikes near 1e-16..1e-15 A. A test with the TA-style "0 V series source" topology gave the identical quantised values, and tight solver tolerances also reproduce them, so this is arithmetic noise inside the BSIM4 evaluation (true value ~0), not a netlist artifact or the mandated tolerances. NMOS OFF `ig` (median 2.5e-21 A) is clean. About 33 % (NMOS OFF) and 29 % (PMOS OFF) of rows have max|I| below 1e-16 A. These cannot be predicted by any model; they matter for the gate sum only at the ~1e-16 A level against ~1e-14 A totals. Also: in "ON" cases Vg is fixed at VDD but Vs is uniform in [0, VDD], so ~0.2-0.3 % of ON rows have almost no gate overdrive (max|I| < 1e-16 A).
10. Orders of magnitude: ON `id`/`is` span ~1e-18..1e-4 A (median ~1e-6), OFF `id`/`is` ~1e-20..1e-10 (median ~2e-15). Signs: id/is negative in ~50 % of ON rows (Vd/Vs swap), ib negative everywhere in NMOS cases, sign of `ig` is nearly constant per case except PMOS OFF.

## In progress
- [ ] Review of PRs by Manas.

## Remaining (next)
- [ ] Phase 3+ (see IMPLEMENTATION_PLAN.md).
- [ ] Manas: send TAs the ASK questions in PROJECT_CONTEXT section 11 (Q1, Q2, Q3, Q5, Q6, Q7).
- [ ] Merge PR #1 (docs/context) and the Phase 1 PR when Manas is happy.

## Git state
| Item | Value |
|---|---|
| Remote | `origin` = https://github.com/Manas-Inamdar/dvd_project.git (PRIVATE) |
| Branches | `main` (1 commit), `initial-context` (PR #1), `feature/p1-spice-plumbing` (PR #2, base initial-context), `feature/p2-datasets` (Phase 2, stacked on p1) |
| Commit identity | repo-local: Manas Inamdar + GitHub noreply email |

## Known bugs / blockers
* No blockers for Phase 2. Resolved: ngspice execution (permission granted by Manas), Smart App Control (did not affect ngspice; pandas 3.x pinned away).
* Open TA questions Q1/Q2/Q6 (affect Phase 4-5, not Phase 1-3).
* Label noise floor in OFF cases (see Findings 2) - a metric/design issue, handled in Phase 3 (D-021).

## Tests performed and results
| Test | Result |
|---|---|
| Phase 0 checks (clone, remote, duplicate PDFs, metadata strip, privacy scan, `.gitignore` for screenshots) | all PASS |
| `pytest` full suite (sampler, model-card override, netlist rules, parser, dataset/failure handling, 4 real-ngspice smoke tests, 8 dataset validation tests on the real CSVs) | **28 passed** |
| Real-ngspice random-sample runs (30 x 4 cases, 60 x 4 tolerance study, 2 x 300 benchmark, misc.) | 0 failures in ~1100 runs |
| Tolerance study (mandated vs tight) | see Findings 2 |
| Throughput benchmark | 77 samples/s (12 workers); full generation 8.5 min for 40,000 rows |
| Data check: Kirchhoff, distributions, 3 trend plots with automatic monotonicity checks | trends PASS; Kirchhoff OK above ~1e-15 A; noise-level targets identified (Findings 8-9) |
| TA example netlist on 22nm_LP | runs, prints currents - PASS |

## Immediate next steps
1. Manas: review/merge PR #1, PR #2 (Phase 1) and the Phase 2 PR (or say continue).
2. Claude: Phase 3 on branch `feature/p3-ml-models`: fixed-seed 70/15/15 split, preprocessing (sign + log10|I| with a floor for noise-level targets, D-024), 4 model families per case, comparison table, best model, test report.
3. Manas: send the TA questions (Q1, Q2, Q3, Q5, Q6, Q7); in particular Q5 (metric definition) now matters because of Finding 9.

## Session log
* 2026-11-05 Session 1: setup, sanitization, understanding, documentation, plan.
* 2026-11-06 Session 1 (cont.): screenshots deleted, repo private, `initial-context` pushed + PR #1, Phase 1 scaffold written and unit-tested; blocked on running ngspice.
* 2026-11-06 (cont.): ngspice 47 installed and verified, Phase 1 completed, first findings about the numerical noise floor recorded.
* 2026-11-06 (cont.): Phase 2 done: 4 datasets x 10,000 rows, Kirchhoff + trend checks, noise-floor targets identified.
