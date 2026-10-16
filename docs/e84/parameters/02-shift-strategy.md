# Shift strategy (program selection, gear limits, driver/situation detection) — E84

E84 X1, gearbox GKE233, cal ZB 8609556, SW `Z5YD7900_8HPXY_K790D`, 8HP45. XDF: `8hpe84_cali_v1.xdf`. Source chapter: `docs/e70/parameters/02-shift-strategy.md` — read that for the full mechanism write-ups; this chapter records what exists in the **E84** XDF, at E84 addresses, and what does not.

**Inherited-code caveat (applies to everything below).** The E84 read is calibration-only: a 2 MB image with everything below 0x180200 erased 0xFF — no program code. Every code-level statement (readers, RAM targets, the state-machine mechanics, XHP observations) inherits from the E70 RE (same Bosch iTCU2 / SH-2A family, earlier 2012 software generation). Items were carried over by porting the E70 XDF — exact byte match, length-preserved interval mapping, record-stream walking, signature alignment and regional delta voting; every ported item states the method and delta in its XDF description. Per-region deltas differ (+0xc1c8 here, +0xc3bc there, …), so **never reuse an E70 address on the E84** — all addresses below were taken from `8hpe84_cali_v1.xdf`.

**"Port" column:** *exact* = byte-identical content found in the E84 (values match the E70 calibration); *interval* = length-preserved interval mapping (the E84 content **differs** from the E70 — those tables hold E84-native values).

Mechanism recap (from the E70 RE): the strategy state machine has up to 100 states; the active state's `strat_shift_char_index` byte picks the shift characteristic, the gear-limit and sport-function logic may veto or hold gears, and the shift-type tables decide how the shift is executed. The E84's native shift lines have **21 characteristics (00..20)** against the E70's 23, with shift-disabled sentinel **8200** (E70: 8000) — see `01-shift-lines.md`. Characteristic-to-drive-mode mapping lives in the (missing) program ROM: identify the active characteristic by logging before retuning it.

Port coverage for this chapter's E70 categories (from `docs/e84/data/e84_port_report.json`):

| Category | E70 items | Ported | Not portable |
|---|---|---|---|
| Shift strategy: programs / state | 49 | 22 | 27 |
| Shift strategy: gear selection / limits | 14 | 8 | 6 |
| Shift strategy: sport functions (sf##) | 3 | 3 | 0 |
| Shift strategy: driver / driving situation | 3 | 3 | 0 |
| Unlabelled: Shift strategy | 19 | 10 | 9 |
| **Total (chapter scope)** | **88** | **46** | **42** |

"Not portable" = present in the E70 XDF but not locatable in the E84 without a full flash read; those items are listed per section below rather than silently dropped.

### Shift strategy: programs / state

**Per-state attribute arrays** — u8[100] arrays indexed by strategy state 0..99. 9 of the 10 E70 arrays ported:

| Parameter | E84 addr | Port | What it does | Confidence |
|---|---|---|---|---|
| `strat_shift_char_index` | 0x1D53E0 | interval | Shift-map characteristic index per state — *which shift schedule each program uses*. E84-native content, see table below. | HIGH |
| `strat_state_gear_sel_method` | 0x1D52B4 | exact | Gear-selection method per state: 0 = shift maps, 1 for states 0..10, 3 for states 11..13 (alternative gear sources). Verified identical to E70 in the E84 binary. | HIGH |
| `strat_state_class` | 0x1D531A | exact | State class 0..7; class 3 routes to an alternative gear source, classes 4–7 set internal flags. XDF item keeps the known E70 curve misparse; real layout u8[100], data at 0x1D5322. E84 binary uses classes 0..5. | MED |
| `strat_state_attr_0` | 0x1D51EC | exact | Per-state value → RAM fff8d520 (E70 blind-verified layout). Gating caveat below. | HIGH |
| `strat_state_attr_1` | 0x1D5250 | interval | Per-state value → fff8d522. | MED |
| `strat_state_attr_2` | 0x1D537C | exact | Per-state flag → fff8dd40. | MED |
| `strat_state_attr_3` | 0x1D5444 | interval | Per-state flag → fff8dd39 (E70 blind-verified layout). | HIGH |
| `strat_state_flag_8` | 0x1D7000 | interval | Per-state flag → fff8de5f. | MED |
| `strat_state_flag_9` | 0x1D7064 | exact | Per-state flag → fff8dd41. | MED |

Not in the E84 XDF (needs full flash read): **`strat_state_attr13`** (the u8[100][13] attribute block whose columns 5..8 are the torque-limit handshake flags) and **`strat_attr_enable`** (the u8[13] enable vector). The enable vector's byte 0x1b gated `strat_state_attr_0` on the E70; its E84 location is unknown, so attr-array edits here are even more blind than on the E70 — edit only with a known-good reference.

**Per-gear × per-state arrays** — u8[8][100], semantics unlabelled (layout pinned from E70 code, meaning unknown — MED): `strat_state_gear_attr_b` at 0x1D68F8 (→ fff8d4c4, interval) and `strat_state_gear_attr_c` at 0x1D6C7C (→ fff8d4c0, interval). **`strat_state_gear_attr_a` is not in the E84 XDF** (needs full flash read).

**E84-native state → characteristic map** (`strat_shift_char_index` content read from the binary at 0x1D53E0, 2026-10-15):

| States | char index (one per state) |
|---|---|
| 0–9 | 0 0 0 0 0 0 0 0 0 0 |
| 10–19 | 0 0 0 0 8 11 11 11 11 11 |
| 20–29 | 11 11 11 11 11 7 7 11 11 11 |
| 30–39 | 11 11 11 11 11 11 11 6 6 10 |
| 40–49 | 10 10 10 10 17 10 10 10 10 10 |
| 50–59 | 5 17 5 2 2 3 2 2 16 2 |
| 60–69 | 2 3 2 2 4 16 1 4 2 2 |
| 70–79 | 3 2 2 15 2 2 3 2 2 13 |
| 80–89 | 0 18 0 14 14 15 0 1 0 0 |
| 90–99 | 0 0 0 0 0 0 0 0 0 0 |

Notes: only indices 0..18 appear; 9, 12, 19 and 20 are never selected by this table (the E84 XDF description still carries the E70-derived "0..22" range text — the data is E84-native). States 0..13 show char 0 but use gear-sel methods 1/3, i.e. the shift maps are not their gear source. Chars **15 and 16** — the two native blocks with all-zero 1>2 stripes, likely manual-mode characteristics (see `01-shift-lines.md`) — are selected by states 73/85 and 58/65. The assumption that index *i* = *i*-th characteristic block in memory order is inherited from E70 code (HIGH there) and has not been verified against E84 code; log before trusting any state→schedule pairing. Changing `strat_shift_char_index` remains the clean way to point a program at a different schedule once the active state is identified by logging.

**Shift-type condition records** — only **r15** survived the port, at 0x1D6511 (exact, LOW). On the E70 the reader indexes a contiguous 20 × 0x1F-byte table (base 0x1CB340 in E70 ROM; layout: +0x00..+0x12 condition mask, +0x13/+0x14 up/down flags, +0x15..+0x1D per-gear enables, +0x1E program/selector). **r00..r14 and r16..r19 are not in the E84 XDF** (needs full flash read): the other 19 records' content could not be matched. If the table layout is unchanged, r15's position implies an E84 table base of 0x1D6340 — inference only, unverified (LOW). Per-byte semantics were never proven even on the E70; treat r15 as view-only.

**Shift-type selection scalars** — 1 of 4 ported: `shift_mode_selectors` at 0x1D8374 (exact, MED) — 12 bytes, mode-indexed selector 0..4 feeding shift-mode index select; XHP changed 4 of the 6 u16-view entries on the E70. Not in the E84 XDF (needs full flash read): **`shift_type_by_gear`**, **`shift_type_thresholds`**, **`shift_ramp_progress_thresh`**.

Also not in the E84 XDF (needs full flash read): **`shift_element_pair_b`** (per-gear shift-element pair list) and **`per_gear_torque_rows`** — the latter matters: it sets the per-gear torque reference for shift-headroom evaluation and is a known XHP target, so it is a real gap if you raise engine torque on an E84.

**Strategy environment maps** — 3 of 3 ported, all exact:

| Parameter | E84 addr | Shape | Confidence |
|---|---|---|---|
| `strat_env_curve` | 0x1D9EB8 | 7x1, 0..1000 → 0..980 | HIGH |
| `strat_env_pressure_map` | 0x1D71CC | 7x4, 0..1100 × 650..850, z 0..1100 | LOW |
| `strat_env_speed_map` | 0x1D721C | 7x5, 1400..3000 × 0..80, z 0..100 | LOW |

**Hot-oil strategy curves (`strat_hot_oil_curve`)** — two copies at 0x197278 and 0x19728C (exact, LOW), 4x1 `cal_curve_s16`, x 65..150, z constant 160 — same disabled-looking shape as the E70.

**Model objects matched by function** — 4 of 4 ported, all exact, all LOW (named only by their E70 reader; meaning not analysed — view before edit): `fn_160bd0_map_1dee08` at 0x1D95EC (5x5, −20..40 × 750..1000, z 60..106), `fn_167870_map_1def98` at 0x1D99E0 (3x3, 0..40 × 620..950, z 10..24), `fn_167ad8_curve_1e51d6` at 0x1DEBDA (5x1, 0..50 → 0..16), `fn_163080_curve_1e4dde` at 0x1DE83C (10x1, 1000..6000 → constant 66).

### Shift strategy: gear selection / limits

**Gear limit curves** — all 6 ported, clustered at 0x1DA1D0–0x1DA24A, read on the E70 by `gear_limit_calc_main` / `gear_limit_core`:

| Parameter | E84 addr | Port | Axis (input) | Output | Confidence |
|---|---|---|---|---|---|
| `gear_limit_cold_oil_curve` | 0x1DA1D0 | exact | 3 pt, −30..0 (cold oil temp) | 0..1200 | LOW |
| `gear_limit_curve_f94` | 0x1DA1DE | exact | 5 pt on RAM fff97f94 (−200..50) | constant 100 | LOW |
| `gear_limit_curve_172_a` | 0x1DA1F4 | exact | 5 pt on fff98172 (−500..0) | constant −100 | LOW |
| `gear_limit_curve_172_b` | 0x1DA20A | exact | 5 pt on fff98172 (−500..0) | constant −200 | LOW |
| `gear_limit_curve_172_c` | 0x1DA220 | interval | 5 pt on fff98172 (−100..100) | 8 | LOW |
| `gear_limit_curve_172_d` | 0x1DA236 | exact | 5 pt on fff98172 (−100..100) | 10 | LOW |

The cold-oil curve remains the one most likely to matter in a swap; the whole family is LOW (E→F label transfer / object match on E70).

**Rev-limit modifier curve (`gear_mod_rev_limit_curve_1e1e2a`)** — 0x1DB354 (exact, LOW): 7x1, x 0..1100, z 5792..6208 rpm-like, same values as the E70. Mechanism unproven. Inherited E70 code analysis puts the TCU's own overspeed guard near ~7100 rpm (assumed same on the E84's software generation — unverifiable without the program ROM), so holding gears to 7000 rpm does not require touching this family; to rev 1st/2nd out, use `tools/xdf_tune.py sport-redline` on the **native** E84 shift lines instead (default target XDF is already `8hpe84_cali_v1.xdf`).

**Gear-selection speed curve** — `gearsel2_speed_curve_b` at 0x1DACD2 (exact, LOW): 6x1, x 30..200, z 25..60. Its sibling **`gear_curve_speed` is not in the E84 XDF** (needs full flash read).

Not in the E84 XDF (needs full flash read): **`gear_multi_dnshift_pedal_curve_1/3/5`** (multi-gear/skip downshift shaping — the family ZF demonstrably tunes per application) and both **`upshift_speed_offsets`** arrays (the conditional per-gear "raise the upshift point" knob, MED on the E70). Their absence removes two of the more interesting E70 strategy levers; plan on a full flash read if you want them.

### Shift strategy: sport functions (sf##)

All 3 chapter items ported, all exact: `sf06_hold_curve_1e1940` at 0x1DAF6A (4x1 over vehicle speed, LOW) and two 5x5 copies of `sf07_hold_curve_1de0f0` at 0x1D8BF4 (LOW) and 0x1D8C3C (HIGH; axes 1000..5000 rpm-like × 5..120 speed-like, z 0..150). Same E70 warning applies: z unit and effect direction unproven — log, then change incrementally. The unlabelled 5x5 map read by the same sf07 function (E70 `auto_mdl_map_u16_u16_1cbf34`) did **not** port, and neither did the Ghidra-new `sf09_hold_table`, `sf13_cornering_hold_table` and `sf15_temp_prepare_map` (see the Ghidra-new note below) — the E84's sport-function picture is thinner than the E70's.

### Shift strategy: driver / driving situation

All 3 ported, all exact: `grade_load_factor_eval_curve_1e1cea` at 0x1DB244 (5x1, −250..250 → −100..200, LOW — grade/hill-program input), `res_altitude_curve` at 0x1DAB26 (3x1, ambient pressure kPa 70..80 → correction 40..0, MED — altitude correction to estimated driving resistance), `res_brake_force_curve_alt` at 0x1DED00 (4x1, 0..500, z all 0, LOW).

### Unlabelled: Shift strategy

10 of the 19 structural-scan items ported (all exact). Since the E70 chapter was written, the Ghidra label sync renamed several of them; the table maps back to the E70 doc's `auto_mdl_*` rows. All remain **LOW** unless noted.

| E84 XDF title | E84 addr | E70 identity / shape |
|---|---|---|
| `auto_mdl_curve_s16_u16_1cecc0` | 0x1DB46C | 5x1, −50..100 → 20..50 (Ghidra now reads it as `shift_press_dn_trq_add_c0_8to7`, LOW) |
| `shift_press_up_ph13_trq_add_7to8` | 0x1DA85E | was `auto_mdl_curve_u16_u16_1ce1f4`: 6x1, 0..60 → 0..180; Ghidra: x = input torque Nm, z = phase-13 pressure term, mbar (MED) |
| `shift_press_up_coast_base_7to8` | 0x1DA896 | was `auto_mdl_curve_u16_u16_1ce22c`: 17x1, 0..32400 → 0..180; Ghidra: coasting phase-13 term (MED) |
| `auto_mdl_curve_u16_u16_1ce90c` | 0x1DB11E | 5x1, 1000..4000 → 0..900 |
| `auto_mdl_curve_u16_u16_1cecf4` | 0x1DB4AE | 5x1, 0..100 → constant 500 |
| `auto_mdl_curve_u16_u16_1d2024` | 0x1DE7DC | 5x1, 600..1000 → constant 40 |
| `auto_mdl_map_s16_u16_1cb2e8` | 0x1D7924 | 5x3, −20..80 × 680..900, z 800..1400 |
| `shift_press_up_ph1_time_c3_4to5` | 0x1D9590 | was `auto_mdl_map_u16_u16_1cc6b8`: 5x5, −1000..1000 × 0..250, z all 0 |
| `auto_mdl_map_u16_u16_1cbdb4` | 0x1D8AB4 | 5x5, 1100..2500 × 20..90, z 70..100 |
| `shift_press_up_trq_press_c2_6to7` | 0x1D8AFC | was `auto_mdl_map_u16_u16_1cbdfc`: 5x5, 5..50 × 20..90, z 20..100; Ghidra: clutch pressure set-point part, mbar (MED) |

Not in the E84 XDF (needs full flash read), 9 items: `auto_mdl_curve_s16_u16_1ced20`, `auto_mdl_curve_u16_u16_1d2130`, `auto_mdl_curve_u16_u16_1d2184`, `auto_mdl_map_u16_u16_1cb078`, `auto_mdl_map_u16_u16_1cb2b8`, `auto_mdl_map_u16_u16_1cbf34` (the sf07-adjacent map), `shift_press_up_trq_add_c2_1to2` (renamed E70 `auto_mdl_map_u16_u16_1cb198`), and `shift_press_dn_ph12_sync_time_c0_2to1` / `shift_press_dn_trq_press_c2_6to4` (the renamed descendants of E70 autos `1ce410` / `1d20dc`).

### Ghidra-new strategy entries (outside the E70 chapter's 88)

The 2026-10 Ghidra sync added a separate "Ghidra new: shift strategy" family: 134 E70 entries, of which only **18 ported, 116 did not**. The ported 18 are the thermal-mode gear/TCC limit sets `thermode_gear_curve_set0..8` and `thermode_gear_tcc_curve_set0..8`, interleaved at 0x199C98–0x199DEC (all interval ports — E84-native values). A sample of the 116 that are **not in the E84 XDF** (needs full flash read): the entire `shiftinh_*` gear-inhibit family (`shiftinh_gear_map_0..8`, speed/temp inhibit limits — the same family the omitted 49 auxiliary entries of "[PATCH] Start in 2nd (E84) [PARTIAL]" belong to), the `sf09`/`sf13`/`sf15` tables above, `pred_decel_map`, `gear_ratio_speed_factor_hi/mid/lo`, the duplicate `strat_env_*` copies and `strat_hot_oil_curve_0x196324`.

Coverage: all 88 E70 chapter items accounted for — 46 in the E84 XDF, 42 not portable from the calibration-only read — plus the Ghidra-new strategy note above.
