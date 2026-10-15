# Torque converter (lock-up clutch control)

The torque converter clutch (TCC) subsystem decides when the 8HP's converter lock-up clutch opens, closes, or runs in controlled slip, and how much pressure holds it there. The TCU runs a converter *model* (K-factor and torque-ratio curves) to estimate pump/turbine torque, computes a **slip target** (how many rpm of slip it wants between engine and turbine), and closes the loop with a slip PID whose output becomes a **pressure setpoint** for the TCC solenoid. A separate scheduling layer decides the open/close transitions (ramps, close pressure and time, open thresholds) as a function of speed, torque, and oil temperature. Adaptation (the `tccadp` block) trims these pressures over time as the clutch wears.

In practice these families interact in a chain: the model estimates torque at the converter → the slip target maps pick a desired slip for that operating point → the PID gains determine how aggressively the controller corrects slip error → the fill/hold/phase pressure maps set the feedforward pressure the loop works around → the open/close maps decide when the whole thing engages or releases. Confidence ratings below come straight from the RE evidence: HIGH means a reader function and unit/use were proven; MED means strong structural or cross-version evidence; LOW usually means a byte-identical object match against the reference 'F' build with no bound reader in this calibration — treat those names as plausible, not proven.

### Torque converter: slip

This category holds the slip-control loop: target maps, conditioning, and PID gains. 13 items.

**Slip target setpoint chain** — 3 members, 0x1A0FA4–0x1A169C, s16 6x6 maps + f32 6-pt curve. Confidence HIGH. The two s16 maps are summed — together with a third curve at `tcc+0x12c` that is not a separate item here — and saturated into the slip-torque setpoint (`cal_map_s16(tcc+0x128)` + curve `+0x12c` + map `+0x140` → sat_s16), read by the slip setpoint chain at FUN_000dd238; the f32 curve sits at `tcc+0xf4` and feeds a separate slip-target-in-rpm computation (readers 0xdba7c/0xdbe6e). Together this is the primary "how much slip do I want" calibration: raising targets gives a softer, more thermally loaded converter; lowering them gives a tighter, more direct feel (and more driveline harshness).

| Parameter | Address | Shape | Axes / units | What it does |
|---|---|---|---|---|
| tcc_slip_target_map | 0x1A151C | s16 6x6 | x: slip -1000..1200, y: torque 800..5000, z: target 13..21 | Main slip-torque setpoint contribution vs slip and torque |
| tcc_slip_cond_map | 0x1A169C | s16 6x6 | x: 40..120, y: 60..150, z: 0..7 | Conditioning term summed into the same setpoint |
| tcc_slip_target_curve | 0x1A0FA4 | f32 6 pt | x: slip -50..450, z: gain 0.5..2.5 | Oil-temp-indexed term added to the slip target; result clamped by `clamp_f32(rpm/1000,0,cal_curve_f32(...))` → slip target in rpm |

**Slip controller gain curves** — 2 members, 0x1A0D70 / 0x1A0EE8, f32 curves. Confidence MED (gain_a) / HIGH (gain_b). `tcc_slip_pid_gain_a` (4 pt, oil temp 0..60 → gain 0.8..1.0, with sibling curves at 0x1a0d80/0x1a0da4/0x1a0dc8/0x1a0ea4 on the same axis) scales the slip PID over oil temperature (gain 0.8–1.0 across 0–60; the evidence does not fix which end of the range is cold). `tcc_slip_gain_b` (6 pt, x: pedal/derivative -100..400, z: gain 2.0..4.0) is evaluated as `cal_curve_f32(oil_temp_raw/10, tcc+0xe4)*0.01` and added to the slip-target accumulator each control step. Changing these alters how quickly and smoothly the controller chases its slip target; too much gain shows up as TCC shudder/hunting.

**Slip PID gain maps (unbound)** — 2 members, 0x1A081C (`tcc_slip_pid_gain_e4`, f32 6x6, z 0.1..20) and 0x1A09AC (`tcc_slip_pid_gain_ec`, f32 6x6, z 0.1..15). Confidence LOW: byte-identical to the F-build objects of the same name and proven members of a calibration block, but no reader was bound in this build. Presumed 2-D PID gain scheduling over slip-error/derivative axes. Verify with logging before tuning.

**Slip-torque factor maps** — 2 members, 0x1A1324 (`tcc_slip_torque_factor_19c`, f32 6x6, z 0..0.6) and 0x1A13FC (`tcc_slip_torque_factor_1a0`, f32 8x8, z 0..1.7). Confidence LOW (F-build object match, block membership proven, no bound reader). Presumed torque-dependent scaling factors in the slip chain.

**Slip offsets and auxiliary slip curves** — 3 members. Confidence MED/LOW. `tcc_slip_2d_offset` (0x1A1B18, f32 6x6, all zero in this calibration; MED — F object match plus cross-version variation across 21 calibrations) is an offset applied to the slip calculation. `tcc_slip_turb_torque_map2_set1` (0x19FFD0, s16 6x6, x 1000..2300, y -500..3000, flat 20; MED — run-context match, reader FUN_000ac4a0/FUN_000ddd82 with slot not attributable) is a per-set turbine-torque-indexed slip table. `tccslip_curve_20c` (0x1A1900, s16 4 pt, x 1000..4000, flat 40; LOW, readers FUN_000c3d9a/c3e22/c3ef0) is a small auxiliary curve.

**tccslip_block anchor** — 1 member, 0x182840, 16-bit constant. Confidence MED. The calibration block behind `DAT_fff84a60` containing the setpoint maps (+0xc8..+0x140) and slip PID terms (+0x1b8..+0x1dc). Emitted as a single value because no full layout was proven — it is a structural anchor for navigation, not a tunable parameter.

### Torque converter: pressure / control

The pressure side of TCC control: feedforward fill/hold pressures per phase, ramps, rate limits, and correction maps. 18 items.

**Phase pressure setpoints (fill / hold / phase / ramp)** — 4 members, 0x1A1590–0x1A1634. Confidence HIGH, with proven readers (0xdcf6a, 0xdd156, tcc_phase_8f84) and proven scaling: the s16 raw value is converted as `*(f32*)(p+0x14)=(float)u/100.0` — i.e. **0.01 bar/LSB**. These are the central feedforward pressures a tuner would touch for TCC apply feel: fill pressure primes the clutch, hold pressure keeps it applied, the phase map sets the bar setpoint per phase, and the ramp curve shapes the transition.

| Parameter | Address | Shape | Axes / units | What it does |
|---|---|---|---|---|
| tcc_press_fill_map | 0x1A15CC | s16 6x6 | x: engine rpm 1000..6000, y: torque -250..300, z: 100..150 (0.01 bar/LSB) | Fill-pressure setpoint during TCC engagement |
| tcc_press_hold_map | 0x1A1634 | s16 6x6 | same axes, z: 40..100 | Hold-pressure setpoint once applied |
| tcc_phase_map | 0x1A1590 | s16 2x2 | breakpoints 1000/3000 x 1000/4000; z → bar setpoint `(float)u/100.0`, also stored raw (10 mbar) | Per-phase pressure setpoint |
| tcc_ramp_curve | 0x1A15A4 | f32 2 pt | x: 0..1 (percent-ratio input, `clamp_f32(ratio,0,100.0)`) | Ramp setpoint shaping the pressure transition |

**Per-set pressure feedforward (rate / turbine accel / turbine torque)** — 6 members around 0x19F948–0x19FA28, mostly associated with reader FUN_000dd49a (the set1 turbine-torque map instead shows readers FUN_000ac4a0/c4998/dd704/dd7f6, slot not attributable). Confidence LOW–MED. These exist in two copies, one per block (set0, set1), with per-block breakpoints published as separate " axis" tables. They shape the pressure command from turbine dynamics: `tcc_press_rate_drive_curve` + axis (0x19F988/0x19F980, s16 4 pt, x -4000..1500 → z 50..500; LOW) is a rate term vs (likely) slip rate; `tcc_press_turb_accel_curve` + axis (0x19F974/0x19F96C, 4 pt, x 0..7000 → z 0 in this cal; MED for the data — cross-version variation across 21 versions — with the two-copy structure itself rated LOW) keys on turbine acceleration; `tcc_press_turb_torque_map_set0/_set1` (0x19F948 / 0x19FA28, s16 4x4, zeroed in this calibration; LOW) key on turbine speed x torque. Zero-filled z-data here means the terms are inactive in this ZB — enabling them is unverified territory.

**Set-indexed pressure correction maps** — 4 members, bank0 block around T=04b734 (readers FUN_000ac4a0/FUN_000bbfe2, slot not attributable). Confidence MED/LOW. `tcc_gain_press_map3_set0` (0x19BFB0, f32 4x8, x 660..900, y 50..850, z 0.8..1; MED) looks like a multiplicative pressure gain; `tcc_press_error_map_set0` appears twice (0x19BC10 MED and 0x19C6B8 LOW — two byte-identical copies in different set slots), x -15..0, y 7..100, z all zero (inactive error correction); `tcc_press_time_temp_map_set2` (0x19C920, f32 8x8, x 0..3, y -10..110 (temperature-like), z 0..20; LOW) schedules a time quantity over temperature.

**Miscellaneous control curves** — 3 members. Confidence LOW. `tcc_press_offset_curve` (0x19ABF8, f32 4 pt, z -4..0 bar; label transferred from the F build where `nidle_open_press_step` reads it, reader FUN_000d83f8) is a pressure offset. `tccctrl_curve_124` (0x19F1DC, s16 2 pt, x -50..300, flat 40; reader FUN_000d9c5c) and `tccctrl_curve_a4` (0x19F0B0, s16 4 pt, x "difference/2" -100..100, z 0; reader FUN_000c45a2) are small control curves in the tccctrl block whose exact roles were not proven.

**tccctrl_block anchor** — 1 member, 0x182524, 16-bit constant. Confidence MED. The calibration block behind `DAT_fff84a58` holding the lock-up/coast/setpoint tables. Structural anchor only.

### Torque converter: lock-up / open / close

When the clutch engages and releases, plus the converter's physical model. 14 items.

**Converter model (K-factor and torque ratio)** — 3 members. Confidence HIGH. This is the mathematical model of the fluid converter itself, used to estimate pump and turbine torque (`tcmodel_pump_torque` / `tcmodel_turbine_torque`). These describe converter hardware — they should only change if the physical converter changes, and getting them wrong corrupts every torque estimate downstream.

| Parameter | Address | Shape | Axes / units | What it does |
|---|---|---|---|---|
| tcmodel_K_curve | 0x1999CC | s16 12 pt | x: turbine rpm 0..15000, z: K factor -769..1775 | Converter capacity (K) factor vs turbine speed |
| tcmodel_mu_curve | 0x1999F4 | s16 6 pt | x: speed ratio index 0..10200, z: mu (torque ratio x10000) 0.9708..1.8650 | Torque multiplication ratio vs speed ratio |
| tcmodel_block | 0x181E18 | const (16-bit anchor) | +0x00 K curve, +0x04 mu curve, +0x08/+0x0c dyn params | Block anchor for the converter model (ROM default twin at 0x4b11c) |

**Lock-up close scheduling** — 2 members, 0x19E370 / 0x19E490. Confidence MED (F object match + cross-version variation, but no bound reader in this build). `tcc_close_press_map` (f32 6x4, x 0..4.3, y 0.1..5, z -0.9..5) sets the pressure used during clutch close, and `tcc_close_time_map` (f32 6x4, x 0..4.3, y 0.2..1, z 0..0.4) the associated close time. Together they determine how fast and firm the lock-up engagement is — the classic "TCC apply flare vs. clunk" trade-off.

**Lock-up open scheduling** — 4 members. Confidence MED/LOW. `tcc_open_speed_slip_map` (0x19F334, s16 4x4, x -1500..-200, y -1000..0, z 100..700) and `tcc_open_speed_slip_map2` (0x19F424, s16 8x8, x 50..2004, y 50..404, z flat -2000) — both read by FUN_000dddca, LOW — schedule release thresholds from speed/slip. `tcc_open_temp_press_map_set0/_set2` (0x19C4F4 MED / 0x19CF9C LOW, f32 6x6, x -20..110 (temperature), y 0..160, z 0..1.1) give per-set temperature-dependent open-pressure terms in the FUN_000bbfe2 bank.

**Lock-up capacity and coast behaviour** — 3 members. Confidence LOW. `converter_lockup_curve` (0x19A9EC, f32 4 pt, x 0..100, z 0..0.7; readers 0xba618/0xba798) is a lock-up factor curve. `tcc_coast_torque_map` (0x19F2F4, s16 4x4, x turbine speed rpm, y engine torque demand x0.1 Nm (negative), z -50..-30; reader FUN_000dd8fa, label transferred from F `tcc_press_torque_calc`) handles the coast (negative-torque) side of TCC torque. `tcc_conv_capacity_map` (0x19EA0C, f32 4x6, x 1000..6000 rpm, y 20..130, z 88.8..95.3) looks like converter/clutch capacity vs speed and temperature (no bound reader).

**Adaptation and auxiliary block anchors** — 2 members, 16-bit constants. Confidence MED. `tccadp_block` (0x1824D4, published as 1x40 — length is simply the gap to the next label, no layout proven) is the TCC adaptation calibration block behind `DAT_fff84a54`, with readers 0xc3608/0xc3758/0xc3b22 pulling curves at +0x44/+0x48/+0x4c; per the F-transferred name, this is presumably where long-term TCC pressure adaptation is parameterised. `tcc_aux_block` (0x1826A8, behind `DAT_fff84a5c`) holds coast/gear limit entries (+0x00/0x18/0x20/0x24/0x2c/0x34). Both are anchors, not directly tunable values.

### Torque converter: other

Supporting curves: torque limits, setpoint shaping, filters, and thermal terms. 17 items.

**Engine-overspeed torque limiting (tctrq)** — 4 members, 0x19AA1C–0x19ABA8, s16 curves vs engine speed 0..10000 rpm. Confidence MED/LOW. `tctrq_overspeed_curve_10` (8 pt, flat factor 10000; MED, run-context match) and `tctrq_overspeed_curve_20` (z: factor x10000, flat 10000; LOW) are unity scaling factors in this cal; `tctrq_overspeed_torque_24` (12 pt, z 0..240; MED) and `tctrq_overspeed_torque_34` (12 pt, torque limit 240..0 — tapering to zero at high rpm; LOW) are the actual torque limit curves (readers FUN_000ba938 and tctrq_cac50; tctrq_cac9a reads curve_20, and curve_10 has no bound reader). If the transferred names hold, these cap converter-side torque as engine speed climbs; relevant if your swap revs past the stock calibration's limits.

**TCC setpoint shaping** — 3 members. `tcc_setpoint_curve_a` (0x1A1A70) and `tcc_setpoint_curve_b` (0x1A1AA0), both s16 2 pt, x 0..5, z 15759..23593, Confidence HIGH: read at 0xdac8c via `cal_tab2_u32` and written as `*(f32*)(p+0x44) = pt1_f32_step` — i.e. they feed a PT1 (first-order lag) filtered setpoint target. `tcc_setpoint_tab2` (0x1A1BB0, tab2 u32 indexed by slip/gear, reader 0xda67c) is the related lookup, Confidence LOW. These shape how quickly the commanded setpoint moves — effectively the smoothing applied to TCC transitions.

**Torque weighting and negative slip** — 2 members. Confidence HIGH. `tcc_pedal_weight_curve` (0x1A1984, u8 4 pt, x 0..255 pedal, z 0..100) is evaluated as `DAT_fff8a630=(p[1]*(float)u)/100.0` — a percent weighting applied to a torque, blending pedal position into the TCC torque calculation. `tcc_neg_slip_curve` (0x1A1978, s16 2 pt, x -500..-150, z -500..-300, 0.01 scale per the accumulate-then-/100 reader `tcc_neg_slip`) governs behaviour when slip goes negative (turbine overrunning the engine, i.e. coast/overrun).

**Torque and capacity maps** — 3 members. `tcc_output_torque_map` (0x19F8C4, s16 6x4, x 350..2500, y -50..400, z 50..400; MED, readers FUN_000dca5c/dcae0/dcb2c, varies across versions) maps operating point to a TCC torque quantity. `tcc_torque_capacity_drive_coast` (0x1A0F30, f32 8x2, x -50..600, y 0..1 (drive/coast flag), z 200..400; LOW) gives separate clutch torque capacity for drive vs coast. `tc_torque_ratio_curve` (0x19A864, s16 6 pt, x 0..920, z 991..1865; LOW, reader FUN_000b9d10) is a second torque-ratio curve, numerically similar to `tcmodel_mu_curve`.

**Pressure-filter input curves** — 3 members, 0x19F4B0–0x19F4E0, labelled by E→F transfer from `tcc_press_torque_calc` / `tcc_press_filter`. `tcc_curve_b69e` (s16 4 pt, x = RAM var fff8b69e 180..250, z 100..300; LOW), `tcc_curve_u8_48` (u8 2 pt, x 191..229, z 20..100; LOW), `tcc_curve_u16_50` (s16 4 pt, x 0..191, z 30..150; MED, cross-version variation). All feed the TCC pressure filter/torque calculation (reader FUN_000ddc1a / FUN_000dd8fa); exact physical meaning of the inputs was not proven.

**Temperature factors** — 2 members. Confidence LOW (both F object matches with block membership but no bound reader). `tcc_eng_temp_factor` (0x1A10B8, f32 2x2, x 1500..2500, y 30..50, z flat 1.0) is a temperature-dependent factor, unity in this calibration. `tcctemp_heat_coeff_map` (0x19E890, f32 4x4, x 600..4000, y 30..110, z 1.3..3) is, per its F-transferred name, a heat-generation coefficient map for the TCC thermal model — if that holds, it affects the TCU's estimate of clutch temperature (and therefore thermal protection behaviour), not the pressure command directly.

Coverage: Covers all 62 items in this group (22 families).
