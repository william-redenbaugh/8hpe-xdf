# Adaptation (self-learning) — E84

E84 X1, gearbox GKE233, cal ZB 8609556, SW `Z5YD7900_8HPXY_K790D`, 8HP45. XDF: `8hpe84_cali_v1.xdf`. Source chapter: `docs/e70/parameters/07-adaptation.md` — read that for the full mechanism write-ups (what fill/shift/cell adaptation does and how the evaluators work); this chapter records what exists in the **E84** XDF, at E84 addresses, and what does not.

**Inherited-code caveat.** The E84 read is calibration-only (everything below 0x180200 erased 0xFF — no program code), so every code-level statement here (readers such as FUN_000d6450, banked slots such as 04ab5c, `adpcond_run_finish`, the table-0x4aeec indexing) inherits from the E70 RE. Items were carried over by porting the E70 XDF; every ported item states the method and delta in its XDF description (`|| E84 8609556: ported from E70 by content match (exact|interval), delta +0x…`). Per-region deltas differ (+0x2d0, +0x35c, +0x46c, +0x4d4, +0x5da8 …), so **never reuse an E70 address on the E84**. All addresses below are the start of the item's embedded data (first axis vector; value address for scalars) as mapped in `8hpe84_cali_v1.xdf`. Note: a few XDF *descriptions* in this group still print the E70 `@` address (blocked tables and Ghidra-imported records); the embedded-data pointers are authoritative.

**Port column:** *exact* = byte-identical to the E70 calibration; *interval* = length-preserved interval mapping — the E84 content **differs** from the E70, i.e. those tables hold E84-native values. Do not copy E70 values over an *interval* item.

Port coverage for this chapter's E70 categories (from `docs/e84/data/e84_port_report.json`):

| Category | E70 items | Ported | Not portable |
|---|---|---|---|
| Adaptation: fill | 17 | 16 | 1 |
| Adaptation: shift | 7 | 6 | 1 |
| Adaptation: driving situation | 26 | 24 | 2 |
| Adaptation: other | 1 | 1 | 0 |
| Unlabelled: Adaptation | 1 | 1 | 0 |
| Ghidra new: adaptation | 305 | 32 | 273 |

The original E70-documented families survived almost completely (48 of 52); the Ghidra-new adaptation records — fine-grained per-shift-type and per-set internals labelled from the E70 decompile — mostly did **not** relocate in the cal-only read (32 of 305). Anything marked "not in the E84 XDF" below needs a full flash read to recover.

Temperature convention, as on the E70: stored value = °C + 40 (so 90..150 = 50..110 °C).

### Adaptation: fill

16 of 17 E70 items. Missing: **`adpshfill_up_step_map_7to8`** — not in the E84 XDF (needs full flash read). Its sibling 6→7 map ported, so upshift fill trim is editable for 6→7 but blind for 7→8.

| Parameter | E84 addr | Port | What it does (per E70 RE) | Confidence |
|---|---|---|---|---|
| `adpshfill_dn_step_map_4to3` / `_5to4` | 0x198D48 / 0x198DB4 | exact | s16 8×4 downshift fill step maps (x deviation −20..30, y −50..20, z stock all 0). Banked blocks 04ab5c/04ab68+4, reader FUN_000d6450. | HIGH |
| `adpshfill_dn_target_time (4>3 .. 5>4)` (+ axis) | 0x198D3C (axis 0x198D38) | interval | Downshift fill target times, 2-pt blocked curves, z 100. **E84-native content.** | MED |
| `adpshfill_dn_target_time (7>6 .. 8>7)` | 0x198E7C | exact | Same, for 7→6 / 8→7. | MED |
| `adpshfill_up_step_map_6to7` | 0x198ADC | exact | s16 8×6 upshift fill step map (x −23..38, y torque 40..250, z −300..300). | MED |
| `adpshfill_up_trq_max_5to6` (2 copies) | 0x198910, 0x198A98 | exact | Max torque for 5→6 upshift fill adaptation to learn (z 40..150). Slots 04aac0/04aaf0+8. | HIGH |
| `adpshfill_up_trq_max_6to7` | 0x198B5C | exact | Same for 6→7 (z 150..250). | HIGH |
| `adpshfill_up_turb_min_6to7` | 0x198B8C | exact | Min turbine speed (~1200 rpm) for 6→7 fill adaptation. | HIGH |
| `adpfill_cond_curve` | 0x19932C | exact | u8 enable/condition curve (x 4/5/60, z 6). | MED |
| `adpfill_cond_curve_b` | 0x199308 | interval | u8 2-pt condition curve. **E84-native content.** | MED |
| `adpfill_elem_curve_2` / `_3` | 0x1993DC / 0x1993FC | exact | Per-element fill values (slots k=2/3 of the 0x4aeec array), z 90. | MED |
| `adpfill_b_pair_curve` | 0x1993AC | exact | Companion per-index fill curve, same reader family. | MED |
| `adpshfill_class_map` | 0x199214 | exact | XDF constant, layout pinned s16 5×10: cell-class selection for fill adaptation (hypothesis — reshaping class boundaries changes *where* corrections are stored). | MED |

### Adaptation: shift

6 of 7 E70 items. Missing: **`adpshift_map_turb_31`** — not in the E84 XDF (needs full flash read). All read by the shift-adaptation evaluator FUN_000d52d4 (E70 code).

| Parameter | E84 addr | Port | What it does | Confidence |
|---|---|---|---|---|
| `adpshift_dev_map` | 0x197668 | exact | s16 8×4: deviation (−100..40) × turbine speed (600..2800) → correction (−70..60). | MED |
| `adpshift_map_turb_2` / `_turb_3` | 0x197728 / 0x197788 | exact | Same shape, slots k=2/k=3 of the ~35-entry per-shift-type array (y 1000..3250 / 1750..4000). | MED |
| `adpshift_grad_curve` | 0x19746C | interval | Gradient-dependent weighting (x −20..50). **E84-native content.** | MED |
| `adpshift_hold_curve` | 0x197454 | exact | Hold/decay factor over a 0..50000 counter, z 100. | MED |
| `adpshift_time_curve` | 0x19739C | exact | Shift-time-dependent weighting (x 20..2000 ms-shaped, z 0..50). | MED |

More slots of the same array are present beyond the E70 chapter's scope: `adpshift_map_turb_7` @ 0x19714E ported with the Ghidra-new batch (see below), and ~24 further `adpshift_map_turb_*` siblings (turb_8..turb_35, numbering with gaps) came over with the unlabelled-structure port at LOW confidence — grep the XDF by title if you need one. The Ghidra duplicates of turb_2/3 at their code-side E70 addresses and turb_0/1/4/5 did not port.

### Adaptation: driving situation

24 of 26 E70 items. Missing, both not in the E84 XDF (needs full flash read):

- **`adp_eval_curve_a`** — one of the three driving-situation evaluation thresholds.
- **`adpcond_temp_curve`** — the oil-temperature-dependent enable threshold (reader `adpcond_enable_check`). On the E70 this was the first place to look when adaptation seemed inactive; on the E84 that gate is not editable (and not inspectable) without a full read.

| Parameter | E84 addr | Port | What it does | Confidence |
|---|---|---|---|---|
| `adp_eval_curve_b` / `_c` | 0x198688 / 0x198698 | exact | Evaluation thresholds (x 40..200 / 100..250, z 0 / 300..900). | MED |
| `adp_eval_time_curves` (2 copies) | 0x1987A8, 0x1987B8 | exact | Time constants (ms-shaped z 2000..3500 / 1200), via table 0x4ab08 +0x10/+0x14. | MED |
| `adpcell_press_map_a..f` | 0x199790 / 0x1997EC / 0x199848 / 0x1998A4 / 0x199900 / 0x19995C | exact | Six per-cell reference pressure maps, consecutive, stride 0x5C; s16 6×5, x rpm 500..1500 (d/e 600..1200), y pedal/temp 40..130, z 11..69 / 12..45 / 14..47 / 60 / 60 / 97..140. Readers FUN_000b4f40 / FUN_000b5128 via adpcell_c2804. | HIGH |
| `adpcell_delta_curve` | 0x1999B4 | exact | Measured error → per-update correction (x −100..100, z −80..100). | HIGH |
| `adpcell_limit_curve` | 0x1999D0 | exact | Cap on accumulated cell correction (z 100 over x 0..10000). | HIGH |
| `adpcond_corr_curve` | 0x1995D8 | exact | 2 blocked copies (set2, set3): end-of-run correction, deviation −200..200 → −250..250. Banked slot 04afb0+1c, reader `adpcond_run_finish`. | HIGH |
| `adpcond_curve_a` | 0x198678 | exact | Enable gate (x −50/0/50, z 26). | MED |
| `adpcond_curves` (2 copies) | 0x198788, 0x198798 | exact | Via 0x4ab08 +0x8/+0xC (z 100..250 / 40). | MED |
| `adpcond_hold_curve` | 0x198630 | exact | Hold factor over 0..50000, z 100 (mirrors `adpshift_hold_curve`). | MED |
| `adpcond_slip_map` | 0x198C70 | exact | s16 8×4 slip window, z stock 0. | MED |
| `adpcond_window_map` | 0x198708 | interval | s16 8×6 allowed band over torque-shaped y 40..250 (z −150..200). **E84-native content.** | MED |

**Per-set temperature and timing gates** (4 block copies each, set0..set3 — the blocked originals; the Ghidra pass later also labelled individual per-set copies, which appear as separate alias entries in the XDF):

| Parameter | E84 addr (first copy) | Port | Stock values | Confidence |
|---|---|---|---|---|
| `adpcond_min_temp_curve` (+ axis 0x1994BC) | 0x1994C2 | exact | x 2..8 per set, z 90 | MED |
| `adpcond_temp_u8_curve` | 0x19948C | exact | x 90..150 (degC+40), z 250 | MED |
| `adpcond_time_ofs_curve` | 0x199474 | exact | x 0..95, z 200..12000 (ms-shaped) | MED |
| `adpcond_ramp_rate_curve` | 0x199464 | exact | x 0..200, z 10..100 | MED |

### Adaptation: other

**`adapt_torque_curve_10`** — 0x1B7B60, exact, s16 4-pt (x −48..300 torque-shaped, z −20..−15). Confidence **LOW**: member of banked block T=04e37c k=358 on the E70, no reader bound. Do not change until a reader is identified (and that identification needs the E84 program ROM anyway).

### Unlabelled: Adaptation

**`adpcond_temp_u8_curve_set0`** — 0x199498, exact. This is the item the E70 chapter documented as `auto_adpcond_run_finish_199028` (s16 8×1, x −200..200, z −250..250, read by `adpcond_run_finish`); the Ghidra label pass renamed it. Its shape still matches `adpcond_corr_curve` exactly, so the "further per-set copy of the correction curve" hypothesis stands — treat the current title with suspicion. Confidence **LOW**.

### Ghidra-new adaptation records (32 of 305 ported)

The wr/xdf-ghidra-labels pass added 305 adaptation records to the E70 XDF, mostly fine-grained relabels of the per-shift-type arrays and the banked condition-set internals. Only 32 relocated in the cal-only E84 read; the other 273 (the `adpshift_map_temp_*` series except two, `adpshift_map_b_2..6`, `adpshift_weight_curve`, `adpeng_time_corr_alt_set2`, the turb duplicates, …) are not in the E84 XDF (needs full flash read). The survivors:

**Engagement-time corrections** (garage shift / element mode, fam_ee_tcc, Ghidra MED) — x = engagement time in cycles, z = correction to the garage-shift cell or element fill value; `alt` variants used when the element has elemprot status 5:

| Parameter | E84 addr | Port |
|---|---|---|
| `adpeng_time_corr_set0` / `alt_set0` | 0x19635C / 0x196380 | exact |
| `adpeng_time_corr_set1` / `alt_set1` | 0x1963A4 / 0x1963C8 | exact |
| `adpeng_time_corr_set2` | 0x1963EC | exact |

**Shift-adaptation internals** (Ghidra LOW): `adpshift_gain_curve` 0x1965E4 exact (u32-count indexed array, z gain %); `adpshift_map_b_0` 0x196600 interval / `_b_1` 0x19664C exact (6×4, z stock 100); `adpshift_map_temp_9` 0x196C28 / `_temp_10` 0x196C88 exact (8×4, adaptation value × oil temp → −30..40); `adpshift_map_turb_7` 0x19714E exact.

**Fill-adaptation arming windows, 5→6** (fam_ee_tcc, Ghidra MED) — x = element adaptation count, z = turbine rpm window at shift start to arm learning: `adpshfill_up_turb_max_5to6` 0x198454 exact (z 2300) and `adpshfill_up_turb_min_5to6` 0x198464 exact (z 1200). Plus `adpshfill_dn_target_time_3to2` 0x1986F4 exact (MED) and the scalar `adpshfill_dn_step_map_3to2` 0x1986FC exact.

**Condition-set records set1..set3** (fam_t58874 — the banked blocks at E70 0x198c18/0x198cb8/0x198d58; the Ghidra comments pin the meanings: min_temp = minimum oil temperature per adaptation count (MED), start_press = start pressure of the run in mbar, stock all zero except element B 710..1230 (MED), ramp_rate = pedal-dependent ramp rate (MED), corr = end-of-run deviation→mbar correction with ±15 deadband (MED), temp_u8/time_ofs LOW):

| Set | min_temp | start_press | ramp_rate | time_ofs | temp_u8 | corr |
|---|---|---|---|---|---|---|
| set1 | 0x1990F0 exact | 0x199104 exact | — | — | — | — |
| set2 | 0x199190 exact | 0x1991A4 interval | 0x199138 interval | 0x199148 exact | 0x199160 interval | 0x19916C exact |
| set3 | 0x199230 interval | 0x199244 exact | 0x1991D8 interval | 0x1991E8 interval | 0x199200 exact | 0x19920C exact |

(Full titles as in the XDF: `adpcond_min_temp_curve_set1_0x198c18`, `adpcond_start_press_map_set1`, `adpcond_ramp_rate_curve_set2`, `adpcond_time_ofs_curve_set2`, `adpcond_temp_u8_curve_set2`, `adpcond_corr_curve_set2`, etc. The set1 ramp_rate/time_ofs/temp_u8/corr records of this block did not port.) A separate `adpcond_time_ofs_curve_set1` @ 0x199514 exact also came over with this batch (u8 4-pt, z 0..3, no Ghidra comment, LOW) — an individual per-set copy in the gates region above, not part of the banked set1 record.

**Misc** (Ghidra LOW): `adpx_curve_2c` 0x199288 exact (6×1, z % 100..150) and `adpcell_map_1c` 0x19937C interval (speed × oil temp → 12..45).

### What remains usable on the E84

- **Cell baseline pressures** (`adpcell_press_map_a..f` + delta/limit bounds) — the HIGH-confidence core of the group — ported byte-identical. These are the knobs if adaptation keeps walking a launch/garage-shift pressure away from your tune.
- **Fill step maps** for 4→3, 5→4 (HIGH) and 6→7 (MED) are editable; **7→8 is not** (map missing).
- **Learning windows** (torque caps 5→6/6→7, turbine minimum 6→7, plus the Ghidra 5→6 turbine arm window) all present — these decide *when* the TCU trusts a sample.
- **Enable gates**: mostly present, but the oil-temperature enable `adpcond_temp_curve` and `adp_eval_curve_a` are gone. If adaptation seems inactive on the E84, you cannot check or move the temperature gate from the XDF.
- *interval*-tagged items hold E84-native data — they are the places this calibration genuinely differs from the E70, and E70 values must not be pasted into them.

As on the E70: if you retune shift pressures or times elsewhere, these parameters decide how strongly the TCU fights or cooperates with the change. Widening the adaptation bounds masks hardware deviation *and* mistakes.

Coverage: 48 of the E70 chapter's 52 items are in the E84 XDF (4 not portable), plus 32 of 305 Ghidra-new adaptation records.
