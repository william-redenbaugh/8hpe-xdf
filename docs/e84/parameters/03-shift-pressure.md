# Shift pressure (clutch pressure during shifts) — E84

E84 X1 (GKE233, cal ZB 8609556, SW Z5YD7900_8HPXY_K790D), `8hpe84_cali_v1.xdf`. This is the E84 edition of the E70 chapter ([docs/e70/parameters/03-shift-pressure.md](../../e70/parameters/03-shift-pressure.md)); read that one first — the physics, the phase model, the family meanings and the reader-function evidence all live there and are **inherited**, not re-proven, here. The E84 read is calibration-only (everything below 0x180200 is erased 0xFF), so there is no E84 program code: every code-level statement (reader functions `FUN_000xxxxx`, banked pointer tables `0x4f560` etc.) refers to the **E70** program ROM of the same Bosch iTCU2 / SH-2A family and is assumed, not verified, for the E84's earlier-generation K790D software.

How this chapter was produced: the E70 XDF entries were ported onto the E84 image by content matching (byte-exact match, length-preserved interval mapping, record-stream walking using the decompile-verified record grammars, global signature alignment, regional delta voting). Every ported table says so in its XDF description — look for `|| E84 8609556: ported from E70 by content match (<method>), delta +0x…`. For `exact` matches the E84 bytes equal the E70 bytes by construction, so the value ranges quoted in the E70 chapter hold; for `interval`/`walk`/`globalign`/`regvote` matches the structure is verified but the stored values may differ — check in TunerPro before trusting a quoted range. Porting never upgrades confidence: treat every E84 entry as at most the E70 confidence level, with the class/block↔reader attribution one notch softer.

**Port outcome for this group** (numbers from the port report; every E84 address below is from `8hpe84_cali_v1.xdf`):

| Category | E70 items | Ported | Not ported | Dominant method / delta |
|---|---|---|---|---|
| Shift pressure: upshift base (b_up) | 51 | 51 | 0 | exact ×43, interval ×8; delta +0x6F54 (+0x5E80 for the 0x1B81xx pair) |
| Shift pressure: upshift phases / torque | 60 | 42 | 18 | exact ×31, walk ×9, interval ×1, globalign ×1 |
| Shift pressure: downshift base (b_dn) | 142 | 139 | 3 | exact ×130, interval ×9; delta mostly +0x6F54 / +0x5E80 |
| Shift pressure: downshift phases / torque | 153 | 140 | 13 | exact ×133, walk ×7 |
| Shift pressure: other | 13 | 7 | 6 | exact ×7 |
| Unlabelled: Shift pressure | 1 | 1 | 0 | exact |
| Ghidra new: shift pressure | 1169 | 169 | 1000 | exact ×110, interval ×52, walk ×2 (164 tables grep-able in the category) |

Everything that did not port is listed by name in its section below with the plain statement: **not in the E84 XDF (needs full flash read)**. A recurring pattern, verified below: several *grouped* multi-block E70 tables failed to port while their per-member *singles* did port under the `Unlabelled:` structural categories or `Ghidra new: shift pressure` — before declaring a parameter lost, grep for it: `/usr/bin/python3 tools/xdf_ls.py 8hpe84_cali_v1.xdf -s <name>`.

Checksums: the E70 checksum algorithm does **not** reproduce on the E84 read (`xdf_checksum.py` search fails). Sign edited bins via the flash tool — xHP corrects checksums itself.

### Shift pressure: upshift base (b_up)

**51 of 51 E70 items ported** — the complete base upshift set survived. The whole block moved by +0x6F54 except the zero-valued `press_ofs`/`sync_time_thr` pair, which sits much earlier (+0x5E80). Family meanings, axes and z ranges: see the E70 chapter; `exact`-matched members are byte-identical.

| Family | E84 members | E84 address range | Confidence (inherited) |
|---|---|---|---|
| **shift_press_b_up_press_torque** (+ axis) | 4 + 1 | 0x1BBF5C–0x1BD1C4 | MED |
| **shift_press_b_up_press_ofs** | 1 | 0x1B8128 | MED |
| **shift_press_b_up_oiltemp_press_ofs** (+ axis) | 4 + 3 | 0x1BBEE0–0x1BCA86 | MED |
| **shift_press_b_up_ph2_end_ofs** | 18 | 0x1BBF84–0x1BD1EC | MED |
| **shift_press_b_up_ph3_time_ofs** | 7 | 0x1BBFEC–0x1BCF6C | MED |
| **shift_press_b_up_ph3_time_grad_ofs** (+ axis) | 3 + 3 | 0x1BBE50–0x1BC9F8 | MED |
| **shift_press_b_up_ph4_trq_add** | 5 | 0x1BD254–0x1BD71C | MED |
| **shift_press_b_up_sync_time_thr** (+ axis) | 1 + 1 | 0x1B8114–0x1B811C | MED |

### Shift pressure: upshift phases / torque

**42 of 60 E70 items ported.** This is where the first real E84 gaps appear, and unfortunately they include the group's only HIGH-confidence item.

| Family | E84 members | E84 address range | Confidence (inherited) |
|---|---|---|---|
| **shift_press_up_trq_press** | 3 | 0x1C5EE4–0x1C73FC | MED |
| **shift_press_up_trq_add** | 9 of 13 | 0x1C6098–0x1C8D20 | MED |
| **shift_press_up_trq_add_alt** | 4 | 0x1C9E88–0x1CAA28 | MED |
| **shift_press_up_alt** (c0 1>2) | 1 | 0x1C5E40 | MED |
| **shift_press_up_ph1_time / ph9_time / ph9_time_alt** | 1 + 15 + 1 of 21 | 0x1C5E0C–0x1CAE2C | MED |
| **shift_press_up_ph1/ph19_sync_time** (+ axis) | 3 of 5 | 0x1C3030 / 0x1C3064 / axis 0x1C3044 | MED |
| **shift_press_up_sync_thresh** (+ axis) | 2 | 0x1C7ECC–0x1C7ED0 | MED |
| **shift_press_up_phase_cycle_curve** | 1 | 0x1C9C00 | MED |
| **shift_press_up_shiftexec_add** | 1 | 0x1CA4A0 | MED |
| **shift_press_up_ph13_base** | 1 | 0x1CAA98 | MED |

Not ported — **not in the E84 XDF (needs full flash read)** unless a replacement is noted:

- **`shift_press_up_oiltemp_pct_1to2`** — the group's single **HIGH** item, the 100–150 % oil-temperature factor on the phase-9 duration and upshift pressure-offset accumulator. Its loss means the proven phase-9 timing formula from the E70 chapter cannot currently be calibrated on the E84.
- `shift_press_up_trq_add_c2` 2>3 / 3>4 / 5>6 / 6>7 (four of the thirteen `trq_add` copies). A relabelled c2 single for 5>6 exists in `Ghidra new: shift pressure` (`shift_press_up_trq_add_c2_5to6_0x1cbafc`, 0x1D87A8).
- `shift_press_up_ph9_time_c2` 2>3 / 3>4 / 5>6 / 6>7. Ghidra-new singles cover part of this (`..._c2_5to6_0x1cbb80` at 0x1D882C, `..._c2_7to8_0x1cc030` at 0x1D8D98).
- `shift_press_up_ph1_sync_time (4>5 .. 5>6)` — a per-member single survives as `shift_press_up_ph1_sync_time_3to4` at 0x1CFCBC (Unlabelled: s16 curves).
- `shift_press_up_ph19_sync_time (1>2 .. 3>4)` — Ghidra-new single `shift_press_up_ph19_sync_time_2to3` at 0x1CFCB4.
- `shift_press_up_ph10_ramp` (all three grouped runs) — **replaced**: seven Ghidra-new per-class singles `shift_press_up_ph10_ramp_c0/c1/c2_*` at 0x1D5660–0x1D8940.
- `shift_press_up_ph4_trq_add` (+ its axis) and `shift_press_up_ph13_trq_add` — the ph4 adder is gone entirely; for ph13, singles survive: `shift_press_up_ph13_trq_add_1to2` at 0x1DA8DE (Ghidra new: shift pressure) and `..._7to8` at 0x1DA85E (filed under Unlabelled: Shift strategy).
- `shift_press_up_start_press_temp` (grouped 3>4/6>7) — Ghidra-new single `shift_press_up_start_press_temp_7to8` at 0x1DAB5E.

### Shift pressure: downshift base (b_dn)

**139 of 142 E70 items ported** — near-complete, overwhelmingly by exact byte match (130 of 139). The big base-pressure and torque→pressure maps for every direct and skip downshift are all present.

| Family | E84 members | E84 address range | Confidence (inherited) |
|---|---|---|---|
| **shift_press_b_dn_press_cls0–2** | 10 | 0x1B82DC–0x1B9E0C | MED |
| **shift_press_b_dn_press_alt_cls0/1** | 4 | 0x1B891C–0x1B9964 | MED |
| **shift_press_b_dn_press_ofs** (+ axis) | 2 + 2 | 0x1B8D14–0x1B9B00 | MED |
| **shift_press_b_dn_trq_press** | 35 | 0x1BD860–0x1C2090 | MED |
| **shift_press_b_dn_ph10_press_add** | 11 | 0x1BD2BC–0x1C1AEC | LOW/MED |
| **shift_press_b_dn_ph11_time** | 12 of 13 | 0x1BD7F8–0x1C1948 | MED |
| **shift_press_b_dn_ph12/ph15 ramp** (incl. `_alt`, axes) | 23 | 0x1B8D28–0x1C2DE4 | MED |
| **shift_press_b_dn_ph13_ramp_add** | 19 | 0x1BDAF0–0x1C1A88 | MED |
| **shift_press_b_dn_ph15_rampout_time** (+ axis) | 4 + 3 | 0x1BDAE0–0x1C1028 | **HIGH** |
| **shift_press_b_dn_ph12_sync_time** (c0 4>3) | 1 | 0x1BDBA0 | HIGH |
| **shift_press_b_dn_sync_time_thr** (+ `_alt`) | 5 + 2 | 0x1B82B0–0x1B9B7C | MED |
| **shift_press_b_dn_outgrad_add** | 3 | 0x1C21CC–0x1C2CD0 | MED |
| **shift_press_b_dn_ph13_add_temp_pct** (+ axis) | 2 + 1 | 0x1C21FC–0x1C2954 | MED |

Not ported:

- **`shift_press_b_dn_adapt_temp_ofs`** (both grouped runs: direct pairs 3>2..5>4 and skip pairs 4>2..8>4) — the grouped tables are not in the E84 XDF, but three per-member singles did port under the Unlabelled structural categories: `shift_press_b_dn_adapt_temp_ofs_5to4` at 0x1CEB48, `..._5to1` at 0x1CF098 (Unlabelled: s16 maps) and `..._8to4` at 0x1CF944 (Unlabelled: s16 curves). The remaining pairs need a full flash read.
- `shift_press_b_dn_ph11_time_c1_6to4` — not in the E84 XDF (needs full flash read).

### Shift pressure: downshift phases / torque

**140 of 153 E70 items ported.** The main downshift firmness levers (`trq_press`, `trq_press_b`, `trq_add`, `ph11_press_add`) are essentially complete.

| Family | E84 members | E84 address range | Confidence (inherited) |
|---|---|---|---|
| **shift_press_dn_trq_press** | 24 | 0x1CAF64–0x1CEEEC | MED |
| **shift_press_dn_trq_press_b** | 9 | 0x1CFCD4–0x1D242C | MED |
| **shift_press_dn_trq_add** | 31 | 0x1CB0C4–0x1CF1F8 | MED |
| **shift_press_dn_ph11_press_add** | 23 of 25 | 0x1CB364–0x1CEF94 | MED |
| **shift_press_dn_ph9_time** | 3 of 6 | 0x1CB0B4–0x1CE634 | **HIGH** |
| **shift_press_dn_ph1/ph4/ph12_sync_time** | 4 of 9 | 0x1C3210 / 0x1C31B8 / 0x1C32B8 / 0x1CB070 | MED/HIGH |
| **shift_press_dn_skip_ph1/ph4_sync_time** (+ axis) | 4 | 0x1C3164–0x1C32A4 | MED |
| **shift_press_dn_ph5_base** | 3 | 0x1CB368–0x1D2360 | MED |
| **shift_press_dn_ph9_base_ofs** | 6 | 0x1B9234–0x1D2334 | MED |
| **shift_press_dn_ph13_ramp** (+ axis) | 1 + 1 of 3 | 0x1D0F8C / axis 0x1CF7B4 | MED |
| **shift_press_dn_ph10_ramp_rate** (+ axis) | 3 + 3 | 0x1CF880–0x1D15CC | MED |
| **shift_press_dn_ph10_ramp_rate_b** | 5 | 0x1CFC14–0x1D23DC | MED |
| **shift_press_dn_ramp_grad** (+ axis) | 2 + 2 | 0x1CF928–0x1D1004 | MED |
| **shift_press_dn_ramp_sync_time** | 1 | 0x1CFA00 | MED |
| **shift_press_dn_ramp_sync_time_b** | 7 | 0x1CFD88–0x1D22E0 | MED |
| **shift_press_dn_outgrad_add** | 5 | 0x1CF6BC–0x1D02C4 | MED |
| **shift_press_dn_oiltemp_curve** (2>1) | 1 | 0x1CF730 | MED |
| **shift_press_dn_grad_map / grad_map2** (2>1) | 2 | 0x1CAF18 / 0x1CB00C | LOW |

Not ported:

- `shift_press_alt_dn_2to1` (the 4-member parameter set living in E70 pointer-table block 0x503f8) — not in the E84 XDF (needs full flash read); it was anchored purely by E70 code structure.
- `shift_press_dn_ph1_sync_time (2>1 .. 3>2)` — only the `_6to5` single survives (0x1C3210).
- `shift_press_dn_ph9_time (c0 7>6 .. c1 7>1)` + its axis, and `shift_press_dn_ph9_time_c2_8to6` — the grouped run is gone, but per-member singles survive scattered: `..._c0_7to6` 0x1CB774, `..._c1_4to3` 0x1CBE24, `..._c1_5to4` 0x1CBFD0, `..._c1_6to3` 0x1CCD30, `..._c1_6to5` 0x1CC17C, `..._c1_7to6` 0x1CC328 (all Unlabelled: s16 maps), `..._c0_6to5` 0x1DAF92 (Unlabelled: model u16 curves), plus Ghidra-new copies `..._c0_5to4` 0x1DAEA0, `..._c0_7to6_0x1ceb0c` 0x1DB298, `..._c2_6to3` 0x1DE296.
- `shift_press_dn_ph11_press_add_c1_5to3` / `_c2_8to6` — Ghidra-new singles exist for both: `..._5to3_0x1d1e34` at 0x1DE1EE and `..._8to6_0x1d29e8` at 0x1DF0F2.
- `shift_press_dn_ph12_sync_time` (c1 2>1..3>2 + axis, c1 3>1..5>1, c2 3>1..5>1) — only the c0 2>1..3>2 run survives (0x1CB070); Ghidra-new singles `..._c2_5to3` 0x1DE252 and `..._c2_8to6` 0x1DF156 cover part of the c2 skip set.
- `shift_press_dn_ph13_ramp (2>1 .. 4>3)` (data run; its axis survived at 0x1CF7B4) — Ghidra-new singles `shift_press_dn_ph13_ramp_2to1/3to2/4to3` at 0x1DF262 / 0x1DF5EE / 0x1DF97A.
- `shift_press_dn_temp_curve_2to1` (LOW) — not in the E84 XDF (needs full flash read); no replacement found.

### Shift pressure: other

**7 of 13 E70 items ported** — and the loss here is the practically important one:

- **`shift_torque_limit_class0–3` + `fallback`: not in the E84 XDF (needs full flash read).** On the E70 these are the 9-gear × 5-slot u16 torque-limit blocks at stride 0x5A — the area the known xHP flash rewrites for "torque limit removal". They are raw u16 arrays with no record header and vehicle-specific content, so none of the content-matching methods could anchor them safely in the E84 image. Until a full flash read recovers the E84 reader (E70: FUN_0012ec10), there is **no defined torque-limit table to edit on the E84**.
- `shift_torque_temp_map_set3` — not in the E84 XDF (needs full flash read). Its siblings survived: **shift_torque_temp_map_set5** at 0x1B67E0 and **set8** at 0x1B69F0 (6×4 s16, MED).

Ported: the four **shift_temp_curve_cb3c** curve tables at 0x1B6730–0x1B69D8 (MED), the two torque/temperature maps above, and **shiftpt_curve_fa2** at 0x1DA7DC (5×1 u16, LOW). All seven by exact byte match.

### Unlabelled: Shift pressure

| Parameter | E84 address | Shape/type | Notes | Confidence |
|---|---|---|---|---|
| **shiftexec_up_trqred_coolant_scale_1to2** | 0x1B4F3C | 4×1 curve (s16) | The E70 chapter documented this structure as `auto_shift_torque_curve_1af8e4` (x 0..400, z flat 1300, read by `shift_torque_curve`); the Ghidra hp8_sh (2026-10-15) pass renamed it as a coolant-temp × torque scale on the upshift torque-reduction path. Ported exact, so byte-identical to the E70 copy. | LOW |

### Ghidra new: shift pressure

**169 of 1169 E70 entries ported; 1000 did not.** (the category holds 169 items: 164 tables plus 5 scalar constants, which a table-only listing undercounts) Methods: exact ×110, interval ×52, walk ×2.

Why the attrition is so bad here, specifically: this category is the output of the hp8_sh Ghidra decompile (2026-10-15) of the **E70 program ROM** — per-phase internals (`ph1_time`, `ph9_time`, `ph9_base_press`, `time_trim`, `dtrq_add`, per-phase ramps and sync thresholds, the whole coast-path family) that live as **packed sub-arrays inside larger calibration records**. Each E70 entry is anchored by a code xref: the banked pointer table and reader function that index into the record. The E84 read has no program region to re-anchor against, and the sub-arrays themselves are tiny, often flat or near-flat (z raw [0..0] is common), i.e. far too low-entropy for safe content matching. Only sub-arrays sitting inside regions that matched byte-exactly or survived length-preserved interval mapping came across. **A full flash read of the E84 would unlock the rest**: decompile the K790D program, rebuild the banked pointer tables for this calibration generation, and re-anchor all ~1000 remaining entries with their own (not inherited) reader evidence — the same applies to the E70's ratio-monitoring and coast/sail Ghidra categories, which ported 5/268 and 0/175.

What did port, in two clusters (treat labels as Ghidra-inherited; grid orientation and scaling flagged "assumed" in the descriptions):

- **Upshift per-class internals**, 0x1CFCB4–0x1DAC1A: `shift_press_up_ph1_time` (8 + 1 alt), `ph9_time` (5 + 4 address-suffixed + 3 alt), `ph9_base_press` (6 — "base pressure (mbar) at the start of phase 9, added to the adaptive value", MED), `time_trim` (11 — "cycles subtracted from the expected time to the phase-9 latch", LOW), `sync_thresh` (7), `trq_press` (7), `trq_add` (3 + 4 suffixed), `ph10_ramp` (7), `ph13_base` (3) and `ph13_base_coast` (2), `ph4_dtrq_add` / `ph9_dtrq_add` singles, `coast_snap` (2), `time_ramp`, `start_press_temp_7to8`, `ph19_sync_time_2to3`.
- **Downshift / coast internals**, 0x1DAE6C–0x1E0456: the 25-table **coast downshift family** `shift_press_dn_coast_*` (ph1_time, ph5_base — "phase 4/5 base pressure level in mbar, coast path", MED — ph5_time, snap, spd_add, add, ph13_ramp), plus `ph13_outgrad_factor`, `ph13_trqrise_add`, `ph5/ph9_dtrq_add`, `sync_lead`, and the dn ph9_time / ph12_sync_time / ph13_ramp singles already cross-referenced above. This is currently the only E84 visibility into the coast/sail downshift path at all.
- One stray: `shift_press_b_dn_press_cls2_5to4` at 0x1C2C94.

Coverage: 544 tables in the E84 XDF across this group's seven categories (51 + 42 + 139 + 140 + 7 + 1 + 164), accounting for 549 of the E70 group's items ported per the report; the 1,040 E70 entries that did not port are named above family-by-family or fall inside the Ghidra-new remainder.
