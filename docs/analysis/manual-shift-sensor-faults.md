# Sensor-related faults during manual-mode shifting — what this calibration can trip, and why

Scope: ZF 8HP TCU (Bosch ITCU2), calibration ZB 8646496 (E70 8HP), analysed from XDF **metadata only** (structure, addresses, axes, value ranges quoted in RE notes). We do not have the live calibration values. Confidence ratings are carried over from the RE evidence verbatim. Everything in section 3 that is not tied to an XDF item is informed speculation and marked as such.

---

## 1. Monitoring mechanisms the XDF exposes that run during manual shifts

### 1.1 Gear-ratio monitoring (the big one)

The calibration carries a complete per-gear and per-shift-pair ratio-monitoring block around 0x1C77C4–0x1C8660. The firmware continuously compares measured ratio (turbine speed n_t vs output speed n_ab) against bands; in-gear bands are per gear, and transition bands/offsets are per gear pair, so this monitor explicitly runs **during** shifts — including manual ones.

**Steady-state (in-gear) bands** — readers FUN_000cc92c / FUN_000cd2ac / FUN_000ce8fa:

| Item | Addr | Shape/bits | Axes (as quoted) | Conf |
|---|---|---|---|---|
| ratio_mon_upper_band_map_set0..set8 | 0x1C77E0, 0x1C78E8, 0x1C79F0, 0x1C7AF8, 0x1C7C00, 0x1C7D08, 0x1C7E10, 0x1C7F18, 0x1C8020 | 8x2, s16 | x: 8 pt speed (set1 50..1200 up to set8 50..8000); y: 2 pt torque 0..5000; z: band 559..32767 | set0 LOW, others MED |
| ratio_mon_lower_band_map_set0..set8 | 0x1C781C, 0x1C7924, 0x1C7A2C, 0x1C7B34, 0x1C7C3C, 0x1C7D44, 0x1C7E4C, 0x1C7F54, 0x1C805C | 8x2, s16 | x: as above except set2 ends 1700 and set3 ends 2500 (vs 2300/3500 upper); y: 2 pt torque-like -5000..0; z: band 800..32767 | set0 LOW, others MED |

Note the per-set x-axis ceilings grow with gear (set4 → 4300, set5 → 5000, set6 → 6000, set7 → 7000, set8 → 8000). The units are flagged "unit not proven" in the evidence, but the gear-indexed scaling is consistent with a per-gear speed input. The y axis ranges (0..5000 / -5000..0) read like signed torque, with drive vs coast split into the upper/lower map pair — plausible, but the y unit is equally unproven.

**Transition bands (during-shift tolerance)** — readers FUN_000cc21a / FUN_000cd610 (plus FUN_000cd2ac / FUN_000ce8fa on the band curves):

| Item | Addr | Shape/bits | Axes | Conf |
|---|---|---|---|---|
| ratio_mon_band_a_curve (+axis) | 0x1C7C70 / 0x1C7C60 | 5x8, s16 | blocks set4..set8; x 50..3800; z 1719..9200 | MED |
| ratio_mon_band_b_curve (+axis) | 0x1C7C94 / 0x1C7C84 | 5x8, s16 | blocks set4..set8; x 50..4300; z 1783..9667 | MED |
| ratio_mon_band_c_curve (+axis) | 0x1C7CDC / 0x1C7CCC | 5x8, s16 | blocks set4..set8; x 50..4300; z 0..1551 | MED |
| ratio_mon_band_d_curve (+axis) | 0x1C7CB8 / 0x1C7CA8 | 5x8, s16 | blocks set4..set8; x 110..3800; z 0..1615 | MED |
| ratio_mon_offset_a_curve (3 blocks) | 0x1C81F8 (5>4..8>7), 0x1C83F0 (4>5..1>3), 0x1C8630 (3>6..6>8) | 4x8 / 5x8 / 7x8, s16 | per gear-pair; x up to 3300..5000; z offsets 48..1650 | MED |
| ratio_mon_offset_b_curve (+axis) | 0x1C818C / 0x1C817C | 24x8, s16 | one block per gear pair (all 24 pairs incl. multi-gear skips); x 320..3000; z 100..830 | MED |
| ratio_slip_map | 0x1CB7CE | 3x3, u16 | axes 100..1500 and 500..3000 (the RE note and the XDF unit fields disagree on which is x), z 0..500 (allowed slip?) read by FUN_0011b708 | LOW |

The offset curves are keyed by gear pair (1>2 … 6>8, 5>4 … 8>7), i.e. the monitor widens its ratio window by a shift-specific offset while a shift is in flight. A manual shift that produces more transient slip than these offsets allow, for longer than the firmware's (not exposed) debounce, is what trips gear-ratio monitoring.

### 1.2 Guard / escalation tests on engine-overspeed (the ones the True manual patch touches)

From the patch documentation (Patches group; structure of the underlying scalars "not proven", Confidence LOW):

- **escalation_test1_threshold @ 0x1CECA4** (u16, stock 7100 rpm) and its neighbour **0x1CECA6** (stock 6825 rpm): thresholds of guard test 1 in FUN_0012c9b8 — the TCU-side **forced upshift at redline**. True manual sets both to 0xFFFF.
- **0x1CC03C** — first word of an 18-u16 block, stock 7200: the cap used by guard **test 2**. The patch *notes* describe an R4 edit raising it to 10000, but the shipped patch entries do **not** touch this address — verified against the XDF's entry list, the shipped patch instead defeats test 2 via the df32-seed and strat_state_attr_3 edits below. Threshold is scaled at runtime by (da9c × df32)/100.
- **df32 seeds @ 0x1D3A80/81** (stock 105, patch 0xFF → 255): multiplies the test-2 threshold to 2.55x.
- **df31 gate @ 0x1D34B1** (stock 02, patch 00) in FUN_0012c660; the patch notes this path "hinges on runtime def4 — supervised test only", with a program patch at 0x12CA44/56 as the deterministic fix.
- **rev-match latch arm @ 0x1D28EC** (stock 6500 rpm, patch 0xFFFF): disarms a latch that otherwise arms above 6500 rpm.
- **strat_state_attr_3 @ 0x1C927C** (u8[100] per-strategy-state flag → RAM fff8dd39, Confidence HIGH for the layout): filled with 01 by patch R5 so df31=1 in every state and the ~7200 forced upshift cannot fire.
- **intervention_element_thr_by_index @ 0x1CE634** (9x3 u16, Confidence LOW, reader unknown): stock rows repeat 1700/6500 motifs; the tune rewrites twelve 1700-cells to 6500/4500/3500/3000 — consistent with per-element engine-intervention / threshold rows raised for high-rpm shifting.

These are protection/escalation paths, not sensor diagnostics per se — but they share inputs (engine/turbine speed) with the plausibility logic, and disabling them changes where in the rpm envelope the remaining monitors operate.

### 1.3 Speed-signal conditioning and plausibility inputs

| Item | Addr | Shape/bits | Axes | Conf |
|---|---|---|---|---|
| sigcond_shift_curve_0 | 0x19A7A0 | 6x1, s16 | x 500..**7000** (engine rpm), z -200..-20 | LOW |
| sigcond_trq_offset_engspd | 0x19A810 | 6x1, s16 | x 500..**7000**, z -10 flat | LOW |
| speed_eng_grad_comp_curve | 0x19F818 | 4x1, s16 | x **1200..1800**, z 31..46 (engine-speed gradient compensation) | LOW |
| speed_curve_d72c | 0x1CE4A4 | 5x1, s16 | x 0..250, z -10000..-250 | LOW |
| standstill_turb_curve | 0x199C1C | 4x1, s16 | x 2800..3450, z 0..330 | LOW |

The notable structural fact: every speed-conditioning axis listed above ends at or below 7000 (rpm if the labels' reading is right — all are Confidence LOW). Above the last breakpoint the interpolation helpers clamp, so with the patch holding gears toward 7200+ the conditioning/compensation terms run flat-extrapolated — outside the region ZF calibrated them for.

There is also a large unlabelled "Diagnosis / monitoring" population (123 auto-detected curves/maps spanning 0x1970xx–0x1C88xx, all Confidence LOW, meaning not analysed) — e.g. the u16 curves right inside the ratio-mon block (auto_cal_curve_u16_1c783c/1c7860/1c78a8 @ 0x1C7850/74/BC, auto_cal_curve_u16_1c810c/1c8130 @ 0x1C8120/44, auto_cal_curve_s16_1c7768 @ 0x1C777C). By address — and because their listed readers include the same FUN_000cc21a/FUN_000cd2ac that read the labelled items — these very likely belong to the same monitor (perhaps timing/debounce or speed-threshold curves), but the XDF marks them "meaning not analysed".

### 1.4 Torque signals and torque monitoring

- **trqloss_gear_map_{hot,warm,cold}_set0..8** @ 0x19A1BC–0x19A76C (6x6 u8 each, x 17..117, y 23..219, z 0..18, MED): per-gear drivetrain-loss model, feeding the torque-balance the ratio monitor's torque axis depends on. Plus trqloss_coolant_curve @ 0x199ECE (HIGH — % scale on input torque vs coolant temp), trqloss_idle_load_map @ 0x199F04, trqloss_outspd_grad_map @ 0x19A0E0.
- **per_gear_torque_rows @ 0x1CEE00** (72 u16, Conf HIGH for the reader: `(&0x1CEE00)[gear]` is the minuend of the headroom calc in shift_torque_headroom_eval, FUN_00111b12) and **shift_torque_headroom curves @ 0x1CED4E (mode0) / 0x1CEDA6 (gear0) / 0x1CEDB0 (gears1_4)** (x axes 3000..6500/6700, rpm-like but unproven; the 0x1CEDB0 block is headerless with no axis; all Confidence LOW, "meaning not analysed"; the Stage 3 tune edits most cells): torque-headroom evaluation around shifts.
- **gear_mod_rev_limit_curve_1e1e2a @ 0x1CEBA4** (7x1 u16, x 0..1100 — pedal-like, z **5792..6208** — rpm-like, read by FUN_0012a764, LOW; units and role inferred from the label only): plausibly the strategy's modelled rev ceiling for gear selection — if so, note it tops out ~6200 rpm, well below an N52K's 7000 rpm redline.
- **Radumfang patch** (dynamic wheel circumference): the repo's own patch notes document that the TCU **learns the rear-axle ratio**, snapping to a fixed list (2.00…4.27), and must be re-learned after changes (Tool32 `steuern_lernfkt_ruecksetzen`, then `status_lernfkt`). The notes document the learn function and the list, not the signal path; that it compares wheel speed against output speed is the obvious mechanism but is our inference.

---

## 2. Ranked hypotheses for a sensor issue during manual shifting

Symptom vocabulary used below (general 8HP knowledge, **not** XDF-evidenced): "gear monitoring / ratio fault" = EGS Übersetzungsüberwachung fault family, typically gear-specific; escalation = substitute gear, then limp (mechanical emergency gear, TCC open) if repeated; "flare" = engine rpm overshoot during the shift.

### H1 — Transition-band trip on hard manual shifts at high rpm (most likely)
**Mechanism.** In manual mode with the True manual patch, shifts are commanded at engine/turbine speeds the stock calibration never shifts at (stock forced upshift was 7100/6825; bands and offsets were calibrated around that envelope). A high-rpm upshift (or a clutchy rev-mismatched downshift, see H2) produces a large, fast ratio transient. If measured ratio sits outside `ratio_mon_offset_a/b` + band_a..d for longer than the debounce, the monitor logs a gear/ratio fault against the target gear.
**XDF items.** ratio_mon_offset_a/b curves (0x1C817C–0x1C8630), ratio_mon_band_a..d (0x1C7C60–0x1C7CDC), per-gear upper/lower band maps (0x1C77E0–0x1C805C), unlabelled curves inside the block (0x1C7850/74/BC, 0x1C8120/44 — possibly debounce/thresholds, unproven).
**Symptom.** Sporadic ratio-monitoring DTC on specific gear pairs (the ones shifted at redline), possibly a single harsh "re-try", escalating to substitute gear/limp only if repeated. Feels like a flare + bang.
**Test/mitigation.** Log n_t, n_ab and current gear during manual shifts; check which gear pair faults. Inspect the offset_a/offset_b block for that pair and the band maps for the target gear — the per-pair x axes end at 3000–5000, so redline shifts already sit on the clamped last breakpoint. Raising offsets for the affected pairs (small steps, MED-confidence items, units unproven — change one thing at a time) or softening the shift (pressure/time in the shift-pressure groups) are the two levers. Keeping shift rpm a couple hundred rpm under the point where the shift completes beyond the band axis is the zero-risk mitigation.

### H2 — Disabled rev-match latch makes coast-side downshifts dirty
**Mechanism.** True manual R2 writes 0xFFFF over the rev-match latch arm (0x1D28EC, stock 6500 rpm). Whatever that latch did above 6500 rpm (arm a rev-match/blip handshake, per the patch note's naming) no longer arms. A manual downshift from high rpm then relies purely on clutch-fill to drag the engine up; the turbine-vs-engine speed trajectory during the shift deviates further from the model, widening the ratio excursion of H1 and lengthening the slip phase — on an NA N52K there is no torque reserve from a turbo to help the blip either.
**XDF items.** 0x1D28EC (LOW, structure not proven); gear_mod_rev_limit_curve_1e1e2a @ 0x1CEBA4 (strategy rev model caps at ~6208 — manual downshifts targeting >6200 are outside the modelled envelope); intervention_element_thr_by_index @ 0x1CE634.
**Symptom.** Downshift-specific: flare or long engagement, ratio fault on the *downshift* pair, possibly engine-intervention requests on CAN the N52K DME answers differently than the original turbo engine.
**Test/mitigation.** Compare fault incidence up vs down shifts. If downshifts dominate, trial-restore 0x1D28EC to stock (6500) or an intermediate value — if the arm threshold works as the patch note's naming suggests, it only matters above 6500 rpm, so True manual's hold-to-redline behaviour below that should be unaffected (the latch's actual action is not evidenced).

### H3 — Wrong learned axle ratio / wheel circumference skews every ratio check (swap-specific, cheap to rule out)
**Mechanism.** The TCU learns the final-drive ratio and snaps it to a fixed ratio list (documented in the Radumfang notes); the comparison of wheel speed (CAN, DSC) against its own output-speed signal is the presumed input, not spelled out in the notes. An 8HP swap with a different diff, tyre size, or a DSC/CAN emulator feeding scaled wheel speeds can leave the learned ratio one step off. Every ratio computation is then biased by a few percent — tolerable in steady state, but it eats exactly the margin the transition bands provide, so faults appear **during shifts** and look like a speed-sensor problem.
**XDF items.** Radumfang patch (documents the learn mechanism, the fixed ratio list, and the ±(-1/+2.5)% acceptance window); ratio_mon band/offset items as the tripwire.
**Symptom.** Ratio faults across many gear pairs (not just redline ones), sometimes at moderate rpm. (The speedometer itself is DSC coding, per the Radumfang notes — a wrong speedo does not implicate this learn, and vice versa.)
**Test/mitigation.** Read `status_lernfkt` with Tool32 — the learned value must equal the real diff ratio. If off: set Radumfang to the true rolling circumference, reset the learn (`steuern_lernfkt_ruecksetzen`, arg 0), drive >24 km/h. This is the first thing to check on a swap; it costs nothing.

### H4 — Torque-signal mismatch from the N52K DME biases band selection
**Mechanism.** Both band map families carry a torque-like y axis (0..5000 / -5000..0; unit unproven, see 1.1). The calibration is an E70 ZB for turbo engines; the ratio monitor and trqloss model expect the original torque signal scaling and range. An N52K (different CAN torque matrix, lower peak torque, different friction values) that reports torque the TCU maps onto the wrong band row makes the monitor evaluate shifts against the wrong tolerance — tighter than intended at the torque the engine actually delivers. Same story for the torque-headroom evaluation (per_gear_torque_rows minus actual torque) deciding shift feasibility.
**XDF items.** ratio_mon_*_band_map y axes; trqloss_gear_map_{hot,warm,cold}_set0..8 (0x19A1BC..0x19A76C, MED); trqloss_coolant_curve 0x199ECE (HIGH); per_gear_torque_rows 0x1CEE00 (HIGH reader evidence); shift_torque_headroom curves 0x1CED4E/0x1CEDA6/0x1CEDB0.
**Symptom.** Torque-interface or plausibility complaints, shifts that feel inconsistently soft/harsh with load, ratio faults clustered at high load.
**Test/mitigation.** Log the torque values the TCU receives (EGS live data: engine torque, loss torque) against what the N52K DME claims to send; verify the swap's CAN gateway passes the full torque set. The trqloss maps are the correct calibration-side lever if losses are systematically wrong — but only with logged evidence.

### H5 — Side effects of the disabled guard tests: limiter bounce outside the conditioned range
**Mechanism.** With guard test 1 dead (0xFFFF) and test 2 at 10000/2.55x, nothing TCU-side ends a held gear; the engine sits on the **DME** limiter at redline. Limiter operation is rapid torque on/off with steep engine-speed gradients. The exposed conditioning curves end at 7000 rpm (sigcond_*) and the gradient-compensation curve is only calibrated for 1200..1800 rpm — all clamped at redline. Meanwhile turbine speed physically oscillates with the limiter. A shift triggered in the middle of limiter bounce starts from a noisy speed state, again feeding H1; sustained operation there is simply unmonitored-by-design territory. The stock behaviour (before the patch) was benign precisely because test 1 upshifted the box at 7100 before this regime was reached.
**XDF items.** 0x1CECA4/A6, 0x1CC03C block (described, not patched), 0x1D3A80/81, 0x1D34B1 + strat_state_attr_3 (0x1C927C); sigcond_shift_curve_0 0x19A7A0, sigcond_trq_offset_engspd 0x19A810, speed_eng_grad_comp_curve 0x19F818.
**Symptom.** Faults only when shifting *off the limiter*; none when shifting 200–300 rpm early.
**Test/mitigation.** Reproduce deliberately: shift at 6800 vs on the limiter; if only the latter faults, this is it. Mitigation: shift before the limiter, or accept it. Note also the patch's own caveat: the 0x1D34B1 (df31) calibration-side route is flagged "supervised test only" because it depends on runtime def4 — if that path is in use rather than the program patch (0x12CA44/56) or the strat_state_attr_3 fill, inconsistent df31 behaviour across strategy states could itself produce one-off forced upshifts mid-manual-drive that get logged as implausible shift requests. Prefer the R5/K0 (strat_state_attr_3) or program-patch route.

### H6 — Genuine sensor-electrical margin at high turbine speeds (least evidenced)
**Mechanism.** Turbine/output speed in the 8HP come from internal Hall sensors read by the mechatronic. Nothing in this XDF calibrates their electrical diagnosis (those thresholds likely live in code or an unexposed region — possibly among the ~120 unlabelled "Diagnosis / monitoring" items). Sustained 7200 rpm input speed is within the hardware's physical capability, so an electrical fault here is less likely than H1–H5; but if faults log as *signal invalid / implausible* (rather than *ratio*), look at wiring/supply first — on a swap, TCU supply drops during shifts (poor grounds, weak feed during solenoid current peaks) classically masquerade as speed-sensor faults.
**XDF items.** None directly (that is the point); the unlabelled diagnosis cluster (section 1.3) is where such thresholds would sit if exposed.
**Test.** Read the exact DTC: ratio-family faults → H1–H4; signal-invalid faults → wiring/supply/sensor, not calibration.

### Reading the fault code tells you which hypothesis to chase
- Ratio/gear-monitoring DTC, specific gear pair, only at redline shifts → H1/H2/H5.
- Ratio DTCs across many pairs at ordinary rpm → H3 (check the axle-ratio learn first).
- Torque-interface / plausibility DTCs, load-correlated → H4.
- Speed-signal-invalid DTCs → H6 (hardware side).

---

## 3. Evidence vs. speculation

**Directly evidenced by the XDF/RE notes:**
- Existence, addresses, shapes and axis ranges of the full ratio-monitoring block (per-gear band maps set0..8, band_a..d curves, per-pair offset_a/b curves) and their reader functions (FUN_000cc21a/cc92c/cd2ac/cd610/ce8fa). Confidence mostly MED; **units of x/y are explicitly "not proven"**.
- The True manual patch's exact edits and the stock values they replace (7100/6825 guard test 1; df32 seed 105; df31 gate 02; rev-match latch arm 6500; strat_state_attr_3 fill — the 7200 cap at 0x1CC03C is described in the patch notes but is not among the shipped entries), including the patch's own warning that the df31 route is supervised-test-only. Underlying scalar structures mostly LOW/"not proven"; strat_state_attr_3 layout HIGH.
- Speed/torque signal-conditioning curves and their axis ceilings (7000 rpm; 1200–1800 rpm for gradient comp). LOW confidence labels.
- trqloss model (gear maps and idle-load map MED, coolant curve HIGH, outspd-grad map LOW), per_gear_torque_rows reader (HIGH; the 8x9 row layout itself is not proven), torque-headroom curves (LOW, tuned).
- The axle-ratio learn mechanism, its fixed ratio list and re-learn procedure (repo's own Radumfang patch documentation).

**Informed speculation (plausible, not provable from metadata):**
- That the band/offset x axes are speed in rpm and that clamped extrapolation beyond the last breakpoint tightens effective margins at redline shifts (the clamping behaviour of the interp helpers is standard; which input is on x is not proven).
- The mapping of monitoring trips to specific BMW EGS fault-code families and the escalation ladder (substitute gear → limp) — general 8HP behaviour, not read out of this image.
- That the rev-match latch at 0x1D28EC performs a downshift blip handshake (name and arm threshold are evidenced; its action is not).
- Everything about N52K CAN torque scaling, DME limiter dynamics, and swap wiring quality — vehicle-side context, outside the XDF entirely.
- Any suggestion to *edit* ratio_mon bands/offsets: the items are MED confidence with unproven units; treat edits as experimental, change one block at a time, and prefer operational mitigations (shift slightly before the limiter, verify the axle-ratio learn) first.
