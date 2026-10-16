# Torque converter (lock-up clutch control) — E84

E84 X1 (gearbox GKE233, cal ZB 8609556, SW Z5YD7900_8HPXY_K790D, 8HP45). XDF: `8hpe84_cali_v1.xdf`. The control architecture — converter model → slip target → slip PID → pressure setpoint, with a separate open/close scheduling layer — is described in `docs/e70/parameters/06-torque-converter.md` and analysed in depth in `docs/e70/analysis/tcc-lockup.md`; none of that text is repeated here. This chapter is the E84 address map: **every TCC-related item in the E84 XDF, and everything that did not survive the port.**

Provenance: all TCC items were **ported from the E70 XDF by content match** (exact byte match, record-stream walk, or length-preserved interval mapping); each XDF description carries the method and delta (the main tcc cluster moved +0x41A8..+0x42C0, the tccctrl cluster +0x1798..+0x4128). The E84 read is calibration-only (no program code), so every reader binding, slot offset (tcc+0x128 etc.) and unit proof is an **E70 code fact inherited by content identity** — valid to the extent the E84's 2012-generation build keeps the same readers, which the byte-identical calibration structures support but do not prove. Confidence levels are carried over verbatim. Axis/z ranges below are the E70 RE-note ranges carried with the port; `exact` items are byte-identical to the E70 image, `walk`/`interval` items matched structure and length — verify values with `xdf_show` before trusting a specific number.

Addresses are XDF z-data addresses (start of z bytes, after inline axes), as `tools/xdf_ls.py` prints them — same convention as the E70 chapters. In Ghidra-sourced description text the `@0x…` is still the E70 source address; trust the XDF table address.

Verified coverage (counted in the XDF, not estimated): **91 `tcc_*` / `tc_*` / `tcmodel_*` entries survived the port** (90 distinct titles — `tcc_press_error_map_set0` exists twice), plus 9 `thermode_gear_tcc_curve_set*` converter-temperature torque limits and 3 `elem_msa_*tcc*` element curves = 103 TCC-related entries. **60 distinct E70 TCC-related titles are not in the E84 XDF** (full list at the end). Checksums: the E70 checksum algorithm does **not** reproduce on this read (`xdf_checksum` search fails) — flash via xHP, which corrects checksums itself.

### Torque converter: slip

12 of 13 ported; dropped: `tccslip_block` (a code-anchored block anchor, not a tunable — needs full flash read).

| Parameter | E84 address | Shape | Axes → z (E70 RE notes) | Confidence / role |
|---|---|---|---|---|
| tcc_slip_target_map | 0x1A5724 | 6x6 s16 | x slip -1000..1200; y torque 800..5000 → z 13..21 | HIGH. Main slip-torque setpoint term (tcc+0x128, reader 0xDD238). E70: 0x1A151C. |
| tcc_slip_cond_map | 0x1A58A4 | 6x6 s16 | x 40..120; y 60..150 → z 0..7 | HIGH. Conditioning term summed into the same setpoint (tcc+0x140). E70: 0x1A169C. |
| tcc_slip_target_curve | 0x1A514C | 6x1 f32 | x slip -50..450 → z 0.5..2.5 | HIGH. Slip-target-in-rpm path (tcc+0xF4, readers 0xDBA7C/0xDBE6E). E70: 0x1A0FA4. |
| tcc_slip_gain_b | 0x1A5090 | 6x1 f32 | x -100..400 → z 2.0..4.0 | HIGH. Slip-target ramp rate, ×0.01 per step (tcc+0xE4). E70: 0x1A0EE8. |
| tcc_slip_pid_gain_a | 0x1A4F18 | 4x1 f32 | x oil temp 0..60 → z 0.8..1.0 | MED. Oil-temp PID gain (reader 0xDB5AA). E70: 0x1A0D70. |
| tcc_slip_pid_gain_e4 | 0x1A49C4 | 6x6 f32 | x -100..150; y -60..60 → z 0.1..20 | LOW, no bound reader. E70: 0x1A081C. |
| tcc_slip_pid_gain_ec | 0x1A4B54 | 6x6 f32 | x -100..50; y -240..150 → z 0.1..15 | LOW, no bound reader. E70: 0x1A09AC. |
| tcc_slip_torque_factor_19c | 0x1A552C | 6x6 f32 | x -900..800; y -100..400 → z 0..0.6 | LOW. E70: 0x1A1324. |
| tcc_slip_torque_factor_1a0 | 0x1A5604 | 8x8 f32 | x -1200..1200; y -150..400 → z 0..1.7 | LOW. E70: 0x1A13FC. |
| tcc_slip_2d_offset | 0x1A5DC0 | 6x6 f32 | zero in this family | MED. E70: 0x1A1B18. |
| tcc_slip_turb_torque_map2_set1 | 0x1A40F8 | 6x6 s16 | x 1000..2300; y -500..3000 → z flat 20 | MED, slot not attributable. E70: 0x19FFD0. |
| tccslip_curve_20c | 0x1A5B70 | 4x1 s16 | x 1000..4000 → z flat 40 | LOW. E70: 0x1A1900. |

The slip-PID sibling curves (E70 analysis §3.2, all read by FUN_000db5aa) also ported: `auto_cal_curve_f32_1a0d80` → **0x1A4F3C**, `…_1a0da4` → **0x1A4F60**, `…_1a0dc8` → **0x1A4F84**, `…_1a0ea4` → **0x1A5060** (all 4x1 f32, LOW). The curve at tcc+0x12C (`auto_cal_curve_s16_1a1564`, second term of the setpoint sum) is **not in the E84 XDF (needs full flash read)** — on the E84 the setpoint sum is editable only through `tcc_slip_target_map` and `tcc_slip_cond_map`.

### Torque converter: pressure / control

15 of 18 ported; dropped: `tcc_press_offset_curve` (the one shared with neutral-idle open), `tccctrl_curve_124`, `tccctrl_block` — all **not in the E84 XDF (needs full flash read)**.

| Parameter | E84 address | Shape | Axes → z (E70 RE notes) | Confidence / role |
|---|---|---|---|---|
| tcc_press_fill_map | 0x1A57D4 | 6x6 s16 | x rpm 1000..6000; y torque -250..300 → z 100..150 raw (0.01 bar/LSB) | HIGH. Fill pressure (tcc+0x138, reader 0xDCF6A). E70: 0x1A15CC. |
| tcc_press_hold_map | 0x1A583C | 6x6 s16 | same axes → z 40..100 | HIGH. Hold pressure (tcc+0x13C). E70: 0x1A1634. |
| tcc_phase_map | 0x1A5798 | 2x2 s16 | breakpoints 1000/3000 × 1000/4000 → bar setpoint u/100 | HIGH. Per-phase pressure (reader 0xDD156). E70: 0x1A1590. |
| tcc_ramp_curve | 0x1A57AC | 2x1 f32 | x percent-ratio 0..1 | HIGH. Ramp setpoint (reader tcc_phase_8f84). E70: 0x1A15A4. |
| tcc_press_rate_drive_curve (+ axis) | 0x1A3AB0 / 0x1A3AA8 | 4x2 s16 | x -4000..1500 → z 50..500, 2 copies (set0/set1) | LOW. Rate term (reader 0xDD49A). E70: 0x19F988/0x19F980. |
| tcc_press_turb_accel_curve (+ axis) | 0x1A3A9C / 0x1A3A94 | 4x2 s16 | x 0..7000 → z 0 stock | MED data / LOW structure. E70: 0x19F974/0x19F96C. |
| tcc_press_turb_torque_map_set0 | 0x1A3A70 | 4x4 s16 | zeroed stock | LOW. E70: 0x19F948. |
| tcc_press_turb_torque_map_set1 | 0x1A3B50 | 4x4 s16 | zeroed stock | LOW. E70: 0x19FA28. |
| tcc_gain_press_map3_set0 | 0x19E1F0 | 8x4 f32 | x 660..900; y 50..850 → z 0.8..1 | MED. Multiplicative pressure gain. E70: 0x19BFB0. |
| tcc_press_error_map_set0 | 0x19D3A8 | 6x6 f32 | zeroed stock | MED. E70: 0x19BC10. |
| tcc_press_error_map_set0 (copy) | 0x19DE50 | 6x6 f32 | zeroed stock | LOW. E70: 0x19C6B8. |
| tcc_press_time_temp_map_set2 | 0x19F150 | 8x8 f32 | x 0..3; y -10..110 → z 0..20 | LOW. E70: 0x19C920. |
| tccctrl_curve_a4 | 0x1A2F30 | 4x1 s16 | x "difference/2" -100..100 → z 0 | LOW (reader 0xC45A2). E70: 0x19F0B0. |

### Torque converter: lock-up / open / close

10 of 14 ported; dropped: `converter_lockup_curve`, `tccadp_block`, `tcc_aux_block`, `tcmodel_block` — all **not in the E84 XDF (needs full flash read)**. The four block anchors were code-anchored (RAM base pointers in the missing program ROM); their loss costs navigation aids, not tunables — but `converter_lockup_curve` and the `tcc_aux_block` "coast/gear limits" were the only per-gear gating evidence the E70 had, and the E84 XDF has **none**.

| Parameter | E84 address | Shape | Axes → z (E70 RE notes) | Confidence / role |
|---|---|---|---|---|
| tcmodel_K_curve | 0x199F64 | 12x1 s16 | x turbine rpm 0..15000 → z K -769..1775 | HIGH. Converter capacity factor — hardware data. E70: 0x1999CC. |
| tcmodel_mu_curve | 0x199F8C | 6x1 s16 | x speed-ratio idx 0..10200 → z mu ×10000 0.9708..1.8650 | HIGH. Torque multiplication — hardware data. E70: 0x1999F4. |
| tcc_close_press_map | 0x1A21F4 | 4x6 f32 | x 0..4.3; y 0.1..5 → z -0.9..5 | MED, no bound reader, axes unidentified. E70: 0x19E370. |
| tcc_close_time_map | 0x1A2314 | 4x6 f32 | x 0..4.3; y 0.2..1 → z 0..0.4 | MED, same class. E70: 0x19E490. |
| tcc_open_speed_slip_map | 0x1A345C | 4x4 s16 | x -1500..-200; y -1000..0 → z 100..700 | LOW (reader 0xDDDCA). Coast-open thresholds by interpretation. E70: 0x19F334. |
| tcc_open_speed_slip_map2 | 0x1A354C | 8x8 s16 | z flat -2000 | LOW. E70: 0x19F424. |
| tcc_open_temp_press_map_set0 | 0x19CB7C | 6x6 f32 | x -20..110 °C; y 0..160 → z 0..1.1 | MED. E70: 0x19C4F4. |
| tcc_open_temp_press_map_set2 | 0x19D66C | 6x6 f32 | same | LOW (second set). E70: 0x19CF9C. |
| tcc_coast_torque_map | 0x1A341C | 4x4 s16 | x turbine rpm; y neg. torque ×0.1 Nm → z -50..-30 | LOW (reader tcc_press_torque_calc). E70: 0x19F2F4. |
| tcc_conv_capacity_map | 0x1A28FC | 6x4 f32 | x 1000..6000 rpm; y 20..130 → z 88.8..95.3 | LOW, no bound reader. E70: 0x19EA0C. |

### Torque converter: other

11 of 17 ported; dropped: `tc_torque_ratio_curve`, `tcc_setpoint_tab2`, and the entire engine-overspeed torque-limit family `tctrq_overspeed_curve_10/_20`, `tctrq_overspeed_torque_24/_34` — all **not in the E84 XDF (needs full flash read)**. Note for the sport-redline work: the tctrq curves (which taper converter-side torque to zero at high rpm on the E70) cannot be inspected or edited on the E84; the stock TCU guard is ~7100 rpm, so holding gears to 7000 rpm does not require touching them anyway.

| Parameter | E84 address | Shape | Axes → z (E70 RE notes) | Confidence / role |
|---|---|---|---|---|
| tcc_setpoint_curve_a | 0x1A5D30 | 2x1 s16 | x 0..5 → z 15759..23593 | HIGH. PT1-filtered setpoint target (reader 0xDAC8C). E70: 0x1A1A70. |
| tcc_setpoint_curve_b | 0x1A5D60 | 2x1 s16 | same | HIGH. Slot tcc+0x1F0. E70: 0x1A1AA0. |
| tcc_pedal_weight_curve | 0x1A5C44 | 4x1 u8 | x pedal 0..255 → z 0..100 % | HIGH. Percent weight blending pedal into the TCC torque term (reader 0xDA984). E70: 0x1A1984. |
| tcc_neg_slip_curve | 0x1A5C38 | 2x1 s16 | x -500..-150 → z -500..-300 (0.01 scale) | HIGH. Coast negative-slip target (reader tcc_neg_slip). E70: 0x1A1978. |
| tcc_output_torque_map | 0x1A39EC | 4x6 s16 | x 350..2500; y -50..400 → z 50..400 | MED (readers 0xDCA5C/0xDCAE0/0xDCB2C). E70: 0x19F8C4. |
| tcc_torque_capacity_drive_coast | 0x1A50D8 | 2x8 f32 | x -50..600; y drive/coast flag → z 200..400 | LOW. E70: 0x1A0F30. |
| tcc_curve_b69e | 0x1A35D8 | 4x1 s16 | x 180..250 → z 100..300 | LOW (reader tcc_press_torque_calc). E70: 0x19F4B0. |
| tcc_curve_u8_48 | 0x1A35E6 | 2x1 u8 | x 191..229 → z 20..100 | LOW (reader tcc_press_filter). E70: 0x19F4BE. |
| tcc_curve_u16_50 | 0x1A3608 | 4x1 s16 | x 0..191 → z 30..150 | MED. E70: 0x19F4E0. |
| tcc_eng_temp_factor | 0x1A5260 | 2x2 f32 | flat 1.0 | LOW, no reader. E70: 0x1A10B8. |
| tcctemp_heat_coeff_map | 0x1A2714 | 4x4 f32 | x 600..4000; y 30..110 → z 1.3..3 | LOW, no reader. TCC thermal-model coefficient by name. E70: 0x19E890. |

### Ghidra-new and unlabelled TCC items (43 entries)

The Ghidra decompile pass on the E70 (hp8_sh, 2026-10-15) named dozens more TCC structures; 43 of them survived the port. They live under "Ghidra new: torque converter" and the unlabelled categories. All LOW/MED per the Ghidra comments; readers are E70 code.

**Ghidra new: torque converter** (4):

| Parameter | E84 address | Shape | Ghidra note |
|---|---|---|---|
| tc_capacity_factor | 0x199E60 | 12x1 s16 | HIGH — x TC speed ratio ×10000 (0..15000), z pump torque factor K (1586..-769). A second copy of the K data next to the tcmodel pair. |
| tcc_gain_press_map3_set2 | 0x1A2BF0 | 8x4 f32 | LOW — x 660..900, y 50..850, z 0.8..1.0 (third set of the map3 gain family) |
| tcc_temp_gain_map_set2 | 0x1A2CB0 | 6x8 f32 | LOW — x 40..450, y oil temp °C, z 0.5..4.1 |
| tcc_torque_limit_time_map_set2 | 0x1A2E94 | 4x4 f32 | LOW — x phase counter s, y 0..600, z flat 1500 |

**tcc_slip_setpoint_map family** — per-set slip setpoint maps, Ghidra MED: x = filtered turbine speed, y = engine torque demand Nm, z = **slip rpm 0..50**. The most direct per-set "how much slip here" tables found so far; which set is active when is not attributed (log first). 12 of 16 sets ported; set6/set13/set18/set26 are **not in the E84 XDF**.

| Set | E84 address | Shape | Set | E84 address | Shape |
|---|---|---|---|---|---|
| set0 | 0x1AB6CC | 4x6 s16 | set29 | 0x1AC87C | 6x6 u8 |
| set2 | 0x1AB7FC | 4x8 s16 | set31 | 0x1AC994 | 6x6 u8 |
| set4 | 0x1AB926 | 6x1 u8 | set33 | 0x1ACAAC | 6x6 u8 |
| set11 | 0x1ABD6C | 4x6 s16 | set34 | 0x1ACB54 | 6x6 u8 |
| set21 | 0x1AC266 | 6x1 u8 | set36 | 0x1ACC6C | 6x6 u8 |
| set24 | 0x1AC53C | 4x1 u8 | set38 | 0x1ACD84 | 6x6 u8 |

**Other unlabelled TCC entries** (Ghidra comment summarized; "cal-scan" items additionally have an auto-detected structure note):

| Parameter | E84 address | Shape | Ghidra note |
|---|---|---|---|
| tc_torque_ratio_mu | 0x199E8C | 10x1 s16 | **HIGH** — x TC speed ratio ×10000 (0..10200), z torque ratio mu ×10000 (18650..9708). The surviving stand-in for the dropped `tc_torque_ratio_curve` (reader FUN_000b66d4 on the E70). |
| tcc_gain_press_map2_set1 | 0x1A2528 | 4x1 f32 | LOW — x 720..1400, y 5..35, z 1.0..1.5 (reader FUN_000d93a4) |
| tcc_gain_press_map2_set3 | 0x1A38B4 | 6x4 s16 | LOW — same family (reader FUN_000dc53a) |
| tcc_gain_press_map3_set3 | 0x1A36EC | 6x4 s16 | LOW — x 660..900, y 50..850, z 0.8..1.0 |
| tcc_gain_temp_map_a_set0 | 0x1A3E04 | 6x6 s16 | LOW — x oil temp °C, z 15..50 |
| tcc_gain_temp_map_b_set0 | 0x1A3D34 | 6x6 s16 | LOW — x oil temp °C, z 0..5 |
| tcc_gain_temp_map_b_set7 | 0x1A5D12 | 7x1 s16 | LOW — x oil temp °C, z 0..5 |
| tcc_gain_temp_map_c_set1 | 0x1A457C | 2x1 s16 | LOW — x oil temp °C, z 300..600 (reader FUN_000db398) |
| tcc_ramp_time_map_set1 | 0x1A448C | 2x1 s16 | LOW — x timer s (×0.01), z 0..10 (reader FUN_000db398) |
| tcc_ramp_time_map_set2 | 0x1A48FC | 6x6 f32 | LOW — same family |
| tcc_ramp_time_map_set4 | 0x1A3FC0 | 6x6 s16 | LOW — same family |
| tcc_ramp_time_map_set7 | 0x1A5B0C | 4x4 f32 | LOW — same family |
| tcc_close_rate_map_set4 | 0x1A3ED4 | 6x6 s16 | LOW — x 0..100, y 550..1100, z 0.04..0.095 |
| tcc_press_step_tab_set0 | 0x1A7980 | 12x1 s16 | MED — initial target step (u8, negated in coast) when the torque request reverses sign |
| tcc_press_rate_tab_set1 | 0x1A7A92 | 12x5 s16 | MED — rate limit while obj state (+0xC) is set |
| tcc_press_turb_accel_curve_set0 | 0x1A794C | 12x1 s16 | MED — x turbine-accel excess, z tcc_press target in TCC state 6, drive (12-pt curve; distinct object from the 4-pt 2-copy block at 0x1A3A9C) |
| tcc_press_turb_accel_curve_set1 | 0x1A7A1C | 12x1 s16 | MED — same role, set1 |
| tcc_press_rate_coast_curve_set1 | 0x1A7A50 | 12x1 s16 | MED — rate limit of the target ramp, coast with sign change |
| tcc_dyn_trq_gain_shift_set2 | 0x1A72B8 | 6x4 f32 | MED — gain on the drive/coast torque term while a shift is in progress |
| tcc_lockup_temp_factor | 0x1A77B0 | 4x4 f32 | LOW — x oil temp raw °C+40, z 100 % |
| tcc_temp_factor_b12c_set2 | 0x1A29A4 | 8x8 f32 | LOW — x 5..35, y oil temp °C, z 0.9..1.0 |
| tcc_slip_pid_gain_e8 | 0x1A8DC0 | 4x4 s16 | LOW — x slip error rpm, y slip gradient, z 0.1..8 (fills the e4/e8/ec PID-map triple) |
| tcc_slip_torque_factor_158 | 0x1A991C | 8x1 s16 | LOW — x TCC slip rpm, y torque Nm, z factor 0..1.7 |
| tcc_slip_torque_factor_164 | 0x1A9D24 | 6x8 s16 | LOW — same family |
| tcc_low_turbine_corr | 0x1AB100 | 4x6 s16 | LOW — x turbine speed filt, y engine torque Nm, z -10..-1 |
| tcc_drive_slip_off_map_a_set1 | 0x1ACF44 | 6x6 u8 | LOW — x turbine speed filt, y blended torque Nm pos, z 0..40 (set0 and the _b maps did not port) |
| tccadp_curve_54 | 0x1A66E8 | 6x4 f32 | LOW — the one surviving tccadp item (the `tccadp_block` anchor and its three E70 curves did not port) |

**thermode_gear_tcc_curve_set0..set8** — 9 items, 4x1 u16 each, contiguous at **0x199CB4, 0x199CDC, 0x199D04, 0x199D2C, 0x199D54, 0x199D7C, 0x199DA4, 0x199DCC, 0x199DF4** (0x28 stride). LOW. Ghidra: x = TCC temperature-model output (tcc_if_b69c), z = **torque limit in Nm falling 450 → 150 as the modelled TCC temperature rises**. This is the TCC thermal protection's visible actuator — together with `tcctemp_heat_coeff_map` it is why sustained high-slip operation loses torque. Relevant to the N52K project only as a reason to keep slip low; do not raise limits.

**elem_msa_torque_tcc_curve_m9c_set2** (0x1BC808), **…_ma0_set2** (0x1BC824), **elem_msa_torque_curve_tcc_m24_set2** (0x1BC04C, const) — MSA (auto start-stop) element curves keyed on a TCC-interface torque signal; documented in the shift-elements chapter.

### Relation to the E70 TCC analyses (N52K NA + N20 converter)

`docs/e70/analysis/tcc-lockup.md` and `docs/e70/analysis/n52k-tcc-optimization.md` were written against the E70 XDF (ZB 8646496). Their architecture reading, tuning order and test procedure carry over unchanged — the E84 is the same controller generation and the calibration structures matched byte-for-byte. What changes is the address map and a few missing levers. Status of every table those analyses reference:

| Analysis lever (opt. doc §) | E70 address | E84 status |
|---|---|---|
| §2.1 tcmodel_K_curve | 0x1999CC | **0x199F64** — exists, HIGH. Fix-first item for the N20 converter, unchanged. |
| §2.1 tcmodel_mu_curve | 0x1999F4 | **0x199F8C** — exists, HIGH. |
| §2.1 tcmodel_block (+0x08/+0x0C dyn params) | 0x181E18 | **not in the E84 XDF** (code-anchored; needs full flash read). The dyn params cannot be inspected on the E84. |
| §2.1 tc_torque_ratio_curve | 0x19A864 | **not in the E84 XDF**; the Ghidra-labelled `tc_torque_ratio_mu` at **0x199E8C** (HIGH comment, same mu ×10000 encoding) and `tc_capacity_factor` at **0x199E60** are the surviving second-copy model curves — mirror a mu change there only with on-car evidence, per the analysis. |
| §2.2 tcc_slip_target_map | 0x1A151C | **0x1A5724** — exists, HIGH. Main de-turbo lever, unchanged. |
| §2.2 tcc_slip_target_curve | 0x1A0FA4 | **0x1A514C** — exists, HIGH. |
| §2.2 curve at tcc+0x12C (auto_cal_curve_s16_1a1564) | 0x1A1574 | **not in the E84 XDF** — the "only touch if the summed setpoint misbehaves" escape hatch is gone. |
| §2.3 tcc_slip_gain_b | 0x1A0EE8 | **0x1A5090** — exists, HIGH. |
| §2.3 tcc_setpoint_curve_a / _b | 0x1A1A70 / 0x1A1AA0 | **0x1A5D30 / 0x1A5D60** — exist, HIGH. |
| §2.4 tcc_pedal_weight_curve | 0x1A1984 | **0x1A5C44** — exists, HIGH. |
| §2.5 tcc_slip_cond_map | 0x1A169C | **0x1A58A4** — exists, HIGH. |
| §2.6 tcc_neg_slip_curve | 0x1A1978 | **0x1A5C38** — exists, HIGH. |
| §2.7 tcc_press_fill_map / tcc_press_hold_map | 0x1A15CC / 0x1A1634 | **0x1A57D4 / 0x1A583C** — exist, HIGH. |
| §2.8 tcc_slip_pid_gain_a + 4 siblings | 0x1A0D70; 0x1A0D94 / 0x1A0DB8 / 0x1A0DDC / 0x1A0EB8 | **0x1A4F18**, siblings **0x1A4F3C / 0x1A4F60 / 0x1A4F84 / 0x1A5060** — all exist. |
| §2.8 tcc_slip_pid_gain_e4 / _ec | 0x1A081C / 0x1A09AC | **0x1A49C4 / 0x1A4B54** — exist, LOW; plus Ghidra `_e8` at **0x1A8DC0**. |
| §3 tccadp_block (adaptation reset caution) | 0x1824D4 | **not in the E84 XDF.** Irrelevant for the procedure: reset adaptation via the diagnostic routine, never by editing bytes — that advice stands. Only `tccadp_curve_54` (0x1A66E8) is visible. |
| §3 do-not-touch list: close press/time, open_speed_slip, conv_capacity, coast_torque, slip-torque factors, capacity_drive_coast, output_torque, heat_coeff, eng_temp_factor | various | All exist at the addresses in the tables above; the do-not-touch reasoning (LOW labels, unbound readers, unattributed sets) carries over verbatim. |
| §3 converter_lockup_curve, tcc_press_offset_curve, tcc_aux_block, tcc_setpoint_tab2, tctrq_* | various | **not in the E84 XDF** — were already "do not touch"; now they cannot be touched. |

Additional E84-specific notes for the deep dive (`tcc-lockup.md`):

- §1.1's five CAL block anchors are all absent (code-anchored). Slot-offset language (tcc+0x128 etc.) remains meaningful only through the inherited E70 readers.
- §5.1 "no lock-up shift lines exist": still true, and worse — the Ghidra pass later found a candidate lock-up scheduling cluster on the E70 (`tcc_lockup_strategy_curve_1de364`, `tcc_strategy_step_curve_1e1ffc`, and 11 `tcc_lockup_strategy_table_1e20xx` records in the strategy region), and **none of it ported**. On the E84 the "when does it lock" scheduling is entirely invisible — needs full flash read. Tune the setpoint path, not the schedule.
- The slip-setpoint path got richer on the E84 side of the port: the 12 `tcc_slip_setpoint_map_set*` tables (z = slip rpm 0..50, MED) are per-set slip targets the original E70 chapter never had. For the N52K slip-reduction program they are the natural complement to §2.2 — same caveat as every per-set family: the set selector is unattributed, so log which set moves before editing it.
- Converter-swap specifics: with the N20 converter, `tcmodel_K_curve` (0x199F64), `tcmodel_mu_curve` (0x199F8C), `tc_capacity_factor` (0x199E60) and `tc_torque_ratio_mu` (0x199E8C) are the complete set of converter-hardware curves visible in this XDF. The `tcmodel_block` dyn params are not visible; if slip control still hunts after correcting all four curves, the remaining mismatch may live there.

### Not in the E84 XDF (needs full flash read)

All 60 E70 TCC-related titles absent from `8hpe84_cali_v1.xdf`, grouped:

- **Block anchors (code-anchored):** `tcmodel_block`, `tccadp_block`, `tccctrl_block`, `tccslip_block`, `tcc_aux_block`.
- **Overspeed torque limits:** `tctrq_overspeed_curve_10`, `tctrq_overspeed_curve_20`, `tctrq_overspeed_torque_24`, `tctrq_overspeed_torque_34`.
- **E70-chapter items:** `converter_lockup_curve`, `tcc_press_offset_curve`, `tccctrl_curve_124`, `tcc_setpoint_tab2`, `tc_torque_ratio_curve` (both E70 copies).
- **Lock-up strategy cluster (Ghidra):** `tcc_lockup_strategy_curve_1de364`, `tcc_strategy_step_curve_1e1ffc`, `tcc_lockup_strategy_table_1e203a/_1e2050/_1e2066/_1e207c/_1e2092/_1e20a8/_1e20be/_1e20d4/_1e20ea/_1e2100/_1e2116`.
- **Ghidra coast/rate/target constants and filters:** `tcc_press_rate_drive_const_set0/set1`, `tcc_press_rate_coast_const_set0/set1`, `tcc_press_target_coast_conf_set0/set1`, `tcc_press_target_coast_ok_set0/set1`, `tcc_trq_rate_filt_set0/set1/set2`, `tcc_trq_rate_filt_shift_set0/set1/set2`.
- **Ghidra per-set stragglers:** `tcc_slip_setpoint_map_set6/set13/set18/set26`, `tcc_slip_turb_torque_map2_set0`, `tcc_slip_pid_gain_f0`, `tcc_slip_pid_temp_factor`, `tcc_drive_slip_off_map_a_set0`, `tcc_drive_slip_off_map_b_set0`, `tcc_coast_slip_off_map_b_set0`, `tcc_open_press_min_map_set1`, `tcc_press_error_map_set2`, `tcc_press_turb_torque_map_set6`, `tcc_gain_temp_map_c_set5`, `tcc_torque_limit_time_map_set0`, `tcc_lockup_turbine_map_a`, `tcc_speed_weight_engine`, `tcc_temp_coolant_factor_a`, `tc_torque_ratio_curve_0x196300`.

Coverage: 48 items across the four torque-converter categories, 4 in "Ghidra new: torque converter", 39 TCC entries under unlabelled categories, and the 9 `thermode_gear_tcc` torque-limit curves — every address verified against `8hpe84_cali_v1.xdf` (`tools/xdf_ls.py`), every drop verified by title diff against `8hpe70_cali_v3.xdf`.
