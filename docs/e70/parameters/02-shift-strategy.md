# Shift strategy (program selection, gear limits, driver/situation detection)

This group is the "brain above the shift maps". The 8HP TCU does not run a single shift schedule: it runs a **strategy state machine** with up to 100 states — on a production 8HP these typically cover sport/comfort programs, manual mode, hot/cold-oil fallbacks, grade/trailer situations and limp states, though the meaning of the individual state numbers has not been mapped in this RE work. Each state carries a bundle of per-state attributes, and one of those attributes — the **shift-characteristic index** — selects which of the 23 shift characteristics (`char 00..22`, documented in the shift-maps group) actually supplies the up/downshift lines. Around that core sit the **shift-type selection** tables (which decide *how* a given shift is executed — e.g. normal clutch-to-clutch vs. multiple/skip shifts), **gear limit** curves that clamp the allowed gear range under cold oil, altitude, or other conditions, the ZF **sport functions** (`sf##`, e.g. downshift/gear-hold logic in spirited driving), and **driver / driving-situation evaluation** inputs such as grade load factor and driving-resistance corrections.

For a tuner, the practical interactions are: the state machine picks a state → `strat_shift_char_index` picks the shift characteristic → the gear-limit and sport-function logic may veto or hold gears → the shift-type tables decide how the resulting shift is carried out. Note that this group was reverse engineered statically; several families below are structural finds whose *meaning* is only MED or LOW confidence — the description of each XDF item carries the exact evidence, and the honest confidence is repeated here.

A note on map orientation: items using the `mdl_map_*` helper store rows = x input, columns = y input; the axis order shown in TunerPro and in the description text can look swapped — trust the breakpoint ranges to identify which physical input is which.

### Shift strategy: programs / state

**Per-state attribute arrays (`strat_shift_char_index`, `strat_state_attr*`, `strat_state_class`, `strat_state_flag_8/9`, `strat_state_gear_sel_method`)** — 10 items, u8[100] arrays indexed by strategy state 0..99, in 0x1C9024–0x1CACA8. Each array gives one attribute per strategy state; the state machine copies the active state's byte into a RAM variable each cycle. These are the master "program" tables:

| Parameter | Address | What it does | Confidence |
|---|---|---|---|
| `strat_shift_char_index` | 0x1C9218 | Shift-map characteristic index 0..22 per state — *which shift schedule each program uses* (e.g. state 14 → char 18, states 25/26 → char 14, state 58 → char 22, state 69 → char 4). | HIGH |
| `strat_state_gear_sel_method` | 0x1C90EC | Gear-selection method per state: 0 = normal shift maps, 1 for states 0..10, 3 for states 11..13 (alternative gear sources). | HIGH |
| `strat_state_class` | 0x1C915A | State class 0..7; class 3 routes to an alternative gear source, classes 4–7 set internal flags. (The 4x1 curve parse at this address is a known misparse; the real layout is u8[100].) | MED |
| `strat_state_attr_0` | 0x1C9024 | Per-state value → RAM fff8d520; zeroed when `strat_attr_enable` byte 0x1b is 0. Blind-verified layout. | HIGH |
| `strat_state_attr_1` | 0x1C9088 | Per-state value → fff8d522. | MED |
| `strat_state_attr_2` | 0x1C91B4 | Per-state flag → fff8dd40. | MED |
| `strat_state_attr_3` | 0x1C927C | Per-state flag → fff8dd39. Blind-verified layout. | HIGH |
| `strat_state_attr13` | 0x1C9790 | u8[100][13] attribute block; columns 5..8 are the torque-limit handshake flags (fff8d4e8..d4f8); gated column-wise by `strat_attr_enable`. | MED |
| `strat_state_flag_8` | 0x1CAC44 | Per-state flag → fff8de5f. | MED |
| `strat_state_flag_9` | 0x1CACA8 | Per-state flag → fff8dd41. | MED |

Changing `strat_shift_char_index` is the clean way to make a program (e.g. D-comfort) use a different shift characteristic. The attr/flag arrays are use-evidenced but their units are not physical — edit only with a known-good reference.

**Per-gear × per-state arrays (`strat_state_gear_attr_a/b/c`)** — 3 items, u8[8][100] (indexed gear*100 + state), at 0x1CA1B8 / 0x1CA53C / 0x1CA8C0, feeding RAM fff8d4c2 / fff8d4c4 / fff8d4c0. One byte per (target gear, strategy state) pair; semantics unlabelled. Confidence MED (layout pinned from code, meaning unknown).

**Attribute enable vector (`strat_attr_enable`)** — 1 item, u8[13] at 0x1D3404. Per-attribute enable: 1 = take the raw byte of the 0x1C9790 attribute block for that column (byte 0x1b additionally gates fff8d520 / `strat_state_attr_0`). Confidence HIGH.

**Shift-type condition records (`shift_type_cond_records r00..r19`)** — 20 items, one 0x1F-byte record each, contiguous at 0x1CB340–0x1CB5AB. The reader indexes the table as `base + row*0x1F`. Record layout: +0x00..+0x12 required condition mask (19 bytes), +0x13/+0x14 up/down flags, +0x15..+0x1D per-gear enable bytes, +0x1E program/selector byte. This is the rule table that decides which shift type fires under which conditions; the known XHP commercial tune rewrites scattered bytes in several records (e.g. 4 bytes in r05), but the per-byte **semantics are not proven — Confidence LOW**. Treat as expert-only.

**Shift-type selection scalars and selectors** — 4 items:

| Parameter | Address | Shape | What it does | Confidence |
|---|---|---|---|---|
| `shift_type_by_gear` | 0x1CDAE2 | u8[8][3] | Per-gear shift-type byte for each of 3 shift phases. | HIGH |
| `shift_type_thresholds` | 0x1CB658 | 6 × u16 | Thresholds read by shift-type select; stock 950, 250, 50, 1060, 1060, 40 — XHP changes them to 550/450/-/850/850/-. | MED |
| `shift_mode_selectors` | 0x1CB334 | 12 bytes (u8, indexed mode*2 + status flag) | Mode-indexed selector 0..4 feeding shift-mode index select; XHP changes 4 of the 6 u16-view entries (~−60%). | MED |
| `shift_ramp_progress_thresh` | 0x1CB32C | 4 × s16 | Per-quadrant percent thresholds compared against shift-ramp progress. | MED |

Together with the condition records these steer *how* a commanded gear change is executed (which shift routine/ramp variant). They are the levers commercial tunes touch to change shift behaviour, but units are internal, not physical.

**Per-gear shift element pair list (`shift_element_pair_b`)** — 1 item, 6 × u16 at 0x1CAF14 (third of three sibling 12-byte pair tables at 0x1CAEFC/0x1CAF08/0x1CAF14). Each entry holds a duplicated byte encoding a (from, to) element pair per gear step; the XHP tune rewrites all six entries to match the 0x1CAF08 sibling — consistent with a per-gear shift-element (clutch) pair list. Confidence MED.

**Per-gear torque rows (`per_gear_torque_rows`)** — 1 item, 75 values (16-bit in the XDF; the evidence suggests 72 u16 = 8 rows of 9, with the length of 75 set only by the gap to the next label) at 0x1CEE00. `(&0x1CEE00)[gear]` is the minuend of the torque-headroom value in the shift-torque-headroom evaluation; XHP lowers 21 entries (−28%..+9%). In plain terms: these rows set the per-gear torque reference the TCU compares engine torque against when judging shift headroom — relevant when raising engine torque in a swap. Structure/usage Confidence HIGH; exact layout not proven.

**Strategy environment maps (`strat_env_curve`, `strat_env_pressure_map`, `strat_env_speed_map`)** — 3 items at 0x1CCFB8 (7x1, 0..1000 → 0..980, HIGH), 0x1CAE18 (4x7, breakpoints 650..850 vs 0..1100, z 0..1100, LOW) and 0x1CAE6A (5x7, breakpoints 1400..3000 vs 0..80, z 0..100, LOW). Environment-condition inputs to the strategy (the 650..850/1400..3000 ranges are consistent with ambient-pressure- and rpm-like inputs, but that is inferred, not proven). All read by the same strategy function as `strat_env_curve`.

**Hot-oil strategy curves (`strat_hot_oil_curve`)** — 2 items (two copies), 4x1 `cal_curve_s16` at 0x197064 and 0x197078, x 65..150 (oil-temperature-like range), z constant 160 in this calibration. These sit outside the main model block and plausibly scale/limit strategy behaviour at high oil temperature. Confidence LOW (byte-identical object match to the F build; second copy data-pointer-only).

**Model objects matched by function (`fn_160bd0_map_1dee08`, `fn_167870_map_1def98`, `fn_167ad8_curve_1e51d6`, `fn_163080_curve_1e4dde`)** — 4 items at 0x1CC716 (5x5, 750..1000 × −20..40 → 60..106), 0x1CC8D2 (3x3, 620..950 × 0..40 → 10..24), 0x1D27E4 (5x1, 0..50 → 0..16) and 0x1D209E (10x1, 1000..6000 rpm-like → constant 66). Named only by the reading function; placed in this category by their readers' context. Meaning not analysed — Confidence LOW. View before edit.

### Shift strategy: gear selection / limits

**Gear limit curves (`gear_limit_cold_oil_curve`, `gear_limit_curve_f94`, `gear_limit_curve_172_a..d`)** — 6 items, small s16 curves clustered at 0x1CD754–0x1CD7BE, all read by the gear-limit calculation (`gear_limit_calc_main` / `gear_limit_core`). These clamp or bias the allowed gear range as a function of internal signals:

| Parameter | Address | Axis (input) | Output | Confidence |
|---|---|---|---|---|
| `gear_limit_cold_oil_curve` | 0x1CD754 | 3 pt, −30..0 (cold oil temp) | 0..1200 | LOW |
| `gear_limit_curve_f94` | 0x1CD766 | 5 pt on RAM fff97f94 (−200..50) | constant 100 | LOW |
| `gear_limit_curve_172_a` | 0x1CD77C | 5 pt on RAM fff98172 (−500..0) | constant −100 | LOW |
| `gear_limit_curve_172_b` | 0x1CD792 | 5 pt on fff98172 (−500..0) | constant −200 | LOW |
| `gear_limit_curve_172_c` | 0x1CD7A8 | 5 pt on fff98172 (−100..100) | constant 8 | LOW |
| `gear_limit_curve_172_d` | 0x1CD7BE | 5 pt on fff98172 (−100..100) | constant 10 | LOW |

The cold-oil curve is the one most likely to matter in a swap — per its label it restricts gear/shift behaviour below 0 °C oil, though like the rest of this family that meaning is LOW confidence (F object match only). The `172`/`f94` curves are labelled only by E→F label transfer onto an unidentified RAM signal — Confidence LOW throughout.

**Multiple-downshift pedal curves (`gear_multi_dnshift_pedal_curve_1/3/5`)** — 3 items, 8x1 s16 curves at 0x1D180A / 0x1D184E / 0x1D1892 (x 0..3000/4000/4500; z −100..100 for curves 1 and 5, −100..80 for curve 3). By their label these shape multi-gear (skip) downshift decisions versus a pedal/gradient-like input; curves 3 and 5 demonstrably vary across 21 calibration versions, so ZF does tune them per application. Confidence LOW (curve 1) / MED (curves 3 and 5); the meaning is label-transferred, not proven.

**Upshift speed offsets (`upshift_speed_offsets`)** — 2 items, u16[8]+u16[8] at 0x1D2878 and 0x1D288A, indexed by gear. Per-gear / per-target-gear adders to the upshift line, applied only when the flags at 0x1D34F4/0x1D34F5 are set. This is a conditional "raise the upshift point in gear N" knob rather than a change to the shift maps themselves. Confidence MED.

**Rev-limit modifier curve (`gear_mod_rev_limit_curve_1e1e2a`)** — 1 item, 7x1 at 0x1CEBA4: x 0..1100, z 5792..6208 (rpm-like). Per its label, an input-dependent rev-limit used in gear modification/selection — plausibly an rpm ceiling respected in gear selection, but the mechanism is not proven. Confidence LOW. If your engine's redline differs from stock, this family is worth inspecting, but verify before editing.

**Gear-selection speed curves (`gear_curve_speed`, `gearsel2_speed_curve_b`)** — 2 items: 0x1D28A8 (5x1, x 10..100, z constant −100) and 0x1CE55E (6x1, x 30..200, z 25..60), both speed-indexed inputs to gear selection. Confidence LOW (structural + F object match only).

### Shift strategy: sport functions (sf##)

**Sport-function gear-hold curves (`sf06_hold_curve_1e1940`, `sf07_hold_curve_1de0f0` ×2)** — 3 items. `sf06_hold_curve` (0x1CE8EE, 4x1 over vehicle speed km/h, Confidence LOW) and two 5x5 copies of `sf07_hold_curve` (0x1CBEBA LOW, 0x1CBF02 HIGH; axes 1000..5000 rpm-like × 5..120 speed-like, z 0..150), all read by the sf07 hold function. The ZF `sf##` sport functions implement situation-driven gear holding (e.g. keeping a lower gear through corners or after lift-off); per the label semantics these curves shape the hold behaviour versus speed/rpm — but neither the unit of z nor the direction of its effect is proven, so view/log before editing and change incrementally.

### Shift strategy: driver / driving situation

**Grade load factor evaluation (`grade_load_factor_eval_curve_1e1cea`)** — 1 item, 5x1 s16 at 0x1CEAC4: x −250..250, z −100..200. Part of the driving-situation evaluation that detects uphill/downhill load (grade): the TCU uses grade load to pick hill programs (earlier downshifts uphill, downshift-for-engine-braking downhill). Confidence LOW (F object match).

**Driving-resistance corrections (`res_altitude_curve`, `res_brake_force_curve_alt`)** — 2 items at 0x1CE46A and 0x1CE47A, read by the driving-resistance estimator. `res_altitude_curve` (3x1): x = ambient pressure in kPa (RAM fff97e32/10, 70..80 kPa breakpoints), z = correction 40..0 — i.e. an altitude correction to the estimated driving resistance, Confidence MED (proven reader via F-twin function match). `res_brake_force_curve_alt` (4x1, x 0..500, z all 0 in this calibration), Confidence LOW. Driving resistance feeds the grade/load detection above, so these indirectly shape hill-program entry at altitude.

### Unlabelled: Shift strategy

These 19 items were auto-detected by the structural calibration scan (`e_calscan.py`) inside shift-strategy reader functions. The structure (breakpoints + data, interpolated curve/map) is solid, but **their meaning has not been analysed — all Confidence LOW**. They are included so the region is editable/viewable in TunerPro; do not change them without first identifying them (several have constant z rows, i.e. features disabled in this calibration).

**Auto-detected curves (`auto_mdl_curve_*`)** — 11 items, 1-D interpolated curves:

| Item | Address | Shape | x range | z range |
|---|---|---|---|---|
| `auto_mdl_curve_s16_u16_1cecc0` | 0x1CECCC | 5x1 | −50..100 | 20..50 |
| `auto_mdl_curve_s16_u16_1ced20` | 0x1CED32 | 8x1 | −500..1000 | 100..1000 |
| `auto_mdl_curve_u16_u16_1ce1f4` | 0x1CE202 | 6x1 | 0..60 | 0..180 |
| `auto_mdl_curve_u16_u16_1ce22c` | 0x1CE250 | 17x1 | 0..32400 | 0..180 |
| `auto_mdl_curve_u16_u16_1ce410` | 0x1CE43A | 20x1 | 0..250 | 150..600 |
| `auto_mdl_curve_u16_u16_1ce90c` | 0x1CE918 | 5x1 | 1000..4000 | 0..900 |
| `auto_mdl_curve_u16_u16_1cecf4` | 0x1CED00 | 5x1 | 0..100 | 500 (const) |
| `auto_mdl_curve_u16_u16_1d2024` | 0x1D2030 | 5x1 | 600..1000 | 40 (const) |
| `auto_mdl_curve_u16_u16_1d20dc` | 0x1D20F2 | 10x1 | 0..9000 | 100 (const) |
| `auto_mdl_curve_u16_u16_1d2130` | 0x1D2146 | 10x1 | 20..200 | 0 (const) |
| `auto_mdl_curve_u16_u16_1d2184` | 0x1D219A | 10x1 | 800..6500 | 3..99 |

**Auto-detected maps (`auto_mdl_map_*`)** — 8 items, 2-D interpolated maps (rows = x input, columns = y input): `1cb078` (0x1CB08A, 3x5, 150..1200 × 250..750, z const 32000), `1cb198` (0x1CB1AA, 3x5, 0..1020 × 250..750, z 1050..10000), `1cb2b8` (0x1CB2CA, 3x5, 0..1020 × 250..750, z 1150..10000), `1cb2e8` (0x1CB2FA, 3x5, −20..80 × 680..900, z 800..1400), `1cbdb4` (0x1CBDCA, 5x5, 1100..2500 × 20..90, z 70..100), `1cbdfc` (0x1CBE12, 5x5, 5..50 × 20..90, z 20..100), `1cbf34` (0x1CBF4A, 5x5, 2000..6000 × 5..120, z 0..150 — read by the same function as the sf07 hold map), `1cc6b8` (0x1CC6CE, 5x5, −1000..1000 × 0..250, z all 0).

Coverage: Covers all 88 items in this group (20 families).
