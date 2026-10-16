# Shift execution (ramps, timing, phase control) — E84

E84 X1 (GKE233, cal ZB 8609556, SW Z5YD7900_8HPXY_K790D), `8hpe84_cali_v1.xdf`. E84 edition of the E70 chapter ([docs/e70/parameters/04-shift-execution.md](../../e70/parameters/04-shift-execution.md)) — the phase model, the `k0..k3`/`c0..c2` variant-block scheme, the `_ti`/`_noti` twin interpretation and all reader-function evidence are documented there and **inherited** here. The E84 read is calibration-only (program region erased 0xFF): reader functions (`FUN_000c7f0a` etc.) and banked block tables (`04d0d4+24`, `04c878 k=n`) are **E70 program addresses**, assumed but not verified for the K790D software generation. As on the E70, the runtime condition that selects a variant block is not pinned — and on the E84 even the block↔reader pairing is one notch softer, since it is inherited through the port rather than traced.

Port provenance: every ported table's XDF description ends with `|| E84 8609556: ported from E70 by content match (<method>), delta +0x…`. `exact` = byte-identical to the E70 copy (quoted z ranges hold); `walk`/`interval`/`globalign` = structure verified by record-grammar walking or region mapping, values may differ — verify in TunerPro. The whole group sits ~+0x4A68..+0x5A08 above its E70 addresses.

**Port outcome for this group** (numbers from the port report; every E84 address below is from `8hpe84_cali_v1.xdf`):

| Category | E70 items | Ported | Not ported | Methods |
|---|---|---|---|---|
| Shift execution: upshift | 107 | 98 | 9 | walk ×36, exact ×35, globalign ×17, interval ×10 |
| Shift execution: downshift | 91 | 91 | 0 | exact ×52, walk ×36, globalign ×3 |
| Shift execution: other | 79 | 73 | 6 | exact ×67, walk ×5, interval ×1 |
| Shift execution: timing control | 1 | 0 | 1 | — |
| Unlabelled: Shift execution | 1 | 1 | 0 | exact |
| Ghidra new: shift execution | 741 | 63 | 678 | exact ×40, interval ×19, walk ×2 (61 tables grep-able in the category) |

As in the shift-pressure chapter: several grouped multi-block E70 tables failed to port while per-member singles survived under the `Unlabelled:` categories — grep by name before declaring a parameter lost: `/usr/bin/python3 tools/xdf_ls.py 8hpe84_cali_v1.xdf -s <name>`.

Checksums: the E70 checksum algorithm does not reproduce on the E84 read; sign via the flash tool (xHP corrects checksums itself).

### Shift execution: upshift

**98 of 107 E70 items ported.** All the big levers survived intact — torque reduction, pressure offsets, ramp-out, the coolant scales. What dropped are grouped k2/k1 runs of the pedal-offset and sync-time-threshold companions, and most of those survive as per-member singles under the Unlabelled categories.

| Family | E84 members | E84 address range | Confidence (inherited) |
|---|---|---|---|
| **shiftexec_up_trq_reduction** `_k0..k3_<pair>` | 21 | 0x1ADA60–0x1AE630 | MED |
| **shiftexec_up_press_ofs_noti** (incl. address-suffixed copies) | 18 | 0x1A9E9C–0x1ABF58 | MED |
| **shiftexec_up_trq_rampout_noti** | 15 | 0x1AA33C–0x1AB368 | MED |
| **shiftexec_up_press_ofs_ti** `_k2_<pair>` | 7 | 0x1AAA34–0x1AAF2C | MED |
| **shiftexec_up_press_pedal_ofs_noti** | 2 of 5 | runs at 0x1AB484 (k0 6>7..k1 3>4), 0x1AB97C (k1 5>6..k2 1>2) | MED |
| **shiftexec_up_sync_time_thr_noti** (+ axis) | 2 of 4 | 0x1AB4FC (axis), 0x1AB502 (k0 7>8..k1 4>5) | MED |
| **shiftexec_up_sync_time_thr_ti** | 1 of 4 | 0x1AAFA4 (`_k3_2to3`) | MED |
| **shiftexec_up_press_pedal_ofs_ti** (+ axis) | 2 of 3 | 0x1AA2B0 (k0 6>7..k1 3>4), axis 0x1AB060 | MED |
| **shiftexec_up_trqinc_coolant_scale** | 24 | 0x1AE818–0x1B2D5C | MED/LOW |
| **shiftexec_up_trqinc_fade_pct** | 2 | 0x1AE6E8–0x1AEA48 | MED |
| **shiftexec_up_trqinc_sync_thr** | 2 | 0x1AE980–0x1AEC08 | MED |
| **shiftexec_up_trq_gate** `_k1_6to7/7to8` | 2 | 0x1ADFA0–0x1AE02C | MED |

Not ported (9), with surviving singles where verified:

- `shiftexec_up_press_pedal_ofs_noti (k2 3>4 .. k2 5>6)`, `(k2 6>7 .. k2 7>8)` and the `(k2 3>4 .. k2 5>6)` axis — singles survive under Unlabelled: s16/u8 maps, e.g. `..._k2_3to4` 0x1ABDB0, `..._k2_6to7` 0x1AC02C, `..._k2_7to8` 0x1AC100.
- `shiftexec_up_press_pedal_ofs_ti (k1 6>7 .. k2 7>8)` — single `..._ti_k1_7to8` at 0x1B0774 (Unlabelled: u8 curves).
- `shiftexec_up_sync_time_thr_noti (k2 1>2 .. k2 4>5)` and `(k2 6>7 .. k2 7>8)` — singles at 0x1ABBB0 (`k2_1to2`), 0x1ABC84, 0x1ABE2C, 0x1ABFD4, 0x1AC0A8 (`k2_7to8`), 0x1B209C (all Unlabelled: s16 maps).
- `shiftexec_up_sync_time_thr_ti (k1 1>2 .. k1 4>5)`, `(k1 6>7 .. k3 1>2)` and that run's axis — singles `..._ti_k1_1to2` 0x1B0194, `..._ti_k1_3to4` 0x1B036C, `..._ti_k3_1to2` 0x1B0E64 (Unlabelled).

Since these are offsets/thresholds stored largely flat (128 / ≈113..128) in the E70 calibration, the practical loss is small; the pedal-offset edits you would actually make live in the two surviving grouped runs plus the singles.

### Shift execution: downshift

**91 of 91 E70 items ported — the group is complete**, and it remains the best-evidenced part of the whole chapter (the E70 RE identified the live reader and banked slot for most members; HIGH confidence inherited, one notch softer on the E84 as the readers are E70 code).

| Family | E84 members | E84 address range | What it does (see E70 chapter) | Confidence |
|---|---|---|---|---|
| **shiftexec_dn_phase4_sync_time** | 23 | 0x1AED6C–0x1B21D4 | Phase-4 sync-time budget (E70 reader FUN_000c7f0a, slot +0x20) | HIGH (22) / LOW (1) |
| **shiftexec_dn_blip_trq** | 21 | 0x1AECEC–0x1B1BF4 | Throttle-blip torque request, >128 = positive torque add (FUN_000c8f92, +0x18) | HIGH (20) / LOW (1) |
| **shiftexec_dn_blip_scale** | 19 | 0x1AED8C–0x1B24A4 | 0–100 % blip strength schedule per operating point (FUN_000c91f8, +0x24) | HIGH (18) / LOW (1) |
| **shiftexec_dn_phase3_time** | 18 | 0x1AF3F8–0x1B25B0 | Phase-3 duration, raw time units (FUN_000c8c9c, +0x1c) | HIGH |
| **shiftexec_dn_phase3_blend_pct** | 9 | 0x1AECCC–0x1B0D0C | Phase-3 blend percentage (FUN_000c92d8, +0x14) | HIGH (8) / LOW (1) |
| **shiftexec_dn_blip_coolant_scale** `_2to1` | 1 | 0x1B263C | Coolant scale on the 2>1 blip; flat 255 as stored | MED |

For rev-match/downshift feel tuning on the E84 this is the place to start: complete coverage, the strongest inherited evidence, and 52 of the 91 members byte-identical to the E70 values.

### Shift execution: other

**73 of 79 E70 items ported.**

**shift_elem_dn_sync_thr** — all 27 members, 0x1B5830–0x1B62B0 (4×4 u8, `c0..c2` per downshift pair incl. skip shifts). Sync *entry* threshold; E70 reader FUN_000ee186. MED.

**shift_elem_dn_sync_end_thr** — 25 of 26 members, 0x1B5850–0x1B62D0. Sync *end* threshold; E70 reader FUN_000ee0ca. HIGH/MED inherited. **`shift_elem_dn_sync_end_thr_c1_7to1` is not in the E84 XDF (needs full flash read).**

**Engagement set (`shiftexec_engage_*`)** — 16 of 20 members, 0x1ACF70–0x1AD894:

| Family | E84 members | E84 addresses | Confidence |
|---|---|---|---|
| shiftexec_engage_trq_enable | 5 (set2 ×3, set3, set8) | 0x1AD08C, 0x1AD188, 0x1AD284, 0x1AD424, 0x1AD7F8 | LOW/MED |
| shiftexec_engage_trq_rampout_pct | 4 (set2 ×2, set3, set8) | 0x1AD284, 0x1AD380, 0x1AD47C, 0x1AD850 | MED |

> **Address collision (port artifact):** one `shiftexec_engage_trq_enable` set2 copy and `shiftexec_engage_trq_rampout_pct` set2 are both defined at **0x1AD284** - the same class of artifact as chapter 11's collision list. Treat one of the two slots as suspect and verify against live behaviour before editing either.
| shiftexec_engage_trq_red | 3 of 4 (set0, set3, set8) | 0x1ACF70, 0x1AD444, 0x1AD818 | MED |
| shiftexec_engage_sync_time_thr (+ axis) | 2 of 3 (set3..set8 run) | 0x1AD4B6, axis 0x1AD4B0 | MED |
| shiftexec_engage_trq_red_elem | 1 of 2 (set2) | 0x1AD3EC | MED |
| shiftexec_engage_press_ofs | 1 of 2 (set8) | 0x1AD894 | MED |

Not ported from the engagement set: `shiftexec_engage_press_ofs (set1 .. set2)`, `shiftexec_engage_sync_time_thr (set1 .. set2)`, `shiftexec_engage_trq_red_elem_set1`, `shiftexec_engage_trq_red_set2` — not in the E84 XDF (needs full flash read). Note the Ghidra-new category adds a **set7** pair and extra set8 records (below), so the E84 engagement picture is differently shaped, not just smaller.

**Standalone tables** — 5 of 6 ported:

| Parameter | E84 address | Confidence |
|---|---|---|
| shiftexec_ratio_torque_map | 0x1AC554 | MED |
| shift_phase_time_curve | 0x1B3E1C | LOW |
| engtime_map_a | 0x199F2C | LOW |
| shiftinh_low_engspd_curve | 0x1D2774 | LOW |
| shiftsync_temp_curve | 0x199FA4 | LOW |

**`shift_skip_rule_table`: not in the E84 XDF (needs full flash read).** On the E70 this is the HIGH-confidence u8[25][14] rule matrix deciding which skip-shift sequences are permitted (matched row-by-row against the 14-byte shift vector by E70 code 0x11811a). It is a raw rule array with no record header, so nothing could anchor it in the E84 image. Consequence: multi-gear downshift *permissions* cannot currently be inspected or edited on the E84.

### Shift execution: timing control

**0 of 1 ported — the category is empty in the E84 XDF.** `shift_time_cap_by_gear` (E70: u8[25] per-gear cap on shift time, read by FUN_00117662) is a raw byte array with no structure to match on: **not in the E84 XDF (needs full flash read).**

### Unlabelled: Shift execution

| Parameter | E84 address | Shape/type | Notes | Confidence |
|---|---|---|---|---|
| **auto_shiftexec_dn_blip_outgrad_scale_1ad67c** | 0x1B2648 | 6-pt s16 curve | x −800..1000, z 0..100; read by the E70 function labelled `shiftexec_dn_blip_outgrad_scale` — an output-gradient scaling of the downshift blip. Ported exact (byte-identical). | LOW |

### Ghidra new: shift execution

**63 of 741 E70 entries ported; 678 did not.** (the category holds 63 items: 61 tables plus 2 scalar constants) Methods: exact ×40, interval ×19, walk ×2 — 50 of the ported members share one delta, +0x5648, i.e. they came across as a single contiguous region.

Same failure mode as the Ghidra-new pressure category: these labels come from the hp8_sh Ghidra decompile (2026-10-15) of the **E70 program ROM** and name packed sub-arrays inside larger records, anchored by E70 code xrefs. With the E84 program region erased there is nothing to re-anchor against, and the sub-arrays are too small and too flat to content-match on their own. **A full flash read would unlock the remaining 678** — including the `shiftexec_up_press_temp_ofs_*` families, `shiftexec_up_trqinc_start_thr_*`, the `shift_offset_c_NN` series and the per-pair copies of everything below — with native E84 reader evidence instead of inherited anchors. (Partial consolation, verified by grep: a dozen-plus `shiftexec_up_press_temp_ofs_*` singles did port as structural entries under the Unlabelled categories, e.g. `..._ti_k2_5to6` 0x1B0C74, `..._noti_k2_3to4` 0x1B1E4C, `..._mode2_2to3` 0x1B2300.)

What did port is genuinely useful — one contiguous block at **0x1B4020–0x1B4E64** that extends the upshift torque-intervention picture well beyond the original E70 doc families:

- **`shiftexec_up_trq_gate_k0/k1/k2_<pair>`** — 21 tables (0x1B4020–0x1B4BE0), a full gate per variant block and gear pair where the original category had only two (k1 6>7/7>8). Per the Ghidra read: 4×4 s16, x = engine torque demand (Nm), y = engine speed (rpm), **z = s16 Nm added to the torque reduction; +200 cancels the reduction, −200 deepens it; result clamped ≤ 0** (MED). This is the per-operating-point knob on how much torque is actually pulled during an upshift.
- **`shiftexec_up_trq_reduction_k0..k3_<pair>`** — 27 tables (0x1B4128–0x1B4E10, many address-suffixed), a second full torque-reduction record set covering k0–k3, alongside the original 21-member family at 0x1ADA60–0x1AE630. Which set the K790D software reads is unknown without code — log before tuning, or edit both consistently.
- **`shiftexec_up_trq_grad_limit_1to2`** at 0x1B4E64 — 6×6 s16, x = turbine-speed gradient, y = input torque; "z×6 Nm: phase-9 torque request and lower cap on the phase-10 reduction" (MED).
- **Engagement extras** at 0x1B3E68–0x1B3EC0: `shiftexec_engage_sync_time_thr_set7` 0x1B3E68, `shiftexec_engage_press_ofs_set7` 0x1B3E78, plus second set8 records `..._trq_enable_set8_0x1ae988` 0x1B3EA0 and `..._trq_red_set8_0x1ae9a8` 0x1B3EC0.
- Downshift singles: `shiftexec_dn_trq_reduction_k2_4to3` 0x1B817C, `shiftexec_dn_phase3_blend_pct_k2_4to3` 0x1B81B4, `shiftexec_dn_sync_time_thr_k2_7to1` 0x1B9028.
- Scattered torque-increase singles: `shiftexec_up_trqinc_sync_thr_6to7_0x1aa0c4` 0x1AEB30, `..._trqinc_fade_pct_1to2_0x1af87c` 0x1B4EC8, `..._trqinc_sync_thr_1to2` 0x1B4ED8, `..._trqinc_coolant_scale_5to6_0x1afc84` 0x1B52C8, and `shiftexec_up_press_pedal_ofs_noti_k0_3to4_0x1ac32c` 0x1B1180.

---

**Naming/legend:** as in the E70 chapter — `<n>to<m>` = gear pair; `k0..k3` / `c0..c2` = runtime-selected variant blocks (selection condition not pinned, and on the E84 not even traceable without code); `set#` = engagement variants; `_ti`/`_noti` = twin paths (plausibly with/without engine torque intervention — label interpretation); trailing `_0x1a....` = the E70 source address of an address-suffixed copy, kept in the title through the port. All values raw big-endian, units unproven unless stated.

Coverage: 324 tables in the E84 XDF across this group's six categories (98 + 91 + 73 + 0 + 1 + 61), accounting for 326 of the E70 group's items ported per the report; the 694 E70 entries that did not port are named above or fall inside the Ghidra-new remainder.
