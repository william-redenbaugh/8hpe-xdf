# Signals & diagnosis (speeds, torque, temperature, monitoring)

Before the 8HP TCU can decide when to shift or how hard to press a clutch, it has to turn raw inputs into usable internal signals. The engine reports its speed and an indicated torque over CAN, but the torque that actually reaches the transmission input shaft is smaller: the torque converter / pump, accessories and parasitic drag eat some of it, and the losses depend on gear, speed and oil temperature. This group holds the parameters of that input-signal conditioning layer — engine-speed-based signal corrections, the transmission loss (drag-torque) model with its hot/warm/cold variants, an idle-load model, tip-in (throttle step) evaluation curves in the torque model region, and a cold-oil pressure compensation curve. Downstream consumers — shift scheduling, clutch pressure calculation, TCC control — all work from the loss-corrected torque and conditioned speeds these tables produce, so errors here propagate everywhere: an overestimated loss means softer clutch pressures than the real torque demands, an underestimated one means harsher shifts.

The group also contains the single largest block of *unlabelled* items in the whole XDF: 123 calibration structures that were found purely by structural scanning (`e_calscan.py`) in the diagnosis/monitoring code region. Their shape, data type and reader functions are known, but their meaning has deliberately **not** been assigned. They are included so that the memory is accounted for and so a curious tuner can correlate them with logging — not because anyone should edit them.

A note on honesty: confidence in this group is mostly LOW. Only `trqloss_coolant_curve` is HIGH (its read-out code was decompiled and the percent-scaling formula recovered), and only the 27 gear-loss maps plus `trqloss_idle_load_map` are MED (byte-identical object matches against the reference 'F' build, in context with aligned neighbour runs). Everything else is a LOW-confidence identification — the name tells you the best current hypothesis, not a verified fact.

### Signals: speeds

Four small curves that condition speed-related signals before they feed the shift logic and torque model.

**sigcond engine-speed conditioning curves** — 2 members, 0x19A7A0–0x19A810, 6x1 s16 curves (`cal_curve_s16`), x axis = engine speed 500..7000 rpm. Both are read by the same function (FUN_000b9b1c), which places them in the signal-conditioning path keyed on engine rpm. Confidence LOW (byte-identical object match against the F build; `sigcond_trq_offset_engspd` additionally reader/function-corroborated).

| Parameter | Address | Shape | Axes | Values (stock range) | Best-guess role |
|---|---|---|---|---|---|
| `sigcond_shift_curve_0` | 0x19A7A0 | 6x1 s16 | x: rpm 500..7000 | z: -200..-20 | rpm-dependent signal correction used around shifting |
| `sigcond_trq_offset_engspd` | 0x19A810 | 6x1 s16 | x: rpm 500..7000 | z: -10..-10 (flat) | torque offset as a function of engine speed |

The flat -10 offset in `sigcond_trq_offset_engspd` suggests a constant torque bias subtracted from the reported engine torque; changing it would shift the torque signal every downstream consumer sees. Treat with care — the names are hypotheses.

**Engine-speed gradient compensation** — 1 member: `speed_eng_grad_comp_curve`, 0x19F818, 4x1 s16 curve, x: 1200..1800 (rpm-like), z: 31..46. Confidence LOW. Plausibly compensates a speed signal for its rate of change (gradient), e.g. to predict rpm slightly ahead during fast transients so shift decisions are not made on stale values. Read by FUN_000dc4da.

**Speed model curve** — 1 member: `speed_curve_d72c`, 0x1CE4A4, 5x1 (`mdl_curve_u16_s16`, 16-bit), x: 0..250 (an output-speed-like range), z: -10000..-250. Confidence LOW. It lives in the model (`mdl_*`) region at 0x1CE rather than the normal calibration area, i.e. it is part of an internal computation model rather than a driver-facing calibration. Read by FUN_00122a1a. Meaning beyond that is not established — do not edit.

### Signals: temperature / warm-up

**Cold-oil pressure compensation** — 1 member: `temp_cold_press_curve`, 0x1C8834, 4x1 s16 curve. x axis: oil temp, raw degC+40 encoding; z: 18500 (mbar?). Confidence LOW (E→F label transfer: the function labelled `temp_cold_press` reads this object; order-aligned, E/F axes byte-identical). The shape of the evidence — an oil-temperature input and a pressure-magnitude output — fits the classic cold-oil behaviour of an automatic: cold ATF is viscous, so the hydraulics need a pressure correction until the box warms up. If the identification is right, this curve sets that correction; raising it would stiffen cold operation, lowering it risks sluggish cold engagements. The `(mbar?)` in the unit is the RE author flagging that the pressure unit is unproven.

### Signals: torque / losses

This is the drag-torque / loss model: the TCU's estimate of how much of the engine's reported torque is lost before the gearsets, as a function of speeds, gear and temperature. The corrected torque drives clutch pressure targets, so these maps matter for shift quality — but note which ones are MED vs LOW confidence before touching anything.

**Per-gear drag-torque maps, hot/warm/cold** — 27 members: `trqloss_gear_map_{hot,warm,cold}_set0..set8`, 0x19A1BC–0x19A734 (one contiguous run), each 6x6 u8 (`cal_map_u8`). All 27 share the same axes: x = 6 pts 17..117, y = 6 pts 23..219 (speed-like breakpoints, exact units not proven); z values are small torque-loss numbers (roughly 0..18). Confidence MED — byte-identical object matches against the F build, with run-context alignment (e.g. 13 consecutive objects matched for the cold run) and, for some sets, index-resolved reader evidence (FUN_000b8a6e / FUN_000ac4a0).

Address scheme: the three temperature variants of each set are interleaved, 0x38 bytes apart, and consecutive sets are 0xA8 apart:

| Set | hot | warm | cold |
|---|---|---|---|
| set0 | 0x19A1BC | 0x19A1F4 | 0x19A22C |
| set1 | 0x19A264 | 0x19A29C | 0x19A2D4 |
| … | +0xA8 per set | +0xA8 per set | +0xA8 per set |
| set8 | 0x19A6FC | 0x19A734 | 0x19A76C |

Nine sets for a transmission with eight forward gears plus reverse is consistent with one loss map per operating gear (which gear maps to which set index is not proven — the reader evidence notes "slot not attributable" for some sets). The hot/warm/cold triplication is the temperature dimension of the loss model: cold oil drags more, so cold z values sit slightly above hot ones. Lowering these values tells the TCU less torque is being lost, i.e. a *higher* net input torque estimate, which generally raises computed clutch pressures; raising them does the opposite. Since the identification is MED, log before/after if you experiment.

**Idle / low-speed loss model** — 5 members, 0x199F04–0x19A0E0, read by FUN_000b85a6 / FUN_000b84c2. Models the drag torque around idle and creep, where converter losses dominate, with a coolant-temperature gate and an output-speed gradient dimension.

| Parameter | Address | Shape | Axes (stock ranges) | Confidence | Best-guess role |
|---|---|---|---|---|---|
| `trqloss_idle_load_map` | 0x199F04 | 8x12 s16 | x: 0..1200, y: 0..1200, z: 0..570 | MED | main idle-region loss/load map (rpm-like axes); cross-version evidence shows it is actually varied between calibrations |
| `trqloss_idle_outspd_curve` | 0x19A006 | 5x1 s16 | x: 64..550, z: 0..100 | LOW | loss factor vs output speed |
| `trqloss_idle_target_curve` | 0x19A0B4 | 6x1 s16 | x: 600..1200 (idle rpm range), z: 14..57 | LOW | idle-region loss target vs engine speed |
| `trqloss_idle_coolant_thr` | 0x19A08C | 4x1 u8 | x: 18..98 (coolant temp), z: 100..150 | LOW | coolant-temperature threshold/scale for the idle loss path |
| `trqloss_outspd_grad_map` | 0x19A0E0 | 6x6 s16 | x: 64..450, y: -800..100 (gradient), z: 0..100 | LOW | loss vs output speed and its gradient (decel/accel) |

**Coolant-temperature torque scaling** — 1 member: `trqloss_coolant_curve`, 0x199ECE, 6x1 u8 curve, x: coolant temp 18..123, z: percent (around 100). **Confidence HIGH** — the only HIGH item in this group. The decompiled reader shows exactly what it does: `cal_curve_u8(DAT_fff84a1c+0x0, oil_temp) -> sat_s16((u8*param_2)/100)` — a percent scale applied to the input torque. In plain terms: the curve output is a percentage, and the torque signal is multiplied by it (value/100), saturated to s16. At 100 it is transparent; values above/below 100 scale the TCU's torque estimate up/down with temperature. This is the one knob in this group whose mechanism is actually proven.

**Loss correction / blend curves** — 2 members. `trqloss_temp_curve_20` (0x19A01C, 4x1 s16, x: 0..80 temp-like, z: 100..140, read by FUN_000b8768) looks like another temperature-dependent percent-style correction on the loss path; `trqloss_blend_curve` (0x19A188, 4x1 s16, x: speed delta -50..50, z: blend 0..255, read by `trqloss_c8698`) looks like a 0..255 blend factor that cross-fades between two loss estimates as a function of a speed difference (e.g. converter slip). Both confidence LOW (E→F label transfer / object match only).

**Torque model tip-in evaluation** — 4 members, 0x1CBD4E–0x1CE5B8, in the model (`mdl_*`) object region, 16-bit. These sit in the torque-model code (readers FUN_001257d0 / FUN_00125b72 / FUN_00121b14) and, per their names, evaluate tip-in events — sudden throttle steps — which a TCU typically needs to classify so it can pick a downshift or firm up pressures. Note the `mdl_map` layout convention: rows = x input, columns = y input — and that for the two maps the RE description and the XDF axis fields assign x/y to the two inputs in opposite orders. The table below follows the XDF axis fields (consistent with the shape column); treat the x/y naming as a convention, not a proven input mapping. Confidence LOW throughout.

| Parameter | Address | Shape | Axes (stock ranges) | Best-guess role |
|---|---|---|---|---|
| `torque_tipin_eval_curve_1ddd84` | 0x1CBD4E | 3x5 mdl_map_u16_u16 | x: 100..500, y: 80..98, z: 70..100 | tip-in evaluation map (percent-like output) |
| `torque_tipin_speed_factor_map_1dddb4` | 0x1CBD82 | 5x5 mdl_map_s16_u16 | x: 700..1000, y: -20..40, z: 80..100 | speed-dependent tip-in factor |
| `torque_tipin_eval_curve_1e1516` | 0x1CE5B8 | 3x1 mdl_curve_u16_u16 | x: 50..500, z: 10..20 | tip-in evaluation curve |
| `torque_curve_e18` | 0x1CE33C | 3x1 mdl_curve_u16_u16 | x: 0..40, z: 1..1 (flat) | torque-model helper curve (flat at stock) |

### Unlabelled: Diagnosis / monitoring

**Auto-detected, unlabelled calibration structures** — 123 members, titled `auto_cal_{curve|map}_{f32|s16|u16|u8}_<address>`, scattered through 0x197094–0x1C8848. Every one of these was found by the structural scanner (`e_calscan.py`): the scan proves there is a well-formed calibration object there (a monotonic axis followed by a plausible data block, matching one of the standard `cal_curve_*`/`cal_map_*` helper layouts) and records which function reads it — but **"Meaning not analysed"** appears verbatim in every description. They were binned under diagnosis/monitoring because of where their reader functions live, not because any threshold has been identified. All are confidence LOW. The title encodes the detected data type and the flash address, so each item is self-locating.

Breakdown by detected structure:

| Pattern | Count | Typical shapes | Data type |
|---|---|---|---|
| `auto_cal_curve_s16_*` | 47 | 2x1..10x1 (two detected as 5x5) | 16-bit signed |
| `auto_cal_map_s16_*` | 22 | 3x2..12x5, up to 8x10 (one detected as 5x1) | 16-bit signed |
| `auto_cal_curve_u16_*` | 20 | 2x1..12x1 | 16-bit unsigned |
| `auto_cal_curve_u8_*` | 14 | 2x1..6x1 | 8-bit |
| `auto_cal_curve_f32_*` | 11 | 4x1..6x1 | 32-bit float |
| `auto_cal_map_u8_*` | 8 | 4x4..6x6 | 8-bit |
| `auto_cal_map_u16_*` | 1 | 3x3 | 16-bit |

Each item's description carries the scanner's detected axis and value ranges (e.g. `cal_curve_f32 4x1, x -20.0..90.0, z 0.4..0.5` — plausibly temperature-indexed; or `cal_map_s16 8x10, x 22..156, y -18..498, z 750..7850`) and its reader function(s) — most have exactly one reader, ten are read by several, and there are 86 distinct readers across the 123 items, so these span many small monitoring routines rather than one subsystem. In a diagnosis/monitoring region, structures like these are typically plausibility limits, debounce times, and fault thresholds: exactly the kind of parameter where an uninformed edit can silence a protection or set a false fault. **Do not edit these.** They are documented so the calibration area is fully mapped and so anyone extending the RE work knows where to start (the reader function is named for each one).

Coverage: Covers all 167 items in this group (10 families).
