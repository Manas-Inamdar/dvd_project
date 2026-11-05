# PROJECT_CONTEXT - Consolidated understanding of the assignment

Last updated: 2026-11-05 (Session 1). Status: **understanding drafted, awaiting Manas's review/approval**.
Sources: `context/DVD_ML_PROJECT.pdf` (the assignment, authoritative), `context/Project-1_leakage_estimation_annotated.pdf`
(TA lecture slides with hand annotations), `context/whatsapp_messages.txt` (informal clarifications),
`context/Project_specs.txt` (team assignment), `context/example/22n_NMOS_ON.net` (TA example netlist),
`context/models/*.pm` (PTM BSIM4 model files).

Precedence when sources disagree: **assignment PDF > TA-confirmed clarifications > WhatsApp clarifications > slides/example netlist**.

---------------------------------------------------------------------------------------------------

## 1. Our assignment (from `Project_specs.txt`)

| Item | Value |
|---|---|
| Team | No. 26, "Return of LUZAAZ" (member names intentionally not stored in the repo) |
| Model file | **22nm_LP** (`context/models/22nm_LP.pm`) - PTM Low Power 22 nm, BSIM4 (`level=54`, `version=4.0`) |
| Nominal VDD | **1 V** (sampled range 0.9 V to 1.1 V) |
| Channel length L | **22 nm** (= Lmin) |
| Widths | W = 1 x Lmin to 8 x Lmin = 22 nm to 176 nm, for NMOS and PMOS |
| Test circuit | **8-bit parity checker** (not the 3-bit CLA) |

---------------------------------------------------------------------------------------------------

## 2. What the project is, in plain language

**Leakage current** is the small current a CMOS circuit draws even when nothing is switching. It matters for power.
The accurate way to get it is a SPICE simulation, which is slow if you must repeat it for many random manufacturing
and operating conditions (PVT = Process, Voltage, Temperature variation).

The idea of the project: **simulate only single transistors in SPICE, train ML models on that data, then predict the
leakage of whole gates and a whole circuit using only those ML models** (no SPICE for the prediction). SPICE of the gates
and circuit is used only as the "ground truth" to measure how good the prediction is.

Leakage mechanisms the four terminal currents capture (explained for beginners):
* **Sub-threshold leakage** - current Id from drain to source in an OFF transistor (gate below threshold). Grows
  exponentially with temperature and with lower Vth.
* **Gate (tunnelling) leakage** - current Ig through the very thin gate oxide (toxe is ~1.4 nm here). Depends on oxide
  thickness and on the voltage across the oxide.
* **Body / junction leakage** - current Ib through the reverse-biased source-body and drain-body junctions and
  band-to-band tunnelling / GIDL.
* **Stack effect** - in a series stack (e.g. NAND2 NMOS pair) the node between transistors floats to an intermediate
  voltage, which reduces leakage. That is why the *internal node voltages* matter and are recorded.

Each transistor is modelled as a 4-terminal device with currents Id, Ig, Is, Ib (slide 1). Slides define all four as
currents flowing **into** the device, so by Kirchhoff's current law **Id + Ig + Is + Ib = 0** (this is the "Kirchhoff
data check" deliverable).

---------------------------------------------------------------------------------------------------

## 3. The workflow (assignment PDF, restated)

### Part A - Transistor models (4 cases: NMOS ON, NMOS OFF, PMOS ON, PMOS OFF)
1. **Generate data**: 10,000 random samples per case (may be increased/decreased; goal = high accuracy on unseen data
   with the smallest dataset that works). Each sample draws *independently*: VDD, T, W, Vd, Vs, process params. Run the
   single-FET SPICE netlist, record Id, Ig, Is, Ib.
2. **Train models**: random split 70/15/15 (or 80/10/10) with a fixed seed. Compare different ML models per case, pick the best
   on **validation**, report on **test**.

### Part B - Gate-level validation (INV, NAND2, NOR2, AND2, OR2 -> 18 input cases)
3. **SPICE reference**: every gate, every input combination, **200 random corners** (evaluation only, never training).
4. **ML prediction**: take the SPICE-recorded internal node voltages (PMOS pull-up stack / NMOS pull-down stack) and
   output voltage; from them derive (Vd, Vg, Vs, Vb) of each transistor; feed those + other parameters to the trained
   transistor models; add up predicted currents into gate leakage.
5. **Compare** ML vs SPICE for every gate and input combination.

### Part C - Test circuit (8-bit parity checker)
6. **SPICE reference**: whole transistor-level netlist, every input vector, the **same 200 corners**.
7. **ML prediction**: for each input vector find the logic value at every gate's inputs, call that gate's model, sum the gate
   leakages. (Ignores loading between gates; expected to be somewhat less accurate than gate level.)
8. **Compare** and submit deliverables.

Target: **up to 99 % mean accuracy** (assignment). The annotated slides add handwritten goals: **R2 > 0.99** and **error < 1 %
vs simulation** for the transistor ML models.

---------------------------------------------------------------------------------------------------

## 4. Parameters to sweep (assignment Section 4)

Draw VDD **first** (Vd and Vs ranges depend on it). All independent.

| Parameter | Range / distribution |
|---|---|
| VDD | Uniform, 1 V +/- 10 % -> [0.9, 1.1] V |
| Vd | Uniform, 0 to VDD |
| Vs | Uniform, 0 to VDD |
| W | Uniform, 1 x Lmin to 8 x Lmin |
| Temperature | Uniform, -40 to 125 degC |
| vth0, toxe, ndep, u0, xj | Uniform, nominal (from `22nm_LP.pm`) +/- 10 %; separate values for NMOS and PMOS |

Gate and body voltage fixed by the case:

| Case | Vg | Vb |
|---|---|---|
| NMOS ON | VDD | 0 |
| NMOS OFF | 0 | 0 |
| PMOS ON | 0 | VDD |
| PMOS OFF | VDD | VDD |

Nominal values to perturb (from `context/models/22nm_LP.pm`):

| Param | NMOS | PMOS |
|---|---|---|
| vth0 | 0.68858 | -0.63745 |
| toxe | 1.4e-9 | 1.4e-9 |
| ndep | 5.5e18 | 4.4e18 |
| u0 | 0.035 | 0.011 |
| xj | 7.2e-9 | 7.2e-9 |

Netlist requirements: every netlist (transistor, gate, test circuit) must contain
`.options gmin=1e-18 abstol=1e-18 reltol=1e-6 vntol=1e-9`; in single-transistor netlists **each terminal has its own
voltage source**. WhatsApp clarification (T1): also add junction areas **AD = AS = W x Ldiff** to transistors.

---------------------------------------------------------------------------------------------------

## 5. Gates and test circuit (assignment Section 5)

Static CMOS gates; AND2 = NAND2 + INV, OR2 = NOR2 + INV.

| Gate | Input combos | Internal node(s) recorded | Cases |
|---|---|---|---|
| INV | A = 0, 1 | none | 2 |
| NAND2 | 00, 01, 10, 11 | x (between series NMOS) | 4 |
| NOR2 | 00, 01, 10, 11 | y (between series PMOS) | 4 |
| AND2 | 00, 01, 10, 11 | x and NAND2 output | 4 |
| OR2 | 00, 01, 10, 11 | y and NOR2 output | 4 |
| **Total** | | | **18 cases x 200 corners = 3,600 SPICE runs** |

* A **corner** = one random draw of VDD, temperature, process params (Section 4 distributions). **All NMOS in a gate share one
  draw, all PMOS share another.** Gate inputs are exactly 0 or VDD.
* AND2 and OR2 must be simulated in SPICE as complete gates (do **not** add separate NAND2 + INV results).
* For every case record: SPICE leakage, ML leakage, internal node voltages (both), SPICE output voltage.
* Test circuit: SPICE the complete netlist at the same 200 corners for every input vector. For 8 inputs that is
  **256 vectors x 200 corners = 51,200 SPICE runs**. ML: compose from gate models, sum gate leakages.

---------------------------------------------------------------------------------------------------

## 6. Deliverables checklist (assignment Section 6)

| # | Deliverable | Notes |
|---|---|---|
| 1 | 4 dataset CSVs (NMOS ON/OFF, PMOS ON/OFF), 10,000 rows each | columns exactly: `vdd, temp, w, vd, vs, vg, vb, vth0, toxe, ndep, u0, xj, id, ig, is, ib` |
| 2 | Example netlists | 1 per transistor case, 1 per gate, test-circuit netlist |
| 3 | Data check | Kirchhoff check for each case; 3 trend plots: OFF current vs temperature, OFF current vs vth0, gate current vs toxe |
| 4 | Model comparison table | 4 model types x 4 cases; R2, median error, 95th-percentile error on **validation** set |
| 5 | Chosen models | test-set median and P95 error; predicted-vs-SPICE plot per case; **4 saved model files** |
| 6 | Gate results table | per each of the 18 cases: SPICE median, ML median, bias, median error, P95 error |
| 7 | Gate parity plot | ML vs SPICE leakage, all gate sims, log-log axes |
| 8 | Test-circuit results | same metrics as #6 + parity plot (log-log) |
| 9 | Code | scripts regenerating everything from the model file, run in order, fixed seeds |
| 10 | Report | setup (model, VDD, circuit, simulator + version); data generation; models (4 types, hyperparameters, preprocessing, comparison, reason for choice); gate results (most/least accurate gates/inputs); test-circuit results vs gate level; error analysis (where/why largest errors, e.g. high T, low vth0); limitations & improvements |

---------------------------------------------------------------------------------------------------

## 7. Informal clarifications from the course group chat (see `context/whatsapp_messages.txt`)

| # | Clarification | Confidence |
|---|---|---|
| T1 | Add AD = AS = W x Ldiff to the transistor netlists (unlike the TA example netlist). | Medium: answerer's role unknown; reply was edited. |
| T2 | Make datasets only for the assigned technology node / model file. | Consistent with PDF ("Use only those as assigned"). |
| T3 | For each of the 4 transistor cases compare >= 4 different ML techniques, finalize only 1 (the best). | Consistent with PDF deliverable 4/5 (4 model types x 4 cases; 4 saved models). |

---------------------------------------------------------------------------------------------------

## 8. What the slides add (annotated PDF, 16 pages)

* p1-3: 4-terminal "bipole" FET model; single-device simulation setups (NMOS cond/int, PMOS cond/int) using a reference
  voltage `Vref`; PMOS done by the complementary configuration.
* p4: sample database layout (PVT columns | W,L | terminal voltages | leakage currents) with handwritten goals
  "Develop ML model, R2 > 0.99, Err % < 1 % compared with simulation", temperature -40..125 C and an example nominal 0.9 V
  (0.81-0.99 V) - **this is the slide's example, ours is 1 V +/- 10 %**.
* p5-6: which internal nodes exist for 2-stack and 3-stack NMOS/PMOS arrangements.
* p7: example "INV_Package": a table of pre-recorded internal node voltages (SD1, SD2) per input combination
  (this is the format idea behind "pre-recorded internal node voltages" in Part B).
* p8-10: how complex gates decompose into stacks ("(A and B)p / (A and B)n") and inverters.
* p11-14: AO31 cell example: recognising pull-up/pull-down stacks, finding intermediate nodes, and which transistor
  contributes sub-threshold (p12), gate (p13) and body (p14) leakage for input pattern ABCD = 0000.
* p15: equations for AND2 input "00": a sum of Isub / Ibody / Igate terms with multiplicities and widths (sample, "not complete").
  Shows the idea of leakage = sum of mechanism currents of each transistor at its terminal voltages.
* p16: sketch of looping over all input patterns for NAND2 -> NOR2 composition.

---------------------------------------------------------------------------------------------------

## 9. Provided simulation files

* `context/models/22nm_LP.pm`: BSIM4 `level=54`, header says *"PTM Low Power 22nm ... nominal Vdd = 0.95V"* (assignment says use 1 V).
  Model cards are named `nmos` and `pmos`.
* `context/example/22n_NMOS_ON.net`: TA example for **NMOS ON** (MGK model). Differences from the assignment rules:
  `GMIN=1e-020` and no reltol/vntol (assignment: `gmin=1e-18 abstol=1e-18 reltol=1e-6 vntol=1e-9`); sweeps a `Vdd` source from 0 to
  1.2 V in a `.CONTROL` loop and `dc TEMP 30 90 60`; gate source is referenced to a `Ref` node; no AD/AS; `Ldiff=44n` defined
  but unused; it prints `I(Vd) I(Vg) I(Vs) I(Vb)`. **Follow the assignment, use the example only for structure.**
* The old `model.tar` supplied by the TAs does **not** contain `22nm_LP.pm`; the newer zip does. The files common to both are identical.
  `22nm_LP.pm` is the only file the project needs.
* Simulator hint: the `.CONTROL` syntax means **ngspice**.

---------------------------------------------------------------------------------------------------

## 10. Constraints (hard rules from the assignment)

* Use only the assigned model file, VDD, test circuit. L = 22 nm.
* Gate-level and circuit SPICE data are **evaluation only** - never used for training.
* ML gate/circuit prediction uses **only the 4 transistor models** (plus SPICE-recorded node voltages at gate level).
* Fixed random seeds everywhere; scripts runnable in order to regenerate all deliverables.
* AND2/OR2 simulated as full gates in SPICE.
* Datasets: exact column names/order above; 10,000 rows each.

---------------------------------------------------------------------------------------------------

## 11. Ambiguities, missing information and risks (NOT resolved - do not silently assume)

Each has a **proposed default** to keep work moving; items marked **ASK** should be confirmed with the TAs.

| ID | Issue | Proposed default | |
|---|---|---|---|
| Q1 | **What exactly is "gate leakage"?** Not defined. Options: (a) total current delivered by all sources at VDD (supply + inputs held high) = current returning to ground; (b) only the supply current; (c) sum of \|I\| of every terminal. | (a): it is physically the total static current and counts gate leakage coming from input drivers. SPICE side measured from source currents; ML side summed from terminal currents of devices attached to VDD-level nodes. | **ASK** |
| Q2 | **Transistor widths inside gates** are not specified (only W range 1-8 x Lmin for the transistor data). Slide p15 hints at PMOS = 2, NMOS = 1 for INV and 2 for the series NMOS of NAND2. | INV: Wn=1, Wp=2 (x Lmin); NAND2: Wn=2, Wp=2; NOR2: Wn=1, Wp=4 (stack-compensated) - must stay within 1..8 x Lmin (training range). Parameterise in config. | **ASK** |
| Q3 | Meaning/value of **Ldiff**, and PD/PS perimeters (chat only mentions AD, AS). | Ldiff = 44 nm (as in example netlist). Currently AD/AS only. Hand estimate with this model: sidewall junction term (jswgs x perimeter ~ 2e-17 A) is ~100x the area term (jss x AD ~ 1e-19 A), so PD/PS may matter for Ib - A/B test in SPICE once ngspice runs (PD = PS = W + 2 x Ldiff is a candidate). | **ASK** |
| Q4 | **VDD**: assignment 1 V, model header 0.95 V, slides 0.9 V. | 1 V +/- 10 % (assignment is authoritative). | resolved |
| Q5 | **Accuracy metric definitions**: "99 % mean accuracy", "error", "bias". | error_i = \|pred - true\| / \|true\|; accuracy = 1 - mean(error); bias = mean signed relative error; median and 95th percentile of error_i; plus R2 on log\|I\|. Report all. | **ASK** |
| Q6 | **Part C gate models need internal node voltages**, but ML prediction there is supposed to start from logic values. | Look up the Part-B recorded internal/output voltages of the same gate type, input combination and corner index (hence "same 200 corners"). | **ASK** |
| Q7 | "Record ... internal node voltages **from both**" (SPICE and ML): ML does not predict node voltages by itself. | Store the SPICE voltages that were fed to ML in both columns; optionally add an extension that solves KCL with ML currents to estimate the node voltage. | **ASK** |
| Q8 | **Parity-checker netlist** is not provided; we must design it. | 7 XOR2 in a tree; each XOR2 built only from allowed cells (INV, NAND2, NOR2, AND2, OR2). Final choice in docs/DECISIONS.md. | design choice |
| Q9 | **Corner in the circuit**: one global NMOS draw and one global PMOS draw for all gates, plus VDD and T? | Yes - same rule as gates, reuse the 200-corner table by index. | confirm |
| Q10 | **Signs**: currents span 1e-18 .. 1e-8 A and Ig, Ib change sign. A plain regression on I is dominated by large values. | Predict `sign` and `log10(abs(I)+eps)` (or an asinh-scaled target); evaluate error in linear domain. | design choice |
| Q11 | **ON-state models used for gate transistors whose gate voltage is not exactly 0/VDD** (e.g. INV inside AND2 driven by NAND2 output). | Choose ON/OFF model by comparing Vg to VDD/2; feed actual Vg/Vb as features. | design choice |
| Q12 | `toxe` is varied but the model card also fixes `toxp`, `toxm`, `dtox`, `toxref`. In BSIM4 only some of these respond. | Vary `toxe` only as the assignment says; verify the "Ig vs toxe" trend plot responds; report if not. | risk |
| Q13 | Convergence at `gmin=1e-18 abstol=1e-18 reltol=1e-6 vntol=1e-9` for tiny currents; failed runs. | Smoke-test early; log and resample failed points so every dataset has exactly 10,000 valid rows. | risk |
| Q14 | Number of ML models: PDF "four ML models" vs chat "4 techniques per case, pick 1". | 4 final models = 1 per case; each predicts all four currents (Id, Ig, Is, Ib) (multi-output or 4 heads). | resolved by T3 |
| Q15 | Is simulator `ngspice`? Which version? Not installed on this PC yet. | ngspice (>= 40) with BSIM4 `level=54`. Record version in the report. | setup needed |
| Q16 | Course material (assignment PDFs) in a public GitHub repo. | Make repo **private** before pushing (see TEAM_WORKFLOW). | Manas to decide |
| Q17 | Sample counts: "may be increased or decreased"; acceptable runtime? | Start with 10,000/case, use learning curves to decide on increasing. | open |
