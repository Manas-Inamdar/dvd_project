# PROJECT_STATUS - Living status (update after every meaningful step)

Last updated: 2026-11-06, Session 1 continued.

## Current phase
**Phase 0 - setup and understanding. Waiting for Manas's review.** No assignment implementation code exists yet (intentionally).

## Completed
- [x] Located local context folder (outside the repo): `...\dvd\project\context` (assignment PDF, annotated slides, model zip/tar, example netlist, specs, 3 WhatsApp screenshots).
- [x] Cloned `https://github.com/Manas-Inamdar/dvd_project` to `...\dvd\project\dvd_project`; remote `origin` verified. Repo had only `README.md` (1 commit on `main`).
- [x] Created local branch `initial-context` (not pushed).
- [x] Read the whole assignment PDF, all 16 pages of the annotated slides (rendered as images), the example netlist, model file `22nm_LP.pm`, specs file, and all 3 WhatsApp screenshots.
- [x] Anonymized WhatsApp transcript written: `context/whatsapp_messages.txt` (no names/phones; items flagged for review inside).
- [x] Sanitized copies of context files placed in the repo `context/` (see list below).
- [x] Privacy scan of files to be committed (see "Tests performed").
- [x] Persistent docs written: `CLAUDE.md`, `docs/PROJECT_CONTEXT.md`, `IMPLEMENTATION_PLAN.md`, `PROJECT_STATUS.md`, `DECISIONS.md`, `TEAM_WORKFLOW.md`.

## In progress
- [ ] Manas reviews the transcript, the understanding and the plan.

## Not done / remaining
- [x] Manas confirmed the transcript (2026-11-06); the 3 original WhatsApp screenshots were permanently deleted from the local context folder. Only the anonymized transcript remains.
- [x] Repo visibility is now **PRIVATE** (verified with `gh repo view` on 2026-11-06).
- [ ] **Push of `initial-context` + PR to `main`**: the first push attempt was blocked by the Claude Code permission classifier; waiting for Manas to allow it or push manually (`git push -u origin initial-context`).
- [x] Local commit on `initial-context` created (NOT pushed). Push + PR to `main` pending repo privacy decision.
- [ ] Ask TAs: Q1 (leakage definition), Q2 (gate widths), Q3 (Ldiff/PD/PS), Q5 (accuracy metric), Q6/Q7 (internal node voltages in Part C / "from both").
- [ ] Phase 1 onward (ngspice install, spike, ...). See IMPLEMENTATION_PLAN.md.

## Git state
| Item | Value |
|---|---|
| Remote | `origin` = https://github.com/Manas-Inamdar/dvd_project.git |
| Local branches | `main` (= origin/main, 1 commit "Initial commit"), `initial-context` |
| Pushed anything? | **No** (push blocked by permission prompt; see Remaining) |
| Commit identity | repo-local: Manas Inamdar + GitHub noreply email |

## Files in the repo `context/` (all sanitized)
* `DVD_ML_PROJECT.pdf` - assignment (as received, no personal metadata)
* `Project-1_leakage_estimation_annotated.pdf` - TA slides (author metadata stripped)
* `Project_specs.txt` - team assignment, member names redacted
* `whatsapp_messages.txt` - anonymized chat transcript
* `example/22n_NMOS_ON.net` - TA example netlist, absolute personal paths redacted
* `models/*.pm` - 11 PTM model files (needed: `22nm_LP.pm`)
* `README.md` - index of the folder
Not transferred: duplicate annotated PDF (byte-identical), `model.tar` (old, lacks 22nm_LP, extra bulk models not needed), the zip wrapper (contents extracted), WhatsApp screenshots.

## Known bugs / blockers
* None in code (no code yet). Blockers: repo visibility; unanswered Q1/Q2/Q6; ngspice not installed.

## Tests performed and results
| Test | Result |
|---|---|
| Clone + remote check | `origin` points to the given URL - PASS |
| Duplicate-PDF check (SHA-256) | the two annotated PDFs are identical - PASS (deduplicated) |
| Tar vs zip models | common files identical after whitespace normalisation; tar lacks 22nm_LP - noted |
| PDF metadata scan | author name found in annotated PDF -> stripped in repo copy - PASS |
| Pattern scan for phone numbers / e-mails / passwords / keys / `/home/` in text files | only the example netlist paths (redacted) - PASS |
| Transcript vs screenshots | all 3 screenshots transcribed message by message; reviewed against the images - PASS, with flags in the file (order/dates, "@`ta'", edited reply) |
| Final scan of the whole repo tree (names from the screenshots, team-member names, instructor name, phone/e-mail patterns, `/home/` paths, PDF text + metadata) | no hits - PASS |
| `.gitignore` blocks screenshots (`context/WA/`, `context/*.png`, `Screenshot*`); verified with `git check-ignore`; no image files in the repo tree | PASS |
| Caveat: PDF *images* (slide pictures) were checked by eye on all 16 pages, not by OCR | noted |

## Immediate next steps
1. Done: transcript confirmed, screenshots deleted, repo private.
2. Push `initial-context` and open PR to `main` (needs Manas to approve the push permission or run it himself).
4. Manas: send TAs the questions in PROJECT_CONTEXT section 11 marked ASK.
5. Manas: approve (or amend) PROJECT_CONTEXT + IMPLEMENTATION_PLAN -> then Phase 1 starts.

## Session log
* 2026-11-05 Session 1: setup, sanitization, understanding, documentation, plan (this file).
