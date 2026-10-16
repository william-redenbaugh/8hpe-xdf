# Shift execution (ramps, timing, phase control)

This group covers the parameters that control the *execution* of a shift once the shift schedule has decided to make one. An 8HP shift is a clutch-to-clutch handover: the TCU fills the oncoming clutch, hands torque over from the offgoing element (torque phase), then pulls the input speed to the new gear's synchronous speed (inertia phase), coordinating clutch pressure with engine torque requests over CAN — torque *reduction* on upshifts, a throttle *blip* (torque increase) on downshifts. The tables here set the phase durations, the sync-detection thresholds that end each phase, the pressure offsets applied during the handover, and the size and shaping of the torque interventions.

Nearly everything in this group is organised the same way: one small map **per gear pair** (1>2 … 7>8 for upshifts; direct and skip downshifts such as 2>1, 4>2, 8>2, 7>1 for downshifts), repeated across several **variant blocks** named `k0…k3` and `c0…c2` in the labels. The RE evidence shows readers resolving these copies through banked block tables (e.g. `04d0d4+24`, `04c878 k=n`), i.e. the firmware selects one block at runtime — plausibly by drive program or shift situation — but *which* condition selects which block is **not pinned by the RE**. Many upshift families also come in `_ti` / `_noti` twins; a natural reading is "with / without (engine) torque intervention", but that is an interpretation of the label, not proven. Z values are raw bytes/words (units marked "not proven" in the evidence); many tables sit on the common conventions of 128 ≈ neutral factor and 0–100 ≈ percent, and several scale curves are stored flat at 255 in this calibration. A few families have a separate companion "`axis`" table holding per-block breakpoints ("column = block, row = point") — edit the axis table together with its data table.

Practical consequence for tuning: to change the feel of *one* shift you must find the right gear pair **and** the right variant block (or change all copies of that gear pair consistently). The downshift phase/blip tables are the best-evidenced (mostly HIGH confidence, with the live reader function identified); the upshift torque/pressure families are MED confidence with unproven units, so make small relative changes and verify on the car.

### Shift execution: upshift

107 items, 12 families, calibration region ≈ 0x1A5700–0x1ADE00. All but the four companion axis tables are `cal_map_u8` / `cal_map_s16` / `cal_curve_u8` structures found by the structural scan and matched against the labelled reference 'F' build — about half byte-identical, the rest via value-matches or run-context alignment.

| Family | Members | Address range | Shape / type | Z range (raw) | What it does | Confidence |
|---|---|---|---|---|---|---|
| **shiftexec_up_trq_reduction** `_k0..k3_<n>to<n+1>` | 21 | 0x1A9008–0x1A9BD8 | 6x10 u8 | 76..140 | Engine torque reduction request during the upshift torque/inertia phase, per gear pair and variant block. Values straddle 128 (≈ neutral factor). Lowering values here changes how much torque is pulled during the shift — firmer/faster but harsher handover. | MED |
| **shiftexec_up_press_ofs_noti** `_k0..k2_<pair>` (incl. 3 extra address-suffixed copies `_1ac75c`/`_1acb80`/`_1acc54`) | 18 | 0x1A573C–0x1A7624 | 8x4 s16 | −10..10 | Clutch pressure offset applied during the upshift ("no torque intervention" path, per the label), per gear pair. Small signed corrections on top of the base shift pressure — the fine-trim for engagement firmness. | MED |
| **shiftexec_up_trq_rampout_noti** `_k0..k2_<pair>` (incl. 1 copy `_1ac488`) | 15 | 0x1A5B90–0x1A6AD8 | 6x4 s16 | 0..100 (%) | Ramp-out of the torque reduction at the end of the upshift: how quickly requested engine torque is restored. X breakpoints ≈ −16..22, Y 1000..6000 (consistent with engine/turbine speed in rpm, unit not proven). Slower ramp-out = softer shift exit. | MED |
| **shiftexec_up_press_ofs_ti** `_k2_<pair>` | 7 | 0x1A622C–0x1A66DC | 8x4 s16 | ≈ −12..2 | Same pressure-offset role as `press_ofs_noti` but for the `_ti` path; only the k2 block set is present for all 7 gear pairs. | MED |
| **shiftexec_up_press_pedal_ofs_noti** (4 multi-block runs + 1 axis table) | 5 | 0x1A6BD8–0x1A76C8 | 4-pt curves per block, u8 | 128 (flat) | Pedal-dependent pressure offset for upshifts, one 4-point curve per (k-block, gear-pair) copy; stored flat at 128 (= no offset) in this calibration except the last run (128..131). The companion `axis` table holds the per-block pedal breakpoints. | MED |
| **shiftexec_up_sync_time_thr_noti** (3 runs + 1 axis table) | 4 | 0x1A6C40–0x1A766E | 6-pt curves per block, u8 | 113..128 | Threshold/target for sync time on upshifts (`noti` path): used to judge when the inertia phase has synchronised. Per-block breakpoint axes in the companion `axis` table. | MED |
| **shiftexec_up_sync_time_thr_ti** (2 runs + axis + single `_k3_2to3`) | 4 | 0x1A5C36–0x1A6736 | 6-pt curves per block, u8 | 117..128 | Same sync-time threshold for the `_ti` path. | MED |
| **shiftexec_up_press_pedal_ofs_ti** (2 runs + 1 axis table) | 3 | 0x1A5B00–0x1A6078 | 4-pt curves per block, u8 | 128 (flat) | Pedal-dependent pressure offset, `_ti` path; flat at 128 as stored. | MED |
| **shiftexec_up_trqinc_coolant_scale** `_<pair>` | 24 | 0x1A9CDC–0x1ADD98 | 4x1 u8 curve | 255 (flat) | Coolant-temperature scaling of the upshift torque-increase path. 19 of the 24 copies are labelled 1>2, with single curves for 2>3, 4>5, 5>6, 6>7 and 7>8. X ≈ 20..128 °C-like breakpoints; stored flat at 255 (= full scale / no derate) in this calibration. | MED (8) / LOW (16) |
| **shiftexec_up_trqinc_fade_pct** (2 runs: 1>2..3>4, …) | 2 | 0x1A9C86–0x1A9FE6 | 6-pt curves per block, u8 | 0..100 (%) | Fade-out percentage for the torque-increase component on upshifts. | MED |
| **shiftexec_up_trqinc_sync_thr** (run 4>5/6>7 + single 7>8) | 2 | 0x1A9F1E–0x1AA1A6 | 6-pt curves, u8 | ≈ 138 | Sync threshold used by the upshift torque-increase logic. | MED |
| **shiftexec_up_trq_gate** `_k1_6to7/7to8` | 2 | 0x1A9548–0x1A95D4 | 4x4 s16 | −200..200 | Signed torque gate/correction for the top-gear upshifts in block k1; X breakpoints 199..250, Y 2199..3500 (rpm-like, unit not proven). | MED |

### Shift execution: downshift

91 items, 6 families, ≈ 0x1AA250–0x1AD680. This is the best-evidenced part of the whole group: for most members the RE identified the exact live reader function and the banked slot it reads (class-2 reader evidence), so the family meanings are HIGH confidence. Downshifts are tabulated per gear pair *including skip shifts* (e.g. 3>1, 4>2, 8>2, 8>4, 7>1), across variant blocks k0–k2 and c0–c2.

| Family | Members | Address range | Shape / type | Z range (raw) | What it does | Confidence |
|---|---|---|---|---|---|---|
| **shiftexec_dn_phase4_sync_time** `_k/c_<pair>` | 23 | 0x1AA2EC–0x1AD274 | 4x4 u8 | ≈ 106..123 | Sync time parameter for downshift phase 4 (the final synchronisation of the inertia phase). Reader FUN_000c7f0a reads the banked slot (+0x20) directly. Governs how long the controller allows/budgets for reaching the new synchronous speed. | HIGH (22) / LOW (1 c-variant) |
| **shiftexec_dn_blip_trq** `_k1/k2/c0_<pair>` | 21 | 0x1AA280–0x1AC848 | 6x10 u8 | 128..186 | Throttle-blip torque request during downshifts: how much extra engine torque is requested to spin the input up to the lower gear's speed. Values above 128 (≈ neutral), i.e. a positive torque add. Larger values = stronger rev-match blip, faster downshift. Reader FUN_000c8f92 (slot +0x18). | HIGH (20) / LOW (1) |
| **shiftexec_dn_blip_scale** `_k0..k2/c0..c2_<pair>` | 19 | 0x1AA314–0x1AD50C | 4x4 s16 | 0..100 (%) | Scaling (0–100%) applied to the blip torque, indexed by X 0..15 (up to 0..40 in some copies) and Y 20..200. Effectively the enable/strength schedule for the rev-match blip per operating point. Reader FUN_000c91f8 (slot +0x24). | HIGH (18) / LOW (1) |
| **shiftexec_dn_phase3_time** `_k0..k2_<pair>` | 18 | 0x1AA8E4–0x1AD5FC | 4x4 u8 | 1..30 | Duration parameter for downshift phase 3 (raw time units, ticks not proven). Longer = more drawn-out overlap/handover before synchronisation; shorter = snappier but harsher downshift. Reader FUN_000c8c9c (slot +0x1c). | HIGH |
| **shiftexec_dn_phase3_blend_pct** `_k0/k1/c0_<pair>` | 9 | 0x1AA258–0x1ABF98 | 4x4 u8 | 0..100 (%) | Blend percentage within downshift phase 3 — how the controller mixes/ramps between phase targets (pressure/torque handover shaping) during the overlap. Reader FUN_000c92d8 (slot +0x14). | HIGH (8) / LOW (1) |
| **shiftexec_dn_blip_coolant_scale** `_2to1` | 1 | 0x1AD678 | 4x1 u8 curve | 255 (flat) | Coolant-temperature scaling of the downshift blip for 2>1; flat at 255 as stored. | MED |

### Shift execution: other

79 items, 14 families. Two large per-gear-pair threshold families plus the gear-*engagement* (garage shift / element engagement) set and a handful of standalone curves.

**shift_elem_dn_sync_thr** — 27 members, 0x1AFE30–0x1B08B0, 4x4 u8 maps (z ≈ 225..248), variants `c0..c2` per downshift gear pair (2>1 … 8>7 incl. skip shifts). Per-element synchronisation *entry* threshold for downshifts: the speed-ratio criterion the shift-element logic uses to recognise that synchronisation has begun. Read by FUN_000ee186. Confidence **MED** (byte-identical object matches, meaning from the F-build label).

**shift_elem_dn_sync_end_thr** — 26 members, 0x1AFE50–0x1B08D0, 4x4 u8 maps (z ≈ 238..253), same `c0..c2`/gear-pair scheme. The matching synchronisation *end* threshold — when the element is considered fully synchronised and the shift can be completed. Read by FUN_000ee0ca. Confidence **HIGH** (25 of 26; 1 MED). Together with `shift_elem_dn_sync_thr` these bracket the inertia-phase end detection; raising the window tolerates more slip before closing the shift.

**Engagement set (`shiftexec_engage_*`)** — 20 members in 6 families, 0x1A86D0–0x1A8E3C, in `set0/set1/set2/set3/set8` variants rather than gear pairs. These shape the controlled engagement of a shift element (e.g. drive-off / garage engagement rather than a flying gear change):

| Family | Members | Shape / type | Z range | What it does | Confidence |
|---|---|---|---|---|---|
| shiftexec_engage_trq_enable_set2/3/8 (+2) | 5 | 4x4 u8 | 0..255 | Enable/threshold map for torque handling during engagement | LOW/MED |
| shiftexec_engage_trq_rampout_pct_set# | 4 | 4x4 s16 | 0..100 % | Ramp-out of the engagement torque reduction; Y 1000..6000 (rpm-like). Cross-version evidence shows this is actively calibrated (3 variants across 21 versions). | MED |
| shiftexec_engage_trq_red_set# | 4 | 6x6 u8 | 15..128 | Torque reduction during engagement (≤128 ≈ reduce) | MED |
| shiftexec_engage_sync_time_thr (set1/set2 run + 1 axis) | 3 | 6-pt curves u8 | 108..118 | Sync-time threshold for engagement completion | MED |
| shiftexec_engage_press_ofs (set1/set2 run + set8) | 2 | 8-pt curves s16 | −100 / 0 | Pressure offset during engagement (set1/2 stored at −100, set8 at 0) | MED |
| shiftexec_engage_trq_red_elem_set1/2 | 2 | 6x6 u8 | 128 (flat) | Per-element engagement torque reduction; flat (no reduction) as stored | MED |

**Standalone tables** (one member each):

| Parameter | Address | Shape / type | What it does | Confidence |
|---|---|---|---|---|
| shiftexec_ratio_torque_map | 0x1A7BA8 | 6x6 s16 | Ratio/torque map used by the shift-execution reader FUN_000c8578 (x 400..900, y 50..400, z 400..1000); actively calibrated across versions. Exact role not pinned. | MED |
| shift_skip_rule_table | 0x1CD984 | u8[25][14] | Rule table for multi-gear (skip) shifts: per the RE, "0011811a matches the 14-byte shift vector against each row; row 25 (max) at 1cd976", z: 1 = required. Decides which skip-shift sequences are permitted. | HIGH |
| shift_phase_time_curve | 0x1AE912 | 3-pt s16 curve | Phase-time curve (x 0..1000, z 150..300), read by FUN_000edefe. | LOW |
| engtime_map_a | 0x1999A0 | 2x4 s16 | Engagement-time map (x 10..60, y 0..140, z 0..400), read by FUN_000c0d30. | LOW |
| shiftinh_low_engspd_curve | 0x1C7760 | 4-pt s16 curve | Shift inhibit at low engine speed: x 700..1500 (rpm-like), z 0/1 flag — blocks shifts below a minimum engine speed. | LOW |
| shiftsync_temp_curve | 0x199A18 | 6-pt s16 curve | Oil-temperature curve feeding the shift-synchronisation filters (x oil_temp 60..150; stored z = 0), via E→F label transfer. | LOW |

### Shift execution: timing control

**shift_time_cap_by_gear** — 1 member, 0x1D344F, u8[25] array (one entry per gear/row 0..24). Per the RE: "0011811a caps the time at 0x18" — a per-gear upper cap (0..0x18, raw units) on the shift time value `fff8ddf9`, read by FUN_00117662. Acts as a global sanity limit on how long a shift may take per gear. Confidence **MED**.

### Unlabelled: Shift execution

**auto_shiftexec_dn_blip_outgrad_scale_1ad67c** — 1 member, 0x1AD68C, 6-pt s16 curve (x −800..1000, z 0..100), auto-detected by the structural scan; meaning not analysed, but it is read by the function labelled `shiftexec_dn_blip_outgrad_scale`, i.e. an output-gradient scaling of the downshift blip. Confidence **LOW**.

---

**Naming/legend for this group:** `<n>to<m>` = gear pair; `k0..k3` and `c0..c2` = runtime-selected variant blocks (selection condition not pinned); `set#` = engagement variant sets; `_ti`/`_noti` = twin parameter paths (plausibly with/without engine torque intervention — label interpretation, not proven); "` axis`" tables hold the per-block breakpoints for their matching multi-block data table. All values are raw (big-endian) with physical units unproven unless stated; 128 ≈ neutral factor and 0..100 ≈ percent are conventions visible in the data, not confirmed scalings.

Coverage: Covers all 279 items in this group (34 families).
