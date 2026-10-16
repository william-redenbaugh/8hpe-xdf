# Standstill functions & gear-ratio monitoring — E84

E84 X1, gearbox GKE233, cal ZB 8609556, SW `Z5YD7900_8HPXY_K790D`, 8HP45. XDF: `8hpe84_cali_v1.xdf`. Source chapter: `docs/e70/parameters/08-standstill-ratio-monitoring.md` — read that for the mechanism write-ups (neutral-idle state machine, ratio plausibility monitoring); this chapter records what exists in the **E84** XDF, at E84 addresses, and what does not.

**Inherited-code caveat.** The E84 read is calibration-only (no program code below 0x180200), so every reader attribution (FUN_000bad54, FUN_000cc92c, the index-resolved band readers, `standstill_range_change`) inherits from the E70 RE. All addresses below are the start of the item's embedded data (first axis vector; value address for scalars) as mapped in `8hpe84_cali_v1.xdf`; per-region deltas differ (+0xc18 for the nidle block, +0x5dc for standstill, +0xc1b8 for ratio monitoring, …), so never reuse an E70 address. Some XDF descriptions in the ratio-monitoring family still print the stale E70 `@` address — the embedded-data pointers are authoritative.

**Port column:** *exact* = byte-identical to the E70 calibration; *interval* = length-preserved interval mapping — **E84-native values that differ from the E70**. The interval items cluster exactly where you would expect a different engine/converter to need different data: the neutral-idle slip controller.

Port coverage for this chapter's E70 categories (from `docs/e84/data/e84_port_report.json`):

| Category | E70 items | Ported | Not portable |
|---|---|---|---|
| Standstill: neutral idle | 32 | 30 | 2 |
| Standstill: other | 7 | 7 | 0 |
| Gear ratio monitoring | 35 | 35 | 0 |
| Ghidra new: standstill / engine | 11 | 6 | 5 |
| Ghidra new: ratio monitoring | 268 | 5 | 263 |

### Standstill: neutral idle

30 of 32 E70 items. Missing, both not in the E84 XDF (needs full flash read):

- **`nidle_temp_curve`** — the temperature-dependent enable/limit (the one reader-corroborated enable curve).
- **`nidle_time_temp_d8`** — the time-vs-temperature duration curve.

Ironically those two were the *entry gates*: on the E84 you can still shape the open/slip/refill behaviour, but not the temperature/time conditions that enable the feature.

| Family | E84 addr(s) | Port | What it does (per E70 RE) | Confidence |
|---|---|---|---|---|
| `neutralctl_time_curve` | 0x1B2E04 | exact | Time curve of the neutral-control function, own reader, sits apart from the block. | LOW |
| `nidle_curve_e4` / `_f8` | 0x19B8A8 / 0x19B8D0 | exact | Pair of small condition curves (x 0..100), reader FUN_000bad54; meaning unresolved. | LOW |
| `nidle_fill_curves` (4) | 0x19DC4C, 0x19DC78, 0x19DCA4, 0x19DD98 | exact | f32 refill-phase scheduling for re-engaging the decoupled clutch. | MED |
| `nidle_open_curves` (2) | 0x19B9D0, 0x19BA04 | exact | f32 controlled-opening curves on entry. | MED |
| `nidle_open_maps` (3) | 0x1A2584, 0x1A2684, 0x1A26B0 | exact | Further open-phase scheduling (speed-, temperature-, torque-like inputs). | MED |
| `nidle_open_torque_curves` (2) | 0x19C650, 0x19C674 | exact | Torque-dependent terms during the open phase. | MED |
| `nidle_press_ramp_map` | 0x19B8E8 | exact | f32 6×6 pressure ramp map; no reader bound (F object match only). | MED |
| `nidle_slip_gain_a/b/c_map` | 0x19BBBC, 0x19BC84, 0x19BD4C | a/b interval, c exact | Slip-controller gain terms (b flat 5 stock). **a and b hold E84-native data.** | LOW |
| `nidle_slip_gain_map` | 0x1A25C0 | exact | Additional gain map, flat 0.5 stock. | MED |
| `nidle_slip_press_a/b_map` | 0x19C134, 0x19C3C4 | interval | Slip→pressure maps. **E84-native data.** | LOW |
| `nidle_slip_time_gain_map` / `_temp_map` | 0x19C06C / 0x19BFA4 | interval | Time terms of the slip phase. **E84-native data.** | LOW |
| `nidle_state1_curves` (2) | 0x1A20C4, 0x1A20D8 | exact | State-1 curves (signed delta / rpm inputs). | MED |
| `nidle_state1_trend_curves` (2) | 0x1A2408, 0x1A243C | exact | Trend/derivative terms in state 1. | MED |
| `nidle_target_curves` (2) | 0x1A2560, 0x1A2598 | exact | Setpoint (slip or pressure) held during neutral idle. | MED |
| `nidle_torque_limit_map` | 0x19BB4C | interval | Torque limit during neutral idle (E70 stock flat 1500; **E84-native data**). | LOW |

**Tuning note (unchanged from the E70, more so here):** leave this family stock unless you have a specific standstill-shudder or harsh re-engagement problem. The slip-controller maps interact as a closed loop, half of them carry E84-specific data (the interval items), and the enable gates are not even visible in this read. Log actual slip before touching anything.

### Standstill: other

All 7 E70 items ported. Supporting conditions for standstill / standstill range change (garage shifts).

| Parameter | E84 addr | Port | What it does | Confidence |
|---|---|---|---|---|
| `standstill_coolant_curve` | 0x19A004 | exact | Coolant-temperature factor (degC+48 axis), E-build reader `standstill_range_change`. | LOW |
| `standstill_gear_map_0_f0` | 0x19A208 | exact | Per-gear standstill map, slot 0, role f0 (x rpm-like 1500..6000, y negative-only). | LOW |
| `standstill_gear_map_0_f4` | 0x19A240 | exact | Slot 0, role f4 (x 600..2500, y ±6000, z 80..1000). | MED |
| `standstill_gear_map_1_f4` | 0x19A2B0 | exact | Slot 1, role f4. (On the E70 this one varied across versions; here it matched byte-identical.) | MED |
| `standstill_gear_map_8_f0` | 0x19A470 | exact | Slot 8, role f0. | MED |
| `standstill_time_curve` | 0x19A194 | interval | Duration-based scheduling (x 0..500, z 64..255). **E84-native data.** | LOW |
| `standstill_turb_curve` | 0x19A1AC | exact | Turbine-speed-dependent curve (x 2800..3450). | LOW |

The E70 chapter noted only four gear slots were defined as XDF items. The Ghidra/unlabelled import filled in more of the indexed table, and these also relocated in the E84 (all LOW, titles as in the XDF): `standstill_gear_map_0_f10` 0x19A278 exact, `_1_f8` 0x19A320 exact, `_1_fc` 0x19A390 exact, `_1_f10` 0x19A3C8 exact, `_5_f0` 0x19A5A8 interval, `_7_f0` 0x19A608 exact.

**Ghidra-new standstill records (6 of 11 ported)** — labelled from the E70 decompile (ctrl_b_d family, all Ghidra LOW):

| Parameter | E84 addr | Port | Ghidra note |
|---|---|---|---|
| `standstill_map_34` | 0x19A090 | exact | 4×4 map, x 20..50, y 150..550, z 100..470. |
| `standstill_outspd_curve` | 0x19A0C4 | exact | Output-speed curve (250..350 rpm → 60..20). |
| `standstill_time_curve_0x199b38` | 0x19A0D4 | exact | Timer 0..500 → factor 255..64 (second copy of the time curve family). |
| `standstill_turb_curve_0x199b50` | 0x19A0EC | exact | Second turbine-speed curve. |
| `standstill_pedal_curve` | 0x19A118 | interval | Pedal 0..200 → u8 50 flat. **E84-native data.** |
| `standstill_gear_map_0_f0_0x199b88` | 0x19A128 | exact | Second copy of the slot-0/f0 gear map. |

Not in the E84 XDF (needs full flash read): the 5 dropped records of this category are the **engine overspeed items** — `engine_speed_limit_margin_curve` and `engine_rpm_limit_stage0/1/2/mode`. This is the same hole the patches chapter hits: the "True manual" patch was not ported because its overspeed limits were unresolvable. Per the E70 RE the stock TCU guard sits at ~7100 rpm, so holding gears to 7000 rpm does not need them.

### Gear ratio monitoring

All 35 E70 items ported, **every one byte-identical (exact)** — the E84 runs the same ratio-plausibility calibration as the E70 in this region (same gearset, same ratios). The band/offset z-values remain raw s16 (32767 = "no limit"), engineering unit unproven, and the per-set index meaning (plausibly gear position) is still unproven because that resolution lived in program code.

**Same warning as the E70: do not widen these bands to "fix" a ratio DTC** — the DTC means a clutch is slipping. These are diagnostic thresholds, not performance maps, and nothing in this group is rated above MED.

| Family | E84 addr | Port | Organization | Confidence |
|---|---|---|---|---|
| `ratio_mon_upper_band_map_set0..set8` | 0x1D3984 + n·0x108 (set0 0x1D3984, set1 0x1D3A8C, set2 0x1D3B94, set3 0x1D3C9C, set4 0x1D3DA4, set5 0x1D3EAC, set6 0x1D3FB4, set7 0x1D40BC, set8 0x1D41C4) | exact | 8×2 s16 maps; x 8 speed points (upper limit growing per set up to 8000), y 0..5000, z up to 32767. | MED (set1..8), LOW (set0) |
| `ratio_mon_lower_band_map_set0..set8` | 0x1D39C0 + n·0x108 (set0 0x1D39C0 … set8 0x1D4200), interleaved with the upper maps | exact | Mirror of the upper maps, y −5000..0. | MED (set1..8), LOW (set0) |
| `ratio_mon_band_a/b/d/c_curve` (+ axis tables) | a 0x1D3E28 (axis 0x1D3E18), b 0x1D3E4C (axis 0x1D3E3C), d 0x1D3E70 (axis 0x1D3E60), c 0x1D3E94 (axis 0x1D3E84) | exact | 5-block (set4..set8) 8-pt s16 curves refining the window for the upper sets; they sit inside the band-map run between the set4 and set5 blocks. | MED |
| `ratio_mon_offset_a_curve` blocks (+ axis tables) | downshifts (5>4..8>7) 0x1D43B0 (axis 0x1D43A0); upshifts + skip (4>5..1>3) 0x1D45A8 (axis 0x1D4598); multi-gear (3>6..6>8) 0x1D47E8 (axis 0x1D47D8) | exact | Per-shift transient ratio tolerance, one 8-pt block per shift pair (readers index-resolved, bound 0x18 = 24 shift slots). | MED |
| `ratio_mon_offset_b_curve` (+ axis) | 0x1D4344 (axis 0x1D4334) | exact | Second per-shift offset term, all 24 shift pairs in one blocked table. | MED |
| `ratio_slip_map` | 0x1D84E0 | exact | 3×3 u16 model map of allowed/expected slip, separate reader (FUN_0011b708). | LOW |

**Ghidra-new ratio-monitoring records (5 of 268 ported).** The Ghidra pass had added 268 records here — per-set/per-shift relabels of the band and offset slots plus a second complete band/offset block at code-adjacent E70 addresses (0x1d6ed4…), and `ratio_mon_step_curve`. That material is almost entirely not in the E84 XDF (needs full flash read); 263 of 268 dropped. The 5 that relocated (no Ghidra comments, treat as LOW):

| Parameter | E84 addr | Kind | Port |
|---|---|---|---|
| `ratio_mon_offset_a_curve_4to8` | 0x1D4940 | 5-pt s16 curve (z 50..4000) | exact |
| `ratio_mon_offset_a_curve_6to8` | 0x1D4984 | scalar (32 bit) | exact |
| `ratio_mon_offset_b_curve_1to7` | 0x1D4888 | scalar (32 bit) | exact |
| `ratio_mon_offset_b_curve_6to8` | 0x1D49A8 | scalar (32 bit) | exact |
| `ratio_mon_band_b_curve_set7` | 0x1D4150 | scalar (32 bit) | exact |

For editing purposes little is lost: the 35 ported family tables above are the stored data the monitoring actually runs on; the dropped records were finer-grained labels and the second block, which cannot be anchored without program code.

### What remains usable on the E84

- **Neutral idle**: the whole controller except its two enable curves. Still best left stock; the interval-tagged slip maps are genuine E84 data, not E70 copies.
- **Standstill / garage shift**: complete, plus six extra gear-map slots and six Ghidra records the E70 chapter never had.
- **Ratio monitoring**: complete and byte-identical. The only legitimate edit remains a hardware change that genuinely alters the plausible ratio window — and the per-set indexing is still unproven, now with no prospect of proving it from this read.
- **Engine rpm-limit records**: gone. Overspeed-guard edits are off the table until a full flash read exists.

Coverage: 72 of the E70 chapter's 74 items are in the E84 XDF (2 not portable), plus 6 of 11 Ghidra-new standstill/engine records and 5 of 268 Ghidra-new ratio-monitoring records.
