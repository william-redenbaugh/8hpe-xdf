# Shift elements (clutch/brake fill and protection) — E84

E84 X1 (gearbox GKE233, cal ZB 8609556, SW Z5YD7900_8HPXY_K790D, 8HP45). XDF: `8hpe84_cali_v1.xdf`. The semantics of every family here are unchanged from the E70 — read `docs/e70/parameters/05-shift-elements.md` for what the tables do (phase sequence, 9-slot reader `FUN_000de8ac`, set caveats, units). This chapter gives the E84 addresses, the coverage, and what did not survive the port.

Provenance: unlike the shift lines (rebuilt natively), **everything in this chapter was ported from the E70 XDF by content match** — exact byte match, record-stream walking, or length-preserved interval mapping — and every item's XDF description ends with the method and delta (e.g. `ported from E70 by content match (exact), delta +0x73dc`). The E84 read is calibration-only (everything below 0x180200 erased 0xFF, no program code), so **all reader/code statements (FUN_… addresses, slot offsets, k-indices) are E70 code facts inherited by content identity** — the E84 runs a different build of the same software family and has not been decompiled. Confidence levels are carried over from the E70 RE evidence.

Addresses below are XDF z-data addresses (start of the z bytes, after inline axes), as `tools/xdf_ls.py` prints them — the same convention as the E70 chapters. Caveat on description text: in Ghidra-sourced entries the `@0x…` inside the description is still the **E70** source address; the E84 address is the XDF table address (what `xdf_ls` prints and what this chapter quotes).

Region shifts vs the E70: the per-set element region 0x1BC1xx–0x1BE0xx moved to **0x1C33xx–0x1C5Dxx** (delta ≈ +0x73DC..+0x7A80 depending on sub-block, still ~0x3A4 bytes per set), the `elemfill` copies moved +0x4518 to 0x1A7xx/0x1A8xxx, and the elemprot cluster sits at 0x1979xx–0x1984xx (delta +0x2D0). Because the ports are content matches, stock values equal the E70 image's values for `exact` items; `walk`/`interval` items matched structure and length — spot-check values before trusting a flat-vs-populated claim from the E70 chapter.

Coverage of the port (verified against the XDF and the port report):

| Category | E70 items | In E84 XDF | Dropped |
|---|---|---|---|
| Shift elements: fill / protection | 4 | 4 | 0 |
| Shift elements: other | 47 | 45 | 2 (`elem_output_speed_corr_set1`, `elem_temp_weight_curve (set2..set3)`) |
| Unlabelled: Shift elements | 3 | 1 | 2 (`adpshfill_up_trq_min_6to7` — adaptation chapter scope, `auto_elemprot_value_c_limit_19821c`) |
| Ghidra new: shift elements | 116 | 28 | 88 |

### Shift elements: fill / protection

All 4 ported.

| Parameter | E84 address | Shape | Confidence | Notes |
|---|---|---|---|---|
| elem_fill_time_curve_set1 | 0x1C3A84 | 10x1 s16 | MED | Fill-time characteristic, flat 300 stock (exact match). E70: 0x1BC6A8. |
| elemfill_e1_range_t3_off (bank1) | 0x1A7FF4 | 4x4 s16 | LOW | Zero stock, no bound reader — leave alone. E70: 0x1A3ADC. |
| elemfill_e1_range_t3_off (bank0) | 0x1A85D8 | 4x4 s16 | LOW | Second copy. E70: 0x1A40C0. |
| elemprot_scale_curve | 0x1984E4 | 4x1 s16 | HIGH | Percent scale in the element-protection path (`elemprot_bc072`), flat 100% stock. E70: 0x198214. |

### Shift elements: other

45 of 47 ported. The per-set address scheme survives: consecutive sets sit ~0x3A4 apart inside 0x1C33xx–0x1C5Dxx, mirroring the E70 layout exactly.

**elem_a_launch_speed_press_map_set1** — `0x1BABD0`, 6x4 s16. MED. Launch-related pressure reduction for element "a" (z ≤ 0). E70: 0x1B4954.

**elem_k4_ph4_base_press (set0/2/4/6)** — 5 items, 10x1 s16 curves. MED. Base pressure per phase-4; z-range differences between sets are as on the E70 (set0 up to 6000 vs set2 topping at 400). A native-record set8 copy also ported (see the Ghidra-new section).

| Member | E84 address | E70 address |
|---|---|---|
| set0 (slot k=0) | 0x1C370C | 0x1BC330 |
| set0 copy (slot k=1) | 0x1C3AB0 | 0x1BC6D4 |
| set2 | 0x1C3F7C | 0x1BCA78 |
| set4 | 0x1C4914 | 0x1BD1C0 |
| set6 | 0x1C52AC | 0x1BD908 |

**elem_k4_ph16_time_press_curve (+ axis)** — values `0x1C3EB2`, axis `0x1C3EAC`, 7x3 s16 (7 copies, set2..set8). MED. Time→pressure ramp for phase ph16; edit per-set breakpoints in the axis table. E70: 0x1BC9AE/0x1BC9A8.

**elem_out_speed_curve_40 (+ axis)** — values `0x1C3538`, axis `0x1C3530`, 8x4 s16 (set0..set7). MED. Low-magnitude output-speed trim. E70: 0x1BC284/0x1BC27C.

**elem_out_speed_curve_50 (+ axis)** — values `0x1C3558`, axis `0x1C3550`, 9x4 s16 (set0..set8). MED. Zeroed stock on the E70; exact-match port. E70: 0x1BC2A4/0x1BC29C.

**elem_output_speed_corr_set1** — **not in the E84 XDF (needs full flash read).** The Ghidra-native set8 sibling did port (`elem_output_speed_corr_set8`, below).

**elem_ph11_time_press_curve_set8** — `0x1C5C8E`, 3x1 s16, zeroed. MED. E70: 0x1BE09A. A second set8 copy from the Ghidra record walk also ported (0x1D50D2, below).

**elem_press_curve_dc4_4c** — `0x1B2E92`, 3x1 s16, z 0..12500 **mbar** (the one unit-confirmed pressure table in this group). LOW name / known reader (`elem_press_setpoint` / FUN_000df1cc, E70 code). E70: 0x1ADECA.

**elem_press_torque_map_70 (set1..set8)** — 8 items, 8x10 s16 maps. MED. The main pressure-from-torque maps of the engagement — the central "clamp vs torque" lever, same tuning guidance as the E70 chapter. set8 is all zero stock (per the E70 image; exact/walk matches).

| Member | E84 address | E70 address |
|---|---|---|
| set1 | 0x1C3B2C | 0x1BC750 |
| set2 | 0x1C3FF8 | 0x1BCAF4 |
| set3 | 0x1C44C4 | 0x1BCE98 |
| set4 | 0x1C4990 | 0x1BD23C |
| set5 | 0x1C4E5C | 0x1BD5E0 |
| set6 | 0x1C5328 | 0x1BD984 |
| set7 | 0x1C57F4 | 0x1BDD28 |
| set8 | 0x1C5CC0 | 0x1BE0CC |

**elem_press_torque_map (set0..set2)** — `0x1C3408`, `0x1C38D4`, `0x1C3DA0`, 4x6 s16. MED. Low-magnitude slip/torque pressure correction. E70: 0x1BC1A0/0x1BC544/0x1BC8E8.

**elem_ramp_press_curve_set8** — `0x1C5A46`, 3x1 s16, zeroed. MED. E70: 0x1BDE9E.

**elem_speed_offset_curve_set0** — `0x1C3478`, 2x1 s16. MED. E70: 0x1BC210.

**elem_temp_weight_curve** — the set2..set3 block is **not in the E84 XDF (needs full flash read)**; only the standalone set8 copy ported: `0x1BBDB6`, 6x1 u8, flat 100. MED. E70 set8: 0x1B4E86.

**elem_timeout_time_set0** — `0x1B4F54`, 2x1 s16, z 250..400 time-like. MED. E70: 0x1AF900.

**elem_torque_curve_14** — values block (set0..set2) `0x1C33D4` with axis `0x1C33CC`, second block (set6, set8) `0x1C509C`. MED. E70: 0x1BC16C/0x1BC164/0x1BD744. A native set7 copy also ported (0x1D4994, below).

**elem_torque_curve_20 (+ axis)** — values `0x1C42AC`, axis `0x1C42A0`, 6x6 s16 (set3..set8). MED. E70: 0x1BCCCC/0x1BCCC0.

**elem_torque_curve_24 (set0..set8)** — 10 items, 6x1 s16, one per set with set8 present twice (same as E70). MED.

| Member | E84 address | Member | E84 address |
|---|---|---|---|
| set0 | 0x1C3464 | set5 | 0x1C4C60 |
| set1 | 0x1C3930 | set6 | 0x1C512C |
| set2 | 0x1C3DFC | set7 | 0x1C55F8 |
| set3 | 0x1C42C8 | set8 | 0x1C5A70 |
| set4 | 0x1C4794 | set8 copy | 0x1C5AC4 |

**elem_torque_press_max2_set5** — `0x1C4C88`, 6x1 s16. MED (ZF tunes it per application). A pressure ceiling over torque for set5 — same protection caveat as the E70 chapter. E70: 0x1BD458.

### Unlabelled / elemprot: Shift elements

**auto_elemprot_bae90_19815c** — `0x198436`, 3x1 s16, x 15..35, z 100..500. LOW (auto-detected; readers FUN_000b0a72 / elemprot_bae90, E70 code). The later Ghidra pass relabels the E70 source region `adpshfill_up_trq_max_5to6` (x = element adaptation count, z = max engine torque Nm; above it the adaptation run is aborted — MED), i.e. this is likely a fill-adaptation abort threshold rather than a protection curve proper.

**auto_elemprot_value_c_limit_19821c** — **not in the E84 XDF (needs full flash read).**

**auto_elemprot_value_a_margin_198230** — documented in the E70 chapter, but no longer present under that name in either current XDF (superseded during the Ghidra relabel pass). Not a port casualty — the E70 chapter's table is stale on this row.

**elemprot_elem_curve_set1** — `0x197EC0`, 8x4 s16, and **elemprot_margin_curve_set3** — `0x197F20`, 8x4 s16. LOW (filed under "Unlabelled: s16 maps"). Ghidra: limits on per-element learn values — `FUN_000bb82e` returns 1 when the per-element value ≥ `elemprot_elem_curve` (x = learn count, sat u8), and `FUN_000bb73c` returns value minus `elemprot_margin_curve` as a margin. Together with `elemprot_scale_curve` these are the visible element-protection surface on the E84. Same stance as the E70 chapter: read to understand interventions, don't raise limits to mask a pressure/fill problem.

**elemprot_count_max_set0..set4** — **not in the E84 XDF (needs full flash read).**

### Ghidra-new shift-element items (28 ported of 116)

These were generated on the E70 from binary record headers / decompile labels (counts + ascending axes verified there) and ported by content match. Data types are the record's raw storage (u16/u8); scaling unknown unless the comment says otherwise; `constant` rows are scalar u32 anchors on a Ghidra label. All LOW unless marked. They fill in the set5–set8 tails of the per-set element blocks (E84 0x1D40xx–0x1D51xx region) that the classic E70 labels did not cover.

| Parameter | E84 address | Shape | Ghidra note (from the E70 decompile) |
|---|---|---|---|
| elem_torque_curve_24_set5_0x1c7ea4 | 0x1D4060 | 6x1 s16 | indexed array, x engine torque Nm |
| elem_speed_offset_curve_set5 | 0x1D4080 | 2x1 u16 | x output speed rpm, z 0..200 mbar |
| elem_ph16_time_press_curve_set5 | 0x1D40AA | 3x1 u16 | MED — pressure add (mbar) growing with phase-16 time (final ramp to full pressure, kinds 2/3) |
| elem_torque_map_34_set5 | 0x1D40B0 | const u32 | x engine torque Nm, z 10..1000 |
| elem_temp_curve_44_set5 | 0x1D414C | 4x1 u8 | oil-temp curve |
| elem_out_speed_curve_50_set5 | 0x1D4160 | 4x1 u16 | x output speed rpm |
| elem_temp_curve_54_set5 | 0x1D4170 | 4x1 u8 | x shift-start oil temp raw |
| elem_fill_press_curve_set5 | 0x1D418C | 10x1 u8 | MED — fill pressure 0..1000 mbar over shift-start oil temp |
| elem_out_speed_curve_40_set6 | 0x1D461C | 4x1 u16 | x output speed rpm |
| elem_temp_curve_44_set6 | 0x1D462C | 4x1 u8 | oil-temp curve |
| elem_out_speed_curve_50_set6 | 0x1D463C | 4x1 u16 | x output speed rpm |
| elem_temp_curve_54_set6 | 0x1D4644 | const u32 | oil-temp scalar |
| elem_ramp_press_temp_curve_set6 | 0x1D46D4 | const u32 | ramp-phase cold-oil pressure add |
| elem_ph16_time_press_curve_alt_set6 | 0x1D4872 | 3x1 u16 | MED — as the +0x30 ph16 ramp when DAT_fff8c97d == 1 |
| elem_out_speed_curve_8c_set6 | 0x1D4884 | 4x1 u8 | x output speed rpm, z 0 |
| elem_temp_curve_04_set7 | 0x1D4894 | 4x1 u8 | x oil temp raw degC+40, z 0 |
| elem_press_add_m2_set7 | 0x1D4938 | const u32 | MED — pressure add-on (mbar) in mode 2 (elem+0x1a = 2) |
| elem_torque_curve_14_set7 | 0x1D4994 | 4x1 u16 | x engine torque Nm, z 5..25 |
| elem_fill_time_curve_set8 | 0x1D505C | 10x1 u16 | x shift-start oil temp, z 6000 |
| elem_k4_ph4_base_press_set8 | 0x1D5088 | 10x1 u16 | MED — kind-4 element base pressure (mbar), loaded into elem+0x28 at phase 4 |
| elem_ramp_press_temp_curve_set8 | 0x1D50B4 | 10x1 u16 | MED — ramp-phase pressure add (mbar), cold-oil boost |
| elem_ph11_time_press_curve_set8_0x1c8f00 | 0x1D50D2 | 3x1 u16 | MED — pressure add growing with phase-11 time |
| elem_press_torque_map_70_set8_0x1c8f10 | 0x1D5104 | 8x10 u16 | MED — second set8 press-torque map, z 750..6850 mbar per the Ghidra comment |
| elem_output_speed_corr_set8 | 0x1D51E4 | 2x1 u16 | x output speed rpm, z -10..0 |
| elem_torque_press_max_set8 | 0x1D51E8 | const u32 | x engine torque Nm, z 10000 mbar |
| elem_c_slip_press_map_set2 | 0x1C4C48 | 4x1 u16 | MED — indexed array: pressure term added to the base map in elem_ctl_c phase 19 (mbar), indexed by shift-start slip snapshot |
| elem_torque_curve_24_set7_0x1bdb68 | 0x1C55E8 | const u32 | no Ghidra comment |
| elem_msa_torque_curve_tcc_m24_set2 | 0x1BC04C | const u32 | value fed to the phase-4 pressure ramp of a kind-2 element (MSA path, TCC-interface torque input) |

Related MSA (auto start-stop) element tables, filed under unlabelled categories, also survived the port — 16 of the E70's 37 `elem_msa_*` items. Compact list (all LOW/MED Ghidra labels): `elem_msa_press_add_map_m54_set0` 0x1BA0A8, `elem_msa_press_torque_map_m58_set0` 0x1BA0F8, `elem_msa_press_torque_map_m64_set0` 0x1BA20C, `elem_msa_press_add_map_m2c_set1` 0x1BA898, `elem_msa_press_add_map_m40_set1` 0x1BADE8, `elem_msa_press_add_map_m44_set1` 0x1BAE98, `elem_msa_press_add_map_m54_set1` 0x1BAF9C, `elem_msa_press_torque_map_m5c_set1` 0x1BAFD4, `elem_msa_press_add_map_m34_set2` 0x1BC15C, `elem_msa_press_add_map_m40_set2` 0x1BC254, `elem_msa_press_add_map_m4c_set2` 0x1BC34C, `elem_msa_press_torque_map_m58_set2` 0x1BC444, `elem_msa_press_torque_map_m60_set2` 0x1BC4D4, `elem_msa_torque_tcc_curve_m9c_set2` 0x1BC808, `elem_msa_torque_tcc_curve_ma0_set2` 0x1BC824, plus the m24 constant above. Irrelevant on a car without functioning auto start-stop; listed for completeness.

### Not in the E84 XDF (needs full flash read)

Dropped Ghidra-new element families — these were anchored to E70 decompile labels (scalars and odd records whose regions did not re-walk cleanly in the E84 image):

- Whole per-set families, all nine sets each: `elem_end_phase_time_set0..8`, `elem_sync_thresh_set0..8`, `elem_ph11_exit_thresh_set0..8`, `elem_k2_ph4_time_set0..8`, `elem_k3_ph4_press_set0..8` and `elem_k3_ph4_press_alt_set0..8`. These are the phase-exit/sync thresholds and kind-3 phase-4 pressures — the most regrettable loss in this chapter, since they bracket what the ported ph4/ph16 tables ramp toward.
- Fill: `elem_k4_fill_time_set0..5/7/8` (set6 never existed), `elem_fill_time_curve_set0/set2`, `elem_fill_press_curve_set0`, `elem_fill_press_curve_alt_set1_1b4d30`, `elem_fill_press_temp_curve_alt_set1_1b4d88`.
- Range/garage-shift (`rng`): `elem_rng_ph4_time_set0..2`, `elem_rng_fill_press_curve_set0/set2`, `elem_rng_press_add_map_set2`, `elem_rng_ramp_temp_map_set2`.
- MSA: `elem_msa_brake_torque_thr_mac_set0..2`, `elem_msa_fill_press_kind3_m90_set0..2`, `elem_msa_fill_press_kind4_m18_set0..2`, `elem_msa_slip_window_m88_set0..2`, `elem_msa_slip_window_m8c_set0..2`, `elem_msa_turb_grad_thr_mb8_set0..2`, `elem_msa_press_add_map_m28_set1`, `elem_msa_press_add_map_m38_set1`, `elem_msa_press_torque_map_m64_set1`.
- Singles: `elem_a_launch_slip_press_curve_set2`, `elem_a_slip_press_map_set5`, `elem_c_base_press_alt_map_set0`, `elem_engine_speed_corr_set6`, `elem_output_speed_corr_set0/set1`, `elem_ph11_time_press_curve_set2`, `elem_ph16_time_press_curve_set0`, `elem_k4_ph16_time_press_curve_set3/set5`, `elem_press_add_m0_set0`, `elem_ramp_press_curve_set0`, `elem_speed_offset_curve_set2`, `elem_temp_curve_44_set7`, `elem_temp_weight_curve_set3/set5/set6`, `elem_torque_curve_20_set7`, `elem_torque_curve_68_set1`, `elem_torque_press_max_set2`, `elem_torque_temp_map_set0/set1`, `elemprot_count_max_set0..4`, `auto_elemprot_value_c_limit_19821c`.

Practical consequence: on the E84 you can tune the main engagement surface (ph4 base pressures, ph16/ph11 ramps, the `_70` press-torque maps, torque curves, fill time/pressure for set1/set5/set8) but **not** the phase-exit thresholds, sync thresholds or per-set timeouts beyond `elem_timeout_time_set0` — if an edit stalls a phase, the recovery behaviour is calibrated in tables this XDF cannot see.

Coverage: 78 items across the four shift-element categories (4 + 45 + 1 + 28), plus 2 elemprot maps and 16 elem_msa items listed from unlabelled categories. Every address above verified against `8hpe84_cali_v1.xdf`.
