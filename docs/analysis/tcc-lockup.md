# Torque-converter clutch (TCC) lock-up: deep dive

Scope: everything the XDF metadata says about how this calibration (ZB 8646496, E-series 8HP,
Bosch ITCU2/SH-2A, big-endian; calibration at flash 0x180200–0x1FFFFF) models TCC behaviour.
Addresses below are flash addresses as quoted in the RE notes ("@0x…"); the XDF table address
(start of the z-data, after the inline axes) is given as "XDF z@" where it differs. **We have XDF
metadata only — structure, addresses, axes and the value ranges quoted in descriptions. No live
calibration values.** Confidence ratings are preserved from the RE evidence verbatim.

---

## 1. Architecture

### 1.1 Five CAL parameter blocks

The TCC software is organised around *five* CAL blocks in the 0x181E18–0x182900 pointer region
(the task brief names four; the group evidence adds a fifth, `tccadp_block`). Each is a parameter
block that boot-time setter code installs behind a RAM base pointer (`DAT_fff84axx`); the control
functions then read calibration through `base + offset` slots. All five are touched by
`FUN_000229bc` ("use-evidenced, unit not physical" — likely init/checksum traversal). **None of
the five blocks has a proven internal layout** — each is emitted in the XDF as a single value or
a raw gap-length table of 16-bit words.

| Block | Flash addr | RAM base ptr | Role per evidence | Confidence |
|---|---|---|---|---|
| `tcmodel_block` | 0x181E18 | DAT_fff84a10 | Converter physical model: +0x00 → K-factor curve (0x1999B0), +0x04 → mu curve (0x1999E4), +0x08/+0x0C dynamic params. ROM default twin at 0x4B11C; setter 0xBCB2C selects CAL, 0xBCB24 the ROM default. | HIGH |
| `tccadp_block` | 0x1824D4 | DAT_fff84a54 | TCC adaptation. Readers 0xC3608 (+0x44 → curve 0x19E9A0), 0xC3758 (+0x48 → curve 0x19E9B4), 0xC3B22 (+0x4C → curve 0x19E9D0). Emitted as 40 raw values (gap length, layout not proven). | MED |
| `tccctrl_block` | 0x182524 | DAT_fff84a58 | "Lock-up/coast/setpoint tables" — the open/close/coast/output-torque data cluster at 0x19E0xx–0x19FAxx. | MED |
| `tcc_aux_block` | 0x1826A8 | DAT_fff84a5c | "Coast/gear limits" at offsets +0x00/+0x18/+0x20/+0x24/+0x2C/+0x34. | MED |
| `tccslip_block` | 0x182840 | DAT_fff84a60 | Slip control: "setpoint maps +0xC8..+0x140, slip PID +0x1B8..+0x1DC, press calc" — the slip data cluster at 0x1A07xx–0x1A1Bxx. | MED |

A sixth, unnamed block also exists: `converter_lockup_curve` is read via **DAT_fff84a24+0x4**
(readers 0xBA618/0xBA798), i.e. through a base pointer that is *not* one of the five above. The
overspeed-protection curves (`tctrq_*`) and `tc_torque_ratio_curve` likewise sit outside the five
blocks.

### 1.2 Reader functions (control-flow skeleton)

The reader functions bound to labelled tables sketch the controller:

- **Converter model**: `tcmodel_pump_torque` (0xC4EAA) / `tcmodel_pump_torque_dyn` (0xC4F0E) read
  the K curve; `tcmodel_torque_ratio` / `tcmodel_turbine_torque` (0xC4E6C/0xC4E82) read the mu
  curve. This computes pump/turbine torque from speeds — the feedforward plant model.
- **Phase sequencing / base pressure**: `FUN_000dd156` reads `tcc_phase_map`;
  `tcc_phase_8f84` (0xDD19E) reads `tcc_ramp_curve`; `FUN_000dcf6a` reads the fill- and
  hold-pressure maps. Together these form the open → fill → ramp → slip/lock pressure schedule.
- **Slip-torque setpoint**: `FUN_000dd238` sums `tcc_slip_target_map` (tcc+0x128), a curve at
  tcc+0x12C, and `tcc_slip_cond_map` (tcc+0x140) into a saturated s16 slip-torque setpoint.
- **Slip-target (rpm) shaping**: `FUN_000dba7c` / `FUN_000dbe6e` (target curve, gain b),
  `FUN_000dac8c` (PT1 setpoint targets), `FUN_000da67c` (setpoint tab2), `FUN_000da984`
  (pedal weight), `tcc_neg_slip` (0xDD208, coast negative slip).
- **Slip PID gain scheduling**: `FUN_000db5aa` reads `tcc_slip_pid_gain_a` plus four sibling
  temperature curves (0x1A0D80/0x1A0DA4/0x1A0DC8/0x1A0EA4).
- **Pressure shaping / limits**: `FUN_000dd49a` (rate-of-change and turbine-accel/torque curves),
  `FUN_000dd8fa` = `tcc_press_torque_calc` (coast torque, curve_b69e), `FUN_000ddc1a` =
  `tcc_press_filter` (filter curves), `FUN_000dddca` (open-on-slip maps).

### 1.3 How slip control relates to lock-up scheduling

Per the evidence, this calibration does **not** model lock-up as per-gear apply/release speed
lines (none exist anywhere in the XDF — see §5). Instead the TCC is run as a *continuously
slip-controlled* clutch:

1. A phase state machine (readers 0xDD156/0xDD19E/0xDCF6A) sequences pressure: fill pulse →
   hold → ramp (driven by a percent-ratio input) → closed-loop phase.
2. In the closed-loop phase, a slip **setpoint** is produced from operating point (slip, torque,
   pedal, oil temperature, condition class). On this reading — an inference from the structure,
   not a proven state machine — "locked" is simply the regime where the scheduled slip target
   goes to ~0; controlled slip (micro-slip) and open would be the other regimes.
3. A PID with temperature- and error-scheduled gains trims commanded pressure to hold the slip
   target; the converter model (K/mu) provides the torque feedforward that converts a slip-torque
   setpoint into pressure.
4. Separate open/close condition maps (§2) decide transitions out of / into the closed state
   (e.g. open on large negative slip in coast, close pressure/time as functions of an
   unidentified 0–4.3 quantity).

---

## 2. Lock-up scheduling (open / close / slip-regime selection)

Every item in the metadata that governs when the clutch opens, closes, or changes slip regime.
Units in quotes are the RE-note axis annotations verbatim; "?" means the note gives only a range.

| Item | Flash addr (XDF z@) | Shape/type | Axes → z | Confidence / reader |
|---|---|---|---|---|
| `converter_lockup_curve` | 0x19A9D8 (0x19A9EC) | 4x1 f32 | x 0..100 (input DAT_fff89d38) → z 0..0.7 | LOW. Readers 0xBA618/0xBA798 via DAT_fff84a24+0x4. Meaning of x and z unproven; name is an RE hypothesis. |
| `tcc_close_press_map` | 0x19E340 (0x19E370) | 6x4 f32 | x 0..4.3 (?); y 0.1..5 (?) → z -0.9..5 (pressure-like) | MED (object match to F cal; varies across 21 versions). No bound reader. Plausibly close-apply pressure vs. two unidentified quantities. |
| `tcc_close_time_map` | 0x19E460 (0x19E490) | 6x4 f32 | x 0..4.3; y 0.2..1 → z 0..0.4 (time-like, s?) | MED, same evidence class as close_press. No bound reader. |
| `tcc_open_temp_press_map_set0` | 0x19C4BC (0x19C4F4) | 6x6 f32 | x -20..110 (temp °C-like); y 0..160 → z 0..1.1 | MED. Reader FUN_000bbfe2 (index-resolved, use-evidenced, unit not proven). |
| `tcc_open_temp_press_map_set2` | 0x19CF64 (0x19CF9C) | 6x6 f32 | same axes → z 0..1.1 | LOW (second set; membership proven, no reader bound to this copy). |
| `tcc_open_speed_slip_map` | 0x19F31C (0x19F334) | 4x4 s16 | x -1500..-200; y -1000..0 → z 100..700 | LOW. Reader FUN_000dddca. Negative slip/speed axes suggest coast-open thresholds. |
| `tcc_open_speed_slip_map2` | 0x19F3FC (0x19F424) | 8x8 s16 | x 50..2004; y 50..404 → z -2000 (flat) | LOW. Reader FUN_000dddca. |
| `tcc_coast_torque_map` | 0x19F2DC (0x19F2F4) | 4x4 s16 | x turbine speed rpm (fff8b544); y negative engine torque demand ×0.1 Nm (fff8b496) → z -50..-30 | LOW (E→F label transfer). Reader `tcc_press_torque_calc` 0xDD8FA — coast capacity input to the pressure/torque calc; any gating of coast lock behaviour is conjecture, not evidenced. |
| `tcc_conv_capacity_map` | 0x19E9DC (0x19EA0C) | 4x6 f32 | x 1000..6000 (rpm); y 20..130 → z 88.8..95.3 | LOW. No bound reader. Plausibly converter capacity/efficiency threshold used in the lock decision. |
| `tcc_slip_cond_map` | 0x1A167C (0x1A169C) | 6x6 s16 | x 40..120; y 60..150 → z 0..7 | HIGH. Reader 0xDD238: summed (as tcc+0x140) with map +0x128 and curve +0x12C into the slip-torque setpoint — a small-integer condition/class term that shifts the operating regime. |
| `tcc_aux_block` limits | 0x1826A8 | raw block | offsets +0x00/+0x18/+0x20/+0x24/+0x2C/+0x34 = "coast/gear limits" | MED for the block's role; individual offsets/units NOT proven. This is the only per-gear gating evidence in the whole TCC set. |
| `tcc_neg_slip_curve` | 0x1A1970 (0x1A1978) | 2x1 s16 | x -500..-150 → z -500..-300 | HIGH. Reader `tcc_neg_slip` 0xDD208 (tcc+0x1CC), accumulated /100 → s16 at p+2 (0.01 scale). Negative (coast) slip target — consistent with overrun micro-slip rather than hard open, though that reading is interpretation. |
| `tcc_eng_temp_factor` | 0x1A10A0 (0x1A10B8) | 2x2 f32 | x 1500..2500 (rpm-like); y 30..50 (temp-like) → z 1..1 | LOW. No reader. Temperature enable/scale factor by name only. |
| `tcctemp_heat_coeff_map` | 0x19E868 (0x19E890) | 4x4 f32 | x 600..4000; y 30..110 → z 1.3..3 | LOW. No reader. TCC thermal-model coefficient by name only; any role in open/limit decisions is conjecture. |

**Notably absent:** per-gear lock-up apply/release speed-vs-pedal lines. The shift-line group
(483 items) contains only gear-change lines; a full-inventory search for lockup / lock-up /
wandler / wk / converter finds nothing else. See §5.

Related but outside this group: the `nidle_*` family (neutral-idle decoupling by name,
0x19Axx–0x19Exx, readers in the 0xD8xxx and 0xBAxxx–0xBBxxx ranges) manages converter/clutch
state at standstill, and
`nidle_open_press_step` (0xD83F8) reads `tcc_press_offset_curve` — evidence that the standstill
decoupling function and TCC pressure control share calibration.

---

## 3. Slip control

### 3.1 Setpoint formation

| Item | Flash addr (XDF z@) | Shape/type | Axes → z | Confidence / use |
|---|---|---|---|---|
| `tcc_slip_target_map` | 0x1A14FC (0x1A151C) | 6x6 s16 | x slip -1000..1200 (rpm); y torque 800..5000 → z 13..21 | HIGH. Reader 0xDD238: `cal_map_s16(tcc+0x128)` summed with curve +0x12C and map +0x140, saturated to s16 → slip-torque setpoint at p+0x1A. |
| curve at tcc+0x12C (likely `auto_cal_curve_s16_1a1564`) | 0x1A1564 | 6x1 s16 | x 40..160 → z 0..17 | LOW (auto-detected; reader FUN_000dd238 matches the +0x12C slot in the setpoint sum). Not formally bound to the slot. |
| `tcc_slip_cond_map` | 0x1A167C | 6x6 s16 | x 40..120; y 60..150 → z 0..7 | HIGH. Third term of the same sum (see §2). |
| `tcc_slip_target_curve` | 0x1A0F88 (0x1A0FA4) | 6x1 f32 | x slip -50..450 → z gain 0.5..2.5 | HIGH. Readers 0xDBA7C/0xDBE6E: `cal_curve_f32(oil_temp_raw/10, tcc+0xF4)` added to DAT_fff8a5dc, clamped ≤ `clamp(rpm/1000,0,curve(tcc+0x1C))` term → **slip target in rpm**. |
| `tcc_slip_gain_b` | 0x1A0ECC (0x1A0EE8) | 6x1 f32 | x pedal/derivative -100..400 → z gain 2.0..4.0 | HIGH. Reader 0xDBA7C: `cal_curve_f32(oil_temp_raw/10, tcc+0xE4)*0.01` added to the slip-target accumulator (p+8) each step — a ramp-rate term. |
| `tcc_slip_2d_offset` | 0x1A1AE0 (0x1A1B18) | 6x6 f32 | x -800..500; y -400..400 → z 0..0 (flat in this family) | MED (object match; varies across versions: all-zero in VE01, nonzero in VM01/M120). Slip-target offset by name; no bound reader. |
| `tcc_setpoint_curve_a` | 0x1A1A68 (0x1A1A70) | 2x1 s16 | x 0..5 → z 15759..23593 | HIGH. Reader 0xDAC8C: `cal_tab2_u32(tcc+0x1EC)` → f32 at p+0x44 = PT1-filtered setpoint target. |
| `tcc_setpoint_curve_b` | 0x1A1A98 (0x1A1AA0) | 2x1 s16 | x 0..5 → z 15759..23593 | HIGH. Same reader, slot tcc+0x1F0. |
| `tcc_setpoint_tab2` | 0x1A1BA8 (0x1A1BB0) | tab2 u32 | x "slip/gear" → ? | LOW. Reader 0xDA67C (tcc+0x200). Layout/meaning not proven. |
| `tcc_pedal_weight_curve` | 0x1A197C (0x1A1984) | 4x1 u8 | x 0..255 (pedal raw) → z 0..100 % | HIGH. Reader 0xDA984: `(p[1]*u)/100.0` → percent weight applied to a torque — pedal-dependent blending of the torque input to the slip setpoint. |
| `tcc_neg_slip_curve` | 0x1A1970 | 2x1 s16 | x -500..-150 → z -500..-300 | HIGH. Coast (negative) slip target, 0.01 scale (see §2). |
| `tccslip_curve_20c` | 0x1A18F4 (0x1A1900) | 4x1 s16 | x 1000..4000 → z 40 (flat) | LOW. Readers 0xC3D9A/0xC3E22/0xC3EF0. |
| `tcc_slip_turb_torque_map2_set1` | 0x19FFB0 (0x19FFD0) | 6x6 s16 | x 1000..2300; y -500..3000 → z 20 (flat) | MED (run-context match). Readers 0xAC4A0/0xDDD82, slot not attributable. |

### 3.2 PID parameters

| Item | Flash addr (XDF z@) | Shape/type | Axes → z | Confidence / use |
|---|---|---|---|---|
| `tcc_slip_pid_gain_a` | 0x1A0D5C (0x1A0D70) | 4x1 f32 | x oil temp 0..60 → z 0.8..1.0 | MED. Reader 0xDB5AA. |
| sibling curves (auto) | 0x1A0D80 / 0x1A0DA4 / 0x1A0DC8 / 0x1A0EA4 | 4x1 f32 each | x 0..60 (oil temp) → z 0.65..1.0 / 0.5..1.0 / 0.8..1.0 / 0.8..1.0 | LOW (auto-detected). All read by the same FUN_000db5aa — a temperature-scheduled gain set (plausibly P/I/D/feedforward scalers). |
| `tcc_slip_pid_gain_e4` | 0x1A07E4 (0x1A081C) | 6x6 f32 | x -100..150; y -60..60 → z 0.1..20 | LOW. Block membership proven (tcc slot +0x1E4 by name), **no reader bound**. Axes look like error × error-rate gain scheduling. |
| `tcc_slip_pid_gain_ec` | 0x1A0974 (0x1A09AC) | 6x6 f32 | x -100..50; y -240..150 → z 0.1..15 | LOW. Same evidence class (slot +0x1EC by name). |
| unlabelled 6x6 f32 run | 0x1A071C, 0x1A08AC, 0x1A0A3C, 0x1A0B04, 0x1A0BCC, 0x1A0C94 | 6x6 f32 | error-like axes (±80..±150 × ±150..±255) → z 0.01..20 | LOW (auto-detected, readers unknown, meaning "not analysed" in the evidence). Interleaved with the two named PID maps — plausibly the rest of the PID gain-map family, but unattributed. |
| `auto_1a0dec` | 0x1A0DEC | 8x4 f32 | x -400..400; y 20..90 → z 0.5..1.0 | LOW, auto-detected, reader unknown — slip-error × temp factor by position. |

### 3.3 Slip-torque conversion factors

| Item | Flash addr (XDF z@) | Shape/type | Axes → z | Confidence |
|---|---|---|---|---|
| `tcc_slip_torque_factor_19c` | 0x1A12EC (0x1A1324) | 6x6 f32 | x -900..800; y -100..400 → z 0..0.6 | LOW (slot +0x19C by name; no reader). |
| `tcc_slip_torque_factor_1a0` | 0x1A13B4 (0x1A13FC) | 8x8 f32 | x -1200..1200; y -150..400 → z 0..1.7 | LOW (slot +0x1A0 by name; no reader). |
| `auto_1a10dc` | 0x1A10DC | 8x8 f32 | x -1200..700; y -150..400 → z 0..1.7 | LOW, auto — same family by axes, unlabelled. |
| `auto_1a1224` | 0x1A1224 | 6x6 f32 | x -600..700; y -50..400 → z 0..0.4 | LOW, auto — same family by axes, unlabelled. |
| `tcc_torque_capacity_drive_coast` | 0x1A0F00 (0x1A0F30) | 8x2 f32 | x -50..600; y 0/1 (drive/coast flag) → z 200..400 | LOW (no reader). Clutch torque capacity by direction, by name. |

### 3.4 Converter model (feedforward plant)

| Item | Flash addr (XDF z@) | Shape/type | Axes → z | Confidence / use |
|---|---|---|---|---|
| `tcmodel_K_curve` | 0x1999B0 (0x1999CC) | 12x1 s16 | x turbine rpm 0..15000 → z K factor -769..1775 | HIGH. Readers `tcmodel_pump_torque` / `_dyn` via DAT_fff84a10+0. |
| `tcmodel_mu_curve` | 0x1999E4 (0x1999F4) | 6x1 s16 | x speed-ratio index 0..10200 → z mu (torque ratio ×10000) 0.9708..1.8650 | HIGH. Readers `tcmodel_torque_ratio` / `tcmodel_turbine_torque` via +4. |
| `tc_torque_ratio_curve` | 0x19A854 (0x19A864) | 6x1 s16 | x 0..920 → z 991..1865 | LOW. Reader 0xB9D10. A second torque-ratio curve (different consumer, outside the five blocks). |
| `tcmodel_block` +0x08/+0x0C | 0x181E18 | scalars | "dyn params" | HIGH for the block, values/meaning not extracted. |

The mu range (0.97..1.87 — consistent with a stall torque ratio ≈1.87 falling toward ≈1 at
coupling, though only the range, not the curve shape, is quoted) and the K curve are
**converter-specific hardware data**. For a swap from the original turbo-matched converter to an
N20-spec converter these are the model-side items that describe the physical converter; the
metadata gives no evidence of which direction the live values would need to move (no binary).

---

## 4. Pressure control: how commanded TCC pressure is formed

The evidence supports this chain (HIGH-confidence links marked):

1. **Phase base pressure** — `tcc_phase_map` @0x1A1580 (XDF z@0x1A1590), 2x2 s16, breakpoints
   1000/3000 × 1000/4000 (axis meaning unknown). HIGH: reader 0xDD156,
   `cal_map_s16(tcc+0x130)` → saturate → f32 at p+0x14 = raw/100.0 (**0.01 bar/LSB**) and raw
   u16 at p+0x28 (10 mbar units). This is the generic bar-setpoint writer for the phase.
2. **Fill pulse** — `tcc_press_fill_map` @0x1A15AC (z@0x1A15CC), 6x6 s16, x engine rpm
   1000..6000, y torque -250..300 → z "100..150 mbar" raw (0.01 bar/LSB → 1.00..1.50 bar).
   HIGH: reader 0xDCF6A, slot tcc+0x138.
3. **Hold pressure** — `tcc_press_hold_map` @0x1A1614 (z@0x1A1634), 6x6 s16, same x axis → z
   40..100 raw (0.40..1.00 bar). HIGH: reader 0xDCF6A, slot tcc+0x13C.
4. **Ramp** — `tcc_ramp_curve` @0x1A1598 (z@0x1A15A4), 2x1 f32. HIGH: reader `tcc_phase_8f84`,
   input `clamp(ratio,0,100)` percent-ratio → f32 ramp setpoint DAT_fff8a5d0.
5. **Torque feedforward** — `tcc_press_torque_calc` (0xDD8FA) combines `tcc_coast_torque_map`
   (LOW) and `tcc_curve_b69e` @0x19F4A4 (4x1 s16, x fff8b69e 180..250 → z 100..300, LOW); the
   slip-torque setpoint (§3.1) is *plausibly* converted via the slip-torque factors (§3.3 —
   labelled by name only, no bound readers, so this link is unproven) and the converter model
   (§3.4). `tcc_output_torque_map` @0x19F8A8 (z@0x19F8C4), 6x4 s16, x 350..2500, y
   -50..400 → z 50..400, MED, readers 0xDCA5C/0xDCAE0/0xDCB2C (separate functions, not tied to
   this calc), is torque-path-shaped by name and axes; its exact place in the chain is unproven.
6. **Rate limiting** — reader 0xDD49A applies `tcc_press_rate_drive_curve` set0/set1 @0x19F97C
   (2 blocks × 4 pt, x -4000..1500 → z 50..500, LOW), `tcc_press_turb_accel_curve` set0/set1
   @0x19F968 (x 0..7000 turbine-accel-like → z flat 0; set0 MED, combined entry LOW), and
   `tcc_press_turb_torque_map` set0 @0x19F930 (4x4 s16, LOW). Set1 @0x19FA10 (4x4 s16, LOW) is
   **not** bound to 0xDD49A — its only noted readers (0xAC4A0/0xC4998/0xDD704/0xDD7F6) are
   "slot not attributable".
7. **Output filtering** — `tcc_press_filter` (0xDDC1A) reads `tcc_curve_u8_48` @0x19F4B8
   (x 191..229 → z 20..100, LOW) and `tcc_curve_u16_50` @0x19F4D4 (x 0..191 → z 30..150, MED).
8. **Corrections / supervision** — `tcc_gain_press_map3_set0` @0x19BF78 (4x8 f32, x 660..900,
   y 50..850 → z 0.8..1.0, MED, reader 0xBBFE2, use-evidenced but "unit not proven"): gain-like
   by name and z-range;
   `tcc_press_error_map_set0` @0x19BBD8 (MED) + copy @0x19C680 (LOW), 6x6 f32, x -15..0,
   y 7..100 → z flat 0: pressure-error correction (zeroed in this family);
   `tcc_press_time_temp_map_set2` @0x19C8D8 (8x8 f32, x 0..3, y -10..110 temp → z 0..20, LOW);
   `tcc_press_offset_curve` @0x19ABE4 (4x1 f32 → z -4..0 bar, LOW, reader
   `nidle_open_press_step` 0xD83F8 — shared with the neutral-idle open function).
9. **Adaptation** — `tccadp_block` curves at 0x19E9A0 (4 pt, x 1100..1400 → z -2..3), 0x19E9B4
   (6 pt, x 0..10000 → z 0), 0x19E9D0 (2 pt, x 1000..1500 → z 100); all LOW/auto-detected
   ("meaning not analysed"), readers 0xC3608/0xC3758/0xC3B22. The block is adaptation-related by
   name (MED); "long-term pressure correction of the apply point" is a guess, not evidence.

The `_set0/_set1/_set2` suffixes indicate multiple parameter sets (per drive program or per
variant); the evidence repeatedly notes the selecting index is "slot not attributable", so which
set is active when is **not known**.

---

## 5. What is NOT known

Explicit gaps — be suspicious of anything below before tuning on top of it.

1. **No lock-up shift lines exist in this XDF.** A full-inventory search (lockup, lock-up,
   wandler, wk, converter) finds only `converter_lockup_curve` (LOW, 4 points, unknown input
   scaling) and the block descriptions. The 483 shift-line items are gear changes only. Either
   the 8HP schedules lock-up purely through the state machine + condition maps above, or the
   actual scheduling tables are among the unlabelled structures. **The primary "when does it
   lock" calibration has not been positively identified.**
2. **CAL block internal layouts are unproven.** All five blocks are emitted as single values or
   raw gaps ("no layout evidence; not proven"). Slot offsets quoted (e.g. tcc+0x128) come from
   reader decompilation, not from a mapped structure; `tcc_aux_block`'s per-gear limits are a
   one-line note with no offsets/units/types proven.
3. **Phase/axis meanings.** `tcc_phase_map` is HIGH for its pressure-writing use but its 2x2
   axes (1000/3000 × 1000/4000) are unidentified. `tcc_close_press_map` / `tcc_close_time_map`
   axes (0..4.3, 0.1..5, 0.2..1) are unidentified ranges — plausibly bar and seconds, not proven
   — and neither has a bound reader in this binary.
4. **LOW-confidence labels are name-transfers.** Roughly half the group (open_speed_slip maps,
   conv_capacity, coast_torque, torque factors, PID e4/ec, capacity_drive_coast, offset curve,
   eng_temp_factor, heat_coeff, press_turb_torque, rate_drive, tccslip_curve_20c, tccctrl
   curves) is labelled by byte-identical object match or E→F label transfer from a *different*
   calibration. Within that set, some (conv_capacity, torque factors, PID e4/ec,
   capacity_drive_coast, eng_temp_factor, heat_coeff, turb_torque set1) have data-pointer-only or
   no reader evidence here, while others (open_speed_slip maps, coast_torque, offset curve,
   rate_drive, turb_torque set0, tccslip_curve_20c, tccctrl curves) **do** have bound readers in
   this binary — it is only the *name* that is transferred. Names may be right while slots/uses
   differ. (`tcc_setpoint_tab2` is LOW for a different reason: its reader 0xDA67C is bound here,
   but the tab2 layout/meaning is unproven — it is not a name-transfer.)
5. **Dozens of unlabelled auto-detected structures sit inside the TCC clusters** (≈28 in the
   slip cluster 0x1A07xx–0x1A1Bxx alone, and on the order of 60 more in the tccctrl cluster) and
   are functionally dark, including: six 6x6 f32 PID-shaped maps 0x1A071C–0x1A0C94; 0x1A0DEC (8x4),
   0x1A0FBC (6x4, x -30..400, y 3000..7000 rpm-like, z -1.55..0 — pressure-offset-shaped),
   0x1A10DC / 0x1A1224 (torque-factor-shaped), 0x1A16E4 / 0x1A17AC (6x6, temp×temp),
   0x1A1874, 0x1A1908, 0x1A1988, 0x1A1A40 (7 pt, x -10..200 → 0..250), 0x1A1BD8 (4x6,
   x 1500..6496 rpm-like, y -40..550 → 0..50), and in the tccctrl cluster 0x19E0D4–0x19F9FC a long
   run of curves/maps around the open/close tables. Any of these could be the missing
   scheduling tables.
6. **Set selection** (set0/set1/set2 families; tcc_setpoint curves a/b; press_rate set0/1) —
   the index that picks the active set is not attributed to a signal (drive program? gear
   range?).
7. **No live values.** This is XDF metadata: all z-ranges quoted are from RE notes on the
   analysed family of binaries, not from the flash image being tuned. Flat ranges quoted as
   "0..0" or "20..20" may differ in other versions (several items explicitly vary across the 21
   analysed versions).

---

## 6. Implications for an N52K (NA) + N20-spec converter — within what the metadata supports

Asked-for context, kept strictly to what the structures imply; no values are known.

- Because this calibration runs the TCC as a slip controller rather than on lock-up speed lines,
  the "use the converter to mask turbo lag" behaviour lives in the **slip setpoint path**
  (`tcc_slip_target_map` torque axis 800..5000 raw, `tcc_slip_target_curve`,
  `tcc_pedal_weight_curve`, `tcc_slip_cond_map`) — these HIGH-confidence items are where an NA
  engine with immediate response could tolerate earlier/tighter lock (lower slip targets at
  lower torque), not in any shift-line table.
- The converter hardware itself is described to the TCU by `tcmodel_K_curve` and
  `tcmodel_mu_curve` (both HIGH, small 12/6-point curves). An N20-spec converter with a
  different K-factor/stall characteristic than the donor calibration's converter would make the
  torque feedforward wrong until these are corrected — a plausible source of hunting or
  slip-error adaptation drift. We cannot say how far off they are without the binary values and
  the converter's data.
- Fill/hold pressures (`tcc_press_fill_map`, `tcc_press_hold_map`, HIGH, 0.01 bar/LSB) and the
  close press/time maps (MED, unproven axes) set apply feel; the PID gain family (§3.2) sets
  stability around the new converter's stiffness. Changes here are testable but half the gain
  family has no bound reader — log before trusting.
- Caution: `tcc_slip_cond_map` and `tcc_aux_block` gear limits are the only identified per-gear/
  per-condition gating, and the aux block is unproven. Aggressive early lock cannot be safely
  scheduled per gear from this XDF as labelled today.
