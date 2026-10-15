# Adaptation (self-learning)

The 8HP is a clutch-to-clutch transmission: every shift hands torque from one clutch pack to another, and shift quality depends on knowing exactly how much oil (and for how long) it takes to fill the oncoming clutch before it starts carrying torque. Those fill times and fill pressures drift with wear, oil ageing and build tolerances, so the TCU continuously *adapts* them — it measures how each shift actually went (slip, shift duration, turbine-speed behaviour) and nudges stored correction values so the next shift lands on target. The parameters in this group are **not the learned values themselves** (those live in the TCU's non-volatile adaptation memory) — they are the calibration that governs the learning: when adaptation is allowed to run (temperature, torque, turbine-speed and signal-quality gates), how the measured error is evaluated, how big each correction step may be, and the limits the learned values are clamped to.

Three sub-areas appear here. *Fill adaptation* (`adpfill_*`, `adpshfill_*`) tunes the per-shift fill phase: step maps keyed to measured shift error, target shift times, and torque/speed windows per gear change. *Shift adaptation* (`adpshift_*`) evaluates overall shift deviation against turbine speed and shift time. *Driving-situation adaptation* (`adp_eval_*`, `adpcell_*`, `adpcond_*`) classifies the current driving situation into cells (engine speed × load/temperature), holds per-cell reference pressures, and gates when learning in a cell is trusted. If you retune shift pressures or shift times elsewhere in the calibration, these parameters decide how strongly — and under what conditions — the TCU will fight (or cooperate with) your changes.

> Confidence note: all meanings below come from static reverse engineering. HIGH items have a bound reader function and a byte-identical or slot-proven match against a reference 'F' build; MED items have a structural match and a plausible reader; LOW items are structure-only. Treat MED/LOW names as working hypotheses.

### Adaptation: fill

Fill adaptation corrects the clutch fill phase per shift type. The `adpshfill_*` tables exist per gear change (e.g. 4→3, 7→8), which is expected for clutch-to-clutch control: each shift uses a different clutch pair, so each learns separately.

**Downshift fill step maps** — 2 members, `adpshfill_dn_step_map_4to3` @ 0x1989E4 and `_5to4` @ 0x198A50. s16 8×4 maps, x: 8 pt (−20..30), y: 4 pt (−50..20), z stock all 0. Confidence **HIGH** (live target of banked blocks 04ab5c/04ab68+4, reader FUN_000d6450). These look up the adaptation step applied to downshift fill parameters as a function of the measured error (axes are deviation-shaped, spanning negative to positive); the stock all-zero z means the shipped calibration applies no extra offset. Changing z would bias the learned fill correction for those downshifts.

**Downshift target-time tables (+ axis)** — 3 members: `adpshfill_dn_target_time (4>3 .. 5>4)` @ 0x1989D8, `(7>6 .. 8>7)` @ 0x198B1C, plus the matching axis table @ 0x1989DC. Each is a block of 2 copies (one per gear change), s16 2-pt curves, breakpoints 700..5000, z constant 100. Confidence **MED**. By name, the target shift time the downshift fill adaptation steers toward, indexed by a 700..5000 quantity (turbine-speed-shaped); the axis table holds the per-block breakpoints (column = block, row = point).

**Upshift fill step maps** — 2 members, `adpshfill_up_step_map_6to7` @ 0x198778 and `_7to8` @ 0x19883C. s16 8×6 maps, x ≈ −23..38 / −15..25, y 40..250 / 40..150 (torque-shaped), z −300..300 / −300..250. Confidence **MED** (byte-identical / 91.7% value match to F objects; readers FUN_000d587e/d5c60/d610e/d6450). Adaptation step for the 6→7 and 7→8 upshift fill as a function of measured deviation and (likely) torque; non-zero stock values mean these upshifts actively trim fill both ways.

**Upshift adaptation torque windows** — 3 members: `adpshfill_up_trq_max_5to6` @ 0x198738 and @ 0x1988C0 (two instances, byte-identical to the same F object, bound to different banked slots 04aac0/04aaf0+8) and `_up_trq_max_6to7` @ 0x1987FC. s16 3-pt curves over x 0..3, z 40..150 (5→6) and 150..250 (6→7). Confidence **HIGH**. By name, the maximum torque at which upshift fill adaptation is allowed to learn for that gear pair — a high-torque shift makes a poor fill-learning sample, so a cap like this would exclude it.

**Upshift turbine-speed minimum** — 1 member, `adpshfill_up_turb_min_6to7` @ 0x19882C. s16 3-pt, x 0..3, z constant 1200. Confidence **HIGH** (slot 04aad8+14, reader FUN_000d5c60). Minimum turbine speed (~1200 rpm by value) for 6→7 fill adaptation to run — below it the slip measurement is unreliable.

**Fill-adaptation condition curves** — 2 members: `adpfill_cond_curve` @ 0x198E54 (u8 3-pt, x 4/5/60, z constant 6) and `adpfill_cond_curve_b` @ 0x198E30 (u8 2-pt, x 15/35). Confidence **MED** (readers adpfill_be6b2 / adpfill_bfabe in the TCC/adaptation module). Small enable/condition thresholds for the fill-adaptation routine.

**Fill element curves** — 2 members: `adpfill_elem_curve_2` @ 0x198F04 and `_3` @ 0x198F24. s16 3-pt, x 0..2, z constant 90. Confidence **MED** (index-resolved via table 0x4aeec, k=2/3 of 4 — i.e. two slots of a per-element array; the readers suggest more elements exist). Per-element (plausibly per-clutch) fill-adaptation values indexed 0..2; stock constant 90.

**`adpfill_b_pair_curve`** — 1 member @ 0x198ED4. s16 3-pt, x 0/1/2, y 90. Confidence **MED** (readers 0xb3688/0xb39f8 via table 0x4aeec +0x0/+0x4, same TCC-adaptation module). A companion per-index fill curve from the same reader family as the element curves.

**`adpshfill_class_map`** — 1 member (listed as a constant) @ 0x198D40, layout pinned as s16 5×10, x: cell class 1..5, y/z −10..40. Confidence **MED** (reader FUN_000d7626). By name and axis labelling, a classification map for fill adaptation: x is a cell class 1..5 over a ±small-range quantity, plausibly selecting which adaptation cell a measured shift updates (a hypothesis — the reader is bound but the mechanism is not proven). Edit with care — if the hypothesis holds, reshaping class boundaries changes *where* corrections are stored, not just their size.

### Adaptation: shift

These tables (all read by the shift-adaptation evaluator FUN_000d52d4) score how far a completed shift deviated from target and convert that into an adaptation update.

**Shift deviation maps** — 4 members: `adpshift_dev_map` @ 0x197390 (y 600..2800) and `adpshift_map_turb_2` @ 0x197450, `_turb_3` @ 0x1974B0, `_turb_31` @ 0x197E70 (y 1000..3250 / 1750..4000). All s16 8×4, x −100..40, z −70..60. Confidence **MED** (all read by the evaluator via the same table 0x4a828; the three `_turb` maps are index-resolved to slots k=2, k=3 and k=29 of a 0x23 ≈ 35-entry array, while `adpshift_dev_map`'s slot is not attributed). Each map converts a measured deviation (x, −100..40) and turbine speed (y, rpm-shaped) into a correction (z). The suffixes come from the reference build's labels (the resolved indices are 2, 3 and 29), and the ~35-slot array suggests one map per shift type; expect more siblings not yet identified.

**Shift-evaluation shaping curves** — 3 members: `adpshift_grad_curve` @ 0x197198 (s16 8-pt, x −20..50, z −30..40), `adpshift_hold_curve` @ 0x197180 (u16 5-pt, x 0..50000, z constant 100), `adpshift_time_curve` @ 0x1970C8 (s16 8-pt, x 20..2000, z 0..50). Confidence **MED** (same reader FUN_000d52d4). By name: a gradient-dependent weighting, a hold/decay factor over a long-range counter (0..50000 — odometer- or event-count-shaped), and a shift-time-dependent weighting (x 20..2000, ms-shaped). Together they scale how much a given shift's measured error is trusted before it updates the stores.

### Adaptation: driving situation

This sub-area classifies operating conditions into adaptation cells, keeps per-cell reference pressure maps, and gates when a cell may learn. If adaptation seems inactive on a swap, the `adpcond_*` enable gates (e.g. an oil-temperature window that is never reached) are a plausible place to look.

**Driving-situation evaluation curves** — 5 members, all s16 3-pt, reader FUN_000d5c60, Confidence **MED**: `adp_eval_curve_a` @ 0x1982E4 (x 0/1/2, z 80), `_b` @ 0x198328 (x 40/100/200, z 0), `_c` @ 0x198338 (x 100/150/250, z 300..900), and `adp_eval_time_curves` @ 0x198448 and @ 0x198458 (two copies via table 0x4ab08 +0x10/+0x14; x 0/2/3, z 2000..3500 / 1200). Thresholds and time constants (the 2000..3500 values are ms-shaped) used when evaluating whether the current driving situation produced a usable adaptation sample.

**Adaptation-cell pressure maps** — 6 members, `adpcell_press_map_a..f` @ 0x199274 / 0x1992D0 / 0x19932C / 0x199388 / 0x1993E4 / 0x199440 (consecutive, stride 0x5C). s16 6×5 maps; x: engine rpm 500..1500 (d/e: 600..1200), y: pedal/temp 40..130; z ranges 11..69, 12..45, 14..47, 60, 60, 97..140. Confidence **HIGH** (read via adpcell_c2804 (0xb52dc) at consecutive struct offsets +0x18..+0x2C; readers FUN_000b4f40 / FUN_000b5128). Base/reference pressures per adaptation cell over low engine speed and a pedal/temperature axis — the pressure-shaped z values and the low-rpm axes suggest the low-speed/launch (possibly garage-shift and creep) pressure adaptation region. Changing these shifts the baseline the cell adaptation corrects around.

**Adaptation-cell correction bounds** — 2 members: `adpcell_delta_curve` @ 0x19949C (s16 6-pt, x −100..100, z −80..100) and `adpcell_limit_curve` @ 0x1994B8 (s16 5-pt, x 0..10000, z constant 100). Confidence **HIGH** (both read by adpcell_c2804, the cell-update routine). By name, the delta curve maps a measured error to a per-update correction and the limit curve caps the accumulated correction (constant 100 over a 0..10000 x). These look like the bounds on how far cell adaptation can walk — widening them lets the TCU mask bigger hardware deviation, and also bigger mistakes.

**`adpcond_corr_curve`** — 1 item holding 2 block copies (set2, set3), first @ 0x199168. s16 8-pt, x −200..200, z −250..250. Confidence **HIGH** (banked slot 04afb0+1c, read by `adpcond_run_finish`). Correction applied when an adaptation run finishes, mapping a signed deviation to a signed correction, with separate curves for two of the condition sets.

**Adaptation enable/gate tables** — 6 members, readers FUN_000d610e / FUN_000d6450, Confidence **MED**: `adpcond_curve_a` @ 0x198318 (3-pt, x −50/0/50, z 26), `adpcond_curves` @ 0x198428 and @ 0x198438 (two copies via 0x4ab08 +0x8/+0xC; x 0/2/3, z 100..250 / 40), `adpcond_hold_curve` @ 0x1982F4 (u16 5-pt, x 0..50000, z 100), `adpcond_slip_map` @ 0x19890C (s16 8×4, x −20..30, y −50..20, z stock 0) and `adpcond_window_map` @ 0x1983A4 (s16 8×6, x −30..25, y 40..250, z −150..200). These define the slip/torque windows and hold factors within which an adaptation sample counts: the window map spans a torque-shaped y (40..250) and outputs an allowed band (−150..200), the slip map is zero stock, and the hold curve mirrors `adpshift_hold_curve`.

**Per-set temperature and timing gates** — 6 members, mostly 4 block copies each (set0..set3), Confidence **MED**:

| Parameter | Address (first copy) | Shape | Stock values | What it does |
|---|---|---|---|---|
| `adpcond_temp_curve` | 0x198F64 | s16 3-pt | x oil_temp (degC+40, 90..150 → 50..110 °C), z threshold 800 | Oil-temperature-dependent enable threshold (reader `adpcond_enable_check`); not constant across versions — 2 distinct values among the 21 surveyed |
| `adpcond_min_temp_curve` (+ axis @ 0x199050) | 0x19904C | s16 3-pt ×4 sets | x 2..8 (per-set, see axis table), z 90 | Minimum-temperature condition per set; the axis table holds each set's breakpoints (column = set) |
| `adpcond_temp_u8_curve` | 0x19901C | u8 4-pt ×4 sets | x 90..150 (degC+40), z 250 | Temperature-indexed gate per set |
| `adpcond_time_ofs_curve` | 0x199004 | s16 5-pt ×4 sets | x 0..95, z 200..12000 | Time offset (ms-shaped, up to 12 s) applied per set |
| `adpcond_ramp_rate_curve` | 0x198FF4 | s16 3-pt ×4 sets | x 0..200, z 10..100 | Ramp rate used by the condition logic per set |

The set0..set3 naming matches `adpcond_corr_curve`, whose two blocks are labelled set2 and set3 — consistent with four independently gated adaptation contexts, of which the correction curve covers two. Note the temperature convention used throughout this calibration: stored value = °C + 40, so 90..150 means 50..110 °C — the temperature gates sit squarely in the warm-oil range.

### Adaptation: other

**`adapt_torque_curve_10`** — 1 member @ 0x1B1DB4, s16 4-pt, x −48..300 (torque-shaped), z −20..−15. Confidence **LOW**: byte-identical to an F object and proven a member of a banked calibration block (T=04e37c k=358), but no reader has been bound to it. A torque-indexed correction (small negative values) whose consumer is unknown; the `_10` suffix implies it is one of a numbered series. Do not change until a reader is identified.

### Unlabelled: Adaptation

**`auto_adpcond_run_finish_199028`** — 1 member @ 0x199028, auto-detected s16 8×1 curve (x −200..200, z −250..250). Confidence **LOW**: structure found by the calibration scanner and read by `adpcond_run_finish`, but its meaning is unanalysed. Its shape and reader match `adpcond_corr_curve` exactly, so it is plausibly a further per-set copy of that correction curve — treat that as a hypothesis only.

Coverage: Covers all 52 items in this group (19 families).
