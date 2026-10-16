# Signals & diagnosis — E84 (GKE233, cal 8609556)

E84 counterpart of [the E70 chapter](../../e70/parameters/09-signals-diagnosis.md). The role of the group is unchanged: input-signal conditioning (speeds, temperature), the transmission loss (drag-torque) model whose corrected torque feeds every downstream consumer, tip-in evaluation in the torque-model region, and the big block of unlabelled diagnosis/monitoring structures. Read the E70 chapter for the mechanism discussion; this one records what exists in `8hpe84_cali_v1.xdf`, at which E84 addresses, and what did not survive the port.

**Provenance.** The E84 read is **calibration-only** (everything below 0x180200 erased 0xFF, no program code), so every code-level statement — reader functions, the decompiled percent formula, the `mdl_*` region semantics — inherits from the E70 RE (same Bosch iTCU2 / SH-2A family, earlier 2012 software generation). The items below were ported from the E70 XDF by exact byte match, record-stream walking, length-preserved interval mapping, global signature alignment and regional delta voting; each XDF description ends with its method and offset, e.g. `E84 8609556: ported from E70 by content match (exact), delta +0x7e4`. A byte-exact object match is strong evidence it is the same table, but the reader attribution cannot be re-verified without the E84 program ROM — treat E70 confidence ratings as the ceiling, not the floor.

**Honesty note, unchanged from the E70:** confidence in this group is mostly LOW. Only `trqloss_coolant_curve` is HIGH (decompiled percent-scaling formula, from the E70 code), the 27 gear-loss maps and `trqloss_idle_load_map` are MED, everything else is a hypothesis.

### Vehicle constants: Radumfang & diff-ratio learn list

**Radumfang — dynamic wheel circumference (mm)** — u16 at **0x191404** (XDF folder "Patches (click to apply)"; ported by manual signature match, delta -0x4b0c). Stock E84 value **2003 mm**, which is a 225/50R17 rolling circumference — the X1 wears different rubber from the X5, so do not copy an E70 value across. Everything else carries over verbatim from the E70 doc:

- Formula: `pi x (rim_inch x 25.4 + 2 x width_mm x profile_pct/100) x 0.97`. Use the tyre maker's Abrollumfang directly if published.
- After flashing: reset the learned rear-axle value (Tool32 job `steuern_lernfkt_ruecksetzen`, argument 0), drive above ~24 km/h, then read `status_lernfkt` and confirm the learned value equals your real diff ratio; if it lands one step off, scale your entry by (real ratio / learned value) and repeat.
- Not a speedometer correction — that is the DSC's coding.

**Diff-ratio learn list** — 17 u16 (ratio x100) at **0x1916B4** in the E84 image: 2.00 2.35 2.47 2.56 2.65 2.81 2.93 3.08 3.15 3.23 3.38 3.46 3.64 3.73 3.91 4.10 4.27 — verified byte-identical to the E70 list in this read. The TCU snaps the learned ratio to the closest entry, which is why the Radumfang entry only needs to land within about -1 %/+2.5 % of the reference. This list is **not an XDF table** (there is nothing to tune in it); it is documented here so the learn procedure above makes sense.

### Signals: speeds

4 of 4 E70 members ported. One structural difference worth knowing: on the E70 the two `sigcond` curves sat 0x70 apart and were documented as one run; on the E84 they ported individually to addresses ~0x3D5C apart, so the "sigcond family" is no longer a contiguous block.

| Parameter | E84 address | Shape | Axes / values (stock) | Confidence | Port |
|---|---|---|---|---|---|
| `sigcond_shift_curve_0` | 0x19AF78 | 6x1 s16 | x: rpm 500..7000, z: -200..-20 | LOW | exact, +0x7e4 |
| `sigcond_trq_offset_engspd` | 0x19721C | 6x1 s16 | x: rpm 500..7000, z: -10 flat | LOW | exact, -0x35e8 |
| `speed_eng_grad_comp_curve` | 0x1A3938 | 4x1 s16 | x: 1200..1800, z: 31..46 | LOW | exact, +0x4128 |
| `speed_curve_d72c` | 0x1DAB34 | 5x1 mdl_curve_u16_s16 | x: 0..250, z: -10000..-250 | LOW | exact, +0xc69a |

Inherited readers (E70 code): FUN_000b9b1c for both sigcond curves, FUN_000dc4da for the gradient compensation, FUN_00122a1a for the model curve. Same warnings as the E70 chapter: the flat -10 in `sigcond_trq_offset_engspd` looks like a constant torque bias every consumer sees; `speed_curve_d72c` is a model-region internal — do not edit.

### Signals: temperature / warm-up

**Cold-oil pressure compensation** — `temp_cold_press_curve`, **0x1D49E4**, 4x1 s16 curve, x: oil temp raw degC+40, z: 18500 (mbar?). Confidence LOW (E→F label transfer inherited from the E70; ported exact, delta +0xc1b8). Same reading as the E70 chapter: a cold-ATF pressure correction; the `(mbar?)` flags an unproven unit.

### Signals: torque / losses

38 of 39 E70 members ported. The missing one: **`trqloss_idle_target_curve` is not in the E84 XDF (needs full flash read)** — the idle-loss family below is therefore one member short.

**Per-gear drag-torque maps, hot/warm/cold** — all 27 ported (`trqloss_gear_map_{hot,warm,cold}_set0..set8`), each 6x6 u8, same axes as the E70 (x 17..117, y 23..219), z 0..18-ish. Confidence MED (byte-identical object matches, run-context aligned). The E84 address scheme differs slightly from the E70's: temperature variants are still 0x38 apart, but consecutive sets are **0xBC** apart (E70: 0xA8) — there is an extra 0x14 of other data between sets in this build.

| Set | hot | warm | cold |
|---|---|---|---|
| set0 | 0x19A778 | 0x19A7B0 | 0x19A7E8 |
| set1 | 0x19A834 | 0x19A86C | 0x19A8A4 |
| … | +0xBC per set | +0xBC per set | +0xBC per set |
| set8 | 0x19AD58 | 0x19AD90 | 0x19ADC8 |

Interpretation unchanged: nine sets ≈ one loss map per operating gear (slot-to-gear mapping unproven), hot/warm/cold is the temperature dimension, lowering z raises the TCU's net input-torque estimate and with it computed clutch pressures. Log before/after if you experiment.

**Idle / low-speed loss model** — 4 of 5 members ported (readers FUN_000b85a6 / FUN_000b84c2 inherited):

| Parameter | E84 address | Shape | Axes (stock ranges) | Confidence |
|---|---|---|---|---|
| `trqloss_idle_load_map` | 0x19A4B8 | 8x12 s16 | x: 0..1200, y: 0..1200, z: 0..570 | MED |
| `trqloss_idle_outspd_curve` | 0x19A5D8 | 5x1 s16 | x: 64..550, z: 0..100 | LOW |
| `trqloss_idle_coolant_thr` | 0x19A664 | 4x1 u8 | x: 18..98, z: 100..150 | LOW |
| `trqloss_outspd_grad_map` | 0x19A6A4 | 6x6 s16 | x: 64..450, y: -800..100, z: 0..100 | LOW |
| `trqloss_idle_target_curve` | — | — | not in the E84 XDF (needs full flash read) | — |

**Coolant-temperature torque scaling** — `trqloss_coolant_curve`, **0x19A4A4**, 6x1 u8, x: coolant temp 18..123, z: percent around 100. **Confidence HIGH** — still the only HIGH item in the group, on the strength of the E70 decompile: `cal_curve_u8(...) -> sat_s16((u8*param_2)/100)`, a percent scale on the input torque. 100 = transparent. The formula is E70 code evidence; the E84 object is a byte-exact port of the same table.

**Loss correction / blend curves** — `trqloss_temp_curve_20` (**0x19A5F0**, 4x1 s16, x 0..80, z 100..140, reader FUN_000b8768) and `trqloss_blend_curve` (**0x19A748**, 4x1 s16, x speed delta -50..50, z blend 0..255, reader `trqloss_c8698`). Both LOW, both ported exact.

**Torque model tip-in evaluation** — all 4 ported, still in the `mdl_*` 16-bit region (readers FUN_001257d0 / FUN_00125b72 / FUN_00121b14 inherited). The E70 chapter's x/y-convention caveat for the two maps applies unchanged.

| Parameter | E84 address | Shape | Axes (stock ranges) | Confidence |
|---|---|---|---|---|
| `torque_tipin_eval_curve_1ddd84` | 0x1D8A3C | 3x5 mdl_map_u16_u16 | x: 100..500, y: 80..98, z: 70..100 | LOW |
| `torque_tipin_speed_factor_map_1dddb4` | 0x1D8A6C | 5x5 mdl_map_s16_u16 | x: 700..1000, y: -20..40, z: 80..100 | LOW |
| `torque_tipin_eval_curve_1e1516` | 0x1DAD34 | 3x1 mdl_curve_u16_u16 | x: 50..500, z: 10..20 | LOW |
| `torque_curve_e18` | 0x1DAA74 | 3x1 mdl_curve_u16_u16 | x: 0..40, z: 1..1 (flat) | LOW |

### Gear display sources (Ghidra new: signals)

Of the 50 "Ghidra new: signals" items the E70 XDF gained from the decompile pass, only **3** ported — the cluster gear-digit source selectors:

| Parameter | E84 address | Shape | Meaning (MED, from E70 decompile) |
|---|---|---|---|
| `disp_gear_src_v0` | 0x193F7C | 4 u8, indexed by display program 0..3 | digit source: 0 none, 1/2 raw sources, **3 = manual/actual gear** |
| `disp_gear_src_v1` | 0x193F84 | 4 u8 | as v0, variant 1 |
| `disp_gear_src_v2` | 0x193F8C | 4 u8 | as v0, variant 2 |

These are the E84 face of what the E70 chapter 10 documented as `gear_display_digit_rule` (that view itself did not port — see the patches chapter): set the per-program byte to 3 and the cluster shows the actual gear number 1..8. The other 47 items of the category — the `sigcond_trq_offset_temp_a/b` offsets, the `spd_*` PT1 filter weights and ring lengths, the input-override flags — are **not in the E84 XDF (needs full flash read)**; they were code-anchored constants that cannot be located in a calibration-only image. "Ghidra new: diagnosis / monitoring" fared worse still: 0 of the E70's 33 items ported.

### Unlabelled: Diagnosis / monitoring

**97** of the E70's 123 auto-detected structures ported; the remaining 26 are **not in the E84 XDF (needs full flash read)**. Everything the E70 chapter says still applies: these were found by the structural scanner (`e_calscan.py`), "Meaning not analysed" appears in every description, they were binned here by reader-function location, all are LOW, and the sensible edit count is zero — in a monitoring region these are plausibility limits, debounce times and fault thresholds, where a blind edit can silence a protection or set a false fault. On the E84 they span roughly 0x1972B4–0x1D49D0.

Breakdown of the 97 by title:

| Pattern | Count | Data type |
|---|---|---|
| `auto_cal_curve_s16_*` | 27 | 16-bit signed |
| `auto_cal_map_s16_*` | 15 | 16-bit signed |
| `auto_cal_curve_u16_*` | 13 | 16-bit unsigned |
| `auto_cal_curve_f32_*` | 9 | 32-bit float |
| `auto_cal_map_u8_*` | 7 | 8-bit |
| `auto_cal_curve_u8_*` | 6 | 8-bit |
| Ghidra-relabelled | 20 | mixed |

Two notes against the E70 chapter. First, the titles still encode the **E70** flash address (`auto_cal_curve_s16_19f9a4` etc.) — on the E84 the item is self-locating through its axes/EMBEDDEDDATA and the `delta` in the description, not the title. Second, 20 members of this category no longer carry `auto_cal_*` names at all: the Ghidra pass that fed the v3 E70 XDF renamed them (e.g. `tcc_gain_temp_map_c_set1` @0x1A4578, `tcc_ramp_time_map_set1` @0x1A4488, `shiftexec_dn_redo_trq_cls2_6to5` @0x1B30C8, `standstill_gear_map_5_f0`, `tc_torque_ratio_mu`), and they ported under those names while staying categorized here. Same rule either way: **do not edit these** — they are documented so the memory is accounted for and so logging work has somewhere to start.

Coverage: 140 XDF items in the four core groups — Signals: speeds 4/4, Signals: temperature / warm-up 1/1, Signals: torque / losses 38/39, Unlabelled: Diagnosis / monitoring 97/123 — plus the Radumfang constant (XDF Patches folder), the binary-only ratio learn list, and 3/50 Ghidra-new signal items (0/33 Ghidra-new diagnosis). Every address above was verified against `8hpe84_cali_v1.xdf`; the deltas and match methods are in each item's description.
