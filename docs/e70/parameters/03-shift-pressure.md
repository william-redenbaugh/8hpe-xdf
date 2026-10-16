# Shift pressure (clutch pressure during shifts)

The 8HP performs clutch-to-clutch shifts: for every gear change one shift element (clutch/brake) is filled and brought up to torque capacity while another is released, in a sequence of internal phases (fill, torque handover, inertia/sync, ramp-out). This group — 420 tables — holds the pressures applied to the oncoming and offgoing elements during those phases, the torque-dependent pressure adders, the phase durations, the ramp slopes into and out of each phase, and the oil-temperature corrections on all of the above. Together they determine how firm, how fast and how smooth each individual shift is: more pressure or steeper ramps give faster, harder torque handover (and more holding capacity at high input torque); less gives softer shifts at the cost of slip and heat during the shift.

Almost everything here is replicated along three dimensions, and the XDF names encode them: `up`/`dn` is the shift direction; `_XtoY` (or `X>Y` in grouped tables) is the gear change; `_c0`/`_c1`/`_c2` is a class index — the RE notes describe the underlying pointer tables as "class 0 pair 1to2" etc., so these are per-class copies of the same parameter (the physical meaning of the classes is not proven by the RE evidence); `phN` is the internal shift-phase number; and the `b_` prefix marks the "base" parameter set as opposed to the phase/torque set. Many small per-gear-pair copies are emitted as one grouped XDF table whose columns are the copies ("blocks", e.g. `(c0 1>2 .. c0 3>4)`); where the breakpoints differ per block, a companion `... axis` table holds each block's breakpoints. All values are big-endian s16/u16/u8 raw table values; for most tables the RE evidence establishes the reader and the table structure but explicitly notes "unit not proven" — raw value ranges are given below instead of physical units, except where the notes prove a unit. Confidence is MED for most families (byte-identical or value-matched objects against a labelled reference 'F' build, plus reader evidence); the few HIGH and LOW families are marked.

### Shift pressure: upshift base (b_up)

51 items, 8 families. The base (`b_`) upshift set: per gear pair (1>2 … 7>8) and class, the base pressure as a function of torque plus phase-2/3/4 corrections and oil-temperature offsets. Readers are the shift-execution functions around FUN_000e1404/FUN_000e2c3e; most tables sit in the banked 28-slot upshift block (pointer table 0x4f560).

| Family | Members | Address range | Shape/type | Axes (as given) | Confidence |
|---|---|---|---|---|---|
| **shift_press_b_up_press_torque** | 5 (grouped per class/pair + axis + `_c#_XtoY`) | 0x1B5008–0x1B6280 | 8-pt curves (s16) | x: torque-like breakpoints (−40..600); z raw 300..12750 | MED |
| **shift_press_b_up_press_ofs** | 1 (7 blocks, 1>2 … 7>8) | 0x1B22B0 | 7×4 curve set (s16) | x: −50..400; z: 0 in this calibration | MED |
| **shift_press_b_up_oiltemp_press_ofs** (+ axis) | 7 | 0x1B4F8C–0x1B5B32 | 3-pt curves per block (s16) | x: oil temp 35..150; z: −10..0 | MED |
| **shift_press_b_up_ph2_end_ofs** | 18 (`_c0/_c1/_c2`, pairs 1>2 … 7>8) | 0x1B5040–0x1B62A8 | 8×8 maps (u8) | x: ~14..126, y: 0..190; z raw ~78..136 | MED |
| **shift_press_b_up_ph3_time_ofs** | 7 (`_c0/_c2`, pairs 3>4 … 7>8) | 0x1B50A8–0x1B6028 | 8×8 maps (u8) | x: ~29..109, y: 10..160; z raw ~58..133 | MED |
| **shift_press_b_up_ph3_time_grad_ofs** (+ axis) | 6 | 0x1B4EFC–0x1B5AA4 | 4-pt curves per block (s16) | x: −300..200 (gradient-like); z: 0..100 | MED |
| **shift_press_b_up_ph4_trq_add** | 5 (pairs 1>2, 2>3, 3>4, 5>6, 7>8) | 0x1B6324–0x1B67EC | 8×10 maps (s16) | x: ~31..194, y: torque-like −102..552; z: 0..700 | MED |
| **shift_press_b_up_sync_time_thr** (+ axis) | 2 (7 blocks, 1>2 … 7>8) | 0x1B2294–0x1B229C | 7×4 curve set (s16) | x: −48..102; z: 0 in this calibration | MED |

What they do: `press_torque` is the base pressure curve versus a torque-like input for the shifting element — the first-order "how hard is this upshift" table. The `ph2_end_ofs` / `ph3_time_ofs` / `ph3_time_grad_ofs` maps trim the end pressure of phase 2 and the duration of phase 3 (handover/inertia phases) as a function of operating point; `ph4_trq_add` adds pressure in phase 4 proportional to input torque. `oiltemp_press_ofs` subtracts a small pressure at low oil temperature, and `sync_time_thr` is a synchronisation-time threshold curve (zero-valued here, as is `press_ofs`). Raising `press_torque` or `ph4_trq_add` values firms up the upshift at the corresponding torque; the exact physical unit of the pressure values is not proven by the RE evidence.

### Shift pressure: upshift phases / torque

60 items, 14 families. The phase/torque upshift set, mostly members of the banked 28-block upshift pointer table 0x50d20 and the 7-block table 0x51038, read by the shift-execution chain FUN_000e374a/FUN_000e40aa. This is where the best-understood timing evidence lives: phase durations are u8 values in control cycles, scaled by an oil-temperature percent factor.

| Family | Members | Address range | Shape/type | Axes (as given) | Confidence |
|---|---|---|---|---|---|
| **shift_press_up_trq_press** | 3 (`_c0/_c1`, pairs 1>2, 3>4) | 0x1BE25C–0x1BF090 | 8×10 maps (s16) | x: turbine speed, y: input torque; z: target clutch pressure, raw 200..6100 (the matching F-build object is labelled as clamping pressure in mbar) | MED |
| **shift_press_up_trq_add** | 13 (`_c0/_c1/_c2`, pairs 2>3 … 7>8) | 0x1BE374–0x1C0170 | 4×6 maps (s16) | x: turbine speed 1000..6500, y: torque −20..450 Nm-like; z: 0..1300 | MED |
| **shift_press_up_trq_add_alt** | 4 (pairs incl. 2>3 …) | 0x1C0EF8–0x1C1548 | 4×6 maps (s16) | as trq_add; z: 0..2100 | MED |
| **shift_press_up_alt** | 1 (c0 1>2) | 0x1BE1E0 | 4×6 map (s16) | x: turbine speed 0/150/1500/4500, y: torque index; "shape and use not yet traced" | MED |
| **shift_press_up_phN_time** (ph1, ph9, ph9_alt) | 21 | 0x1BE1A5–0x1C1754 | 10×3 / 4×4 maps, 10×1 curve (u8) | ph1: oil temp 0..180 × torque index, z = phase-1 duration in control cycles (12..45); ph9: torque index × turbine speed, z = phase-9 duration before the oil-temp factor (30..50 for c0 1>2; other copies differ, e.g. the alt curve is 3..16) | MED (formula evidence) |
| **shift_press_up_oiltemp_pct** | 1 (1to2) | 0x1C0CD4 | 4×1 curve (u8) | x: oil temp 10/20/60/90; z: percent factor 100..150 | **HIGH** |
| **shift_press_up_phN_ramp** (ph10) | 3 | 0x1BE30C–0x1C029C | 6-pt curves per block (s16) | x: input torque Nm (−30..400); z: phase-10 ramp parameter | MED |
| **shift_press_up_phN_sync_time** (ph1, ph19) (+ axis) | 5 | 0x1BBE2C–0x1BBE9C | 4-pt curves per block (ph1 s16, ph19 u8) | ph1 x: −50..100; ph19 x: 26..51 | MED |
| **shift_press_up_sync_thresh** (+ axis) | 2 (c2, 1>2 … 7>8) | 0x1BF7A0–0x1BF7A4 | 7×4 curve set (u8) | x per block; z raw 117..122 | MED |
| **shift_press_up_ph4/ph13_trq_add** (+ axis) | 3 | 0x1C0FAC–0x1C0FD0 | 5×4 / 3×6 (s16) | torque-dependent phase-4 adder (blocks 3>4 … 7>8, z 0..25) and phase-13 adder (blocks 2>3 … 4>5, z 30..600) | MED |
| **shift_press_up_phase_cycle_curve** | 1 (1to2) | 0x1C0DB6 | 3×1 curve (s16) | x: phase cycles; z: pressure term (added in 0xe554c) | MED |
| **shift_press_up_shiftexec_add** | 1 (4to5) | 0x1C125E | 5×1 curve (s16) | x: 0..140; z: 50..100 | MED |
| **shift_press_up_start_press_temp** | 1 (blocks 3>4, 6>7) | 0x1C105C | 2×10 curve set (s16) | x: oil temp 10..150; z: 0..800 | MED |
| **shift_press_up_ph13_base** | 1 (6to7) | 0x1C15AA | 3×1 curve (s16) | x: 0..35; z raw 50..12750 | MED |

Key proven behaviour (keep these formulas): phase-1 upshift duration is read as `cal_map_u8(+4, oil temp, turb/32)`; phase-9 duration is `shift_press_ph9_time = cal_map_u8(+0x10, torque idx, turb/32) * cal_curve_u8(up7+8, oil temp)/100` — i.e. the HIGH-confidence `shift_press_up_oiltemp_pct` curve scales phase-9 (and feeds the upshift pressure-offset accumulator) by 100–150 % depending on oil temperature — up to +50 %. The `trq_add` maps are the main torque-dependent pressure adders for upshifts: increasing them raises oncoming-clutch pressure with input torque and turbine speed, which shortens slip time under load. Durations are in control cycles (u8); shortening phase times quickens shifts but reduces the time available for a clean handover.

### Shift pressure: downshift base (b_dn)

142 items, 14 families. The base (`b_`) downshift set: full base-pressure maps per class, torque-dependent pressure maps per class and gear pair (including skip-shifts such as 5>1, 8>4), and the phase-10/11/12/13/15 adders, timers and ramps. Readers are FUN_000e1404/FUN_000e197a/FUN_000e256e/FUN_000e2a78/FUN_000e2e40 via banked pointer tables (0x4f154, 0x4fe78, 0x50218, 0x4f740).

| Family | Members | Address range | Shape/type | Axes (as given) | Confidence |
|---|---|---|---|---|---|
| **shift_press_b_dn_press_cls0–2** | 10 (classes 0–2, direct pairs 2>1 … 7>6) | 0x1B2480–0x1B3FB0 | 8×10 maps (s16) | x: 1..194, y: torque-like −102..600; z raw 0..6700 | MED |
| **shift_press_b_dn_press_alt_cls0/1** | 4 (alternate copies, e.g. 3>2, 5>4) | 0x1B2AC0–0x1B3B08 | 8×10 maps (s16) | as above; z raw 0..6500 | MED |
| **shift_press_b_dn_press_ofs** (+ axis) | 4 | 0x1B2E94–0x1B3C80 | 4-pt curves per block (s16) | small per-pair pressure offset | MED |
| **shift_press_b_dn_trq_press** | 35 (`_c0/_c1/_c2`, 16 gear pairs incl. skip-shifts 3>1 … 8>2) | 0x1B6930–0x1BB160 | 8×10 maps (s16) | x: 0..194, y: torque −102..600; z raw 0..7550 | MED |
| **shift_press_b_dn_ph10_press_add** | 11 (`_c0/_c1/_c2`, direct pairs) | 0x1B6898–0x1BABA0 | 4×1 curves (s16) | x: 26..144; z raw 0..3000 | **LOW/MED** |
| **shift_press_b_dn_ph11_time** | 13 (`_c0/_c1/_c2`) | 0x1B68A8–0x1BA9F8 | 4×1 curves (u8) | x: ~17..117; z: 0..18 (time values) | MED |
| **shift_press_b_dn_phN_ramp** (ph12, ph15) | 23 (per pair, incl. `_alt` and element-variant "e1" blocks and odd-suffix copies) | 0x1B2EB4–0x1BBCDC | 6-pt curves (s16), some grouped 2×6/3×6 | ph12: x −50..400 (torque-like), z −25..−2; ph15: x −100..600, z −1000..0 (negative release slopes) | MED |
| **shift_press_b_dn_ph13_ramp_add** | 19 (`_c0/_c1/_c2`, 11 pairs) | 0x1B6BB4–0x1BAB4C | 6×6 maps (s16) | x: 1..194, y: torque −102..500; z: 0..700 | MED |
| **shift_press_b_dn_ph15_rampout_time** (+ axis) | 7 | 0x1B6B8C–0x1BA0D8 | 4-pt curves (u8) | x: ~30..68; z: 15..40 (time values) | **HIGH** |
| **shift_press_b_dn_ph12_sync_time** | 1 (c0 4>3) | 0x1B6C50 | 4×1 curve | sync-time curve | HIGH |
| **shift_press_b_dn_sync_time_thr** (+ `_alt`) | 7 (direct pairs) | 0x1B2438–0x1B3D04 | 4×1 curves (s16) | x: −48..450; z: −25..−10 | MED |
| **shift_press_b_dn_outgrad_add** | 3 (grouped: 10+2+2 blocks, direct + skip pairs) | 0x1BB280–0x1BBC80 | 4-pt curves per block (s16) | x: output-gradient −450..−80; z: 0 here | MED |
| **shift_press_b_dn_ph13_add_temp_pct** (+ axis) | 3 (9+8 blocks) | 0x1BB2A8–0x1BB8EC | 4-pt curves per block (u8) | x: 0..190; z: 100 % here | MED |
| **shift_press_b_dn_adapt_temp_ofs** | 2 (blocks 3>2/4>3/5>4, plus 10 skip-pair blocks) | 0x1BB3A0–0x1BB800 | 10-pt curves per block (s16) | x: oil temp 10..150; z: −400..0 (direct pairs), flat 100 (skip pairs) | MED |

What they do: `press_cls0` and `trq_press` are the big base-pressure maps for downshifts — pressure over an operating-point grid with a torque-like y axis, covering every direct and skip downshift the box can perform (many members carry cross-version evidence: their values vary between calibration versions). The phase families then shape the shift: `ph10_press_add` adds pressure in phase 10 (meaning LOW confidence — matched by name against the F build only), `ph11_time` sets a phase-11 duration, `ph12/ph15 ramp` curves set negative pressure slopes (release ramps) versus torque, `ph13_ramp_add` adds a torque-dependent ramp amount, and the HIGH-confidence `ph15_rampout_time` sets how long pressure ramps out at the end of the shift. `adapt_temp_ofs` applies an oil-temperature-dependent offset tied to adaptation (negative for the direct 3>2/4>3/5>4 blocks, flat 100 for the skip-pair blocks); `outgrad_add` keys on a (negative) output gradient — i.e. deceleration-dependent — and `add_temp_pct` is a percent trim (100 % in this calibration). Firmer, faster coast/kickdown downshifts come mainly from the `trq_press`/`press_cls` maps and shorter `ph11`/`ph15` times; the ramp curves control how abruptly the offgoing element lets go.

### Shift pressure: downshift phases / torque

153 items, 20 families. The phase/torque downshift set — the downshift mirror of the upshift phase block, read through pointer tables 0x503f8, 0x515d8, 0x51b28, 0x51038 by FUN_000e374a/FUN_000e3f52/FUN_000e4f60/FUN_000e561c/FUN_000e5936.

| Family | Members | Address range | Shape/type | Axes (as given) | Confidence |
|---|---|---|---|---|---|
| **shift_press_dn_trq_press** | 24 (`_c0/_c1/_c2`, 11+ pairs incl. skip-shifts) | 0x1C1828–0x1C53BC | 8×8 maps (s16) | x: 0..194, y: torque −102..450; z raw 0..1000 | MED |
| **shift_press_dn_trq_press_b** | 9 (direct + skip pairs 3>2 … 8>7) | 0x1C58E8–0x1C7468 | 8×8 maps (s16) | as above; z raw 50..1050 | MED |
| **shift_press_dn_trq_add** | 31 (`_c0/_c1/_c2`, 11 pairs) | 0x1C1944–0x1C54D8 | 4×6 maps (s16) | x: turbine speed 992..5504, y: torque −102..400; z: 0..500 | MED |
| **shift_press_dn_ph11_press_add** | 25 (`_c0/_c1/_c2`, 15 pairs) | 0x1C1BB0–0x1C55D0 | 6×6 maps (s16) | x: 0..194, y: torque −102..500; z: 0..900 | MED |
| **shift_press_dn_ph9_time** (+ axis) | 6 (grouped 3/16/7-block class sets + axis + single) | 0x1C1924–0x1C54B8 | 4-pt curves per block (u8) | x: 17..42; z: phase-9 duration 8..40 | **HIGH** |
| **shift_press_dn_ph1/ph4/ph12_sync_time** (+ axis) | 9 | 0x1BBF0C–0x1C4798 | 4-pt curves (ph1 s16, ph4/ph12 u8) | ph1: x −12..100, z −25..0; ph4/ph12: x 20..120, z raw ~112..128 | MED/HIGH |
| **shift_press_dn_skip_ph1/ph4_sync_time** (+ axis) | 4 (blocks 3>2, 5>4, 7>6, 8>7) | 0x1BBF58–0x1BC0A0 | 4-pt curves (ph1 s16, ph4 u8) | ph1 z: −100..0; ph4 z raw ~113..128 (skip-shift variant) | MED |
| **shift_press_dn_ph5_base** | 3 (5>4 ×2, 8>6) | 0x1C0D34–0x1C73A0 | 10×1 curves (s16) | x: oil temp 10..150; z: 200..1000 | MED |
| **shift_press_dn_ph9_base_ofs** | 6 (incl. 5>1) | 0x1AE4B4–0x1C7374 | 10×1 curves (s16) | x: oil temp 10..150; z: 0..1050 | MED |
| **shift_press_dn_ph13_ramp** (+ axis) | 3 | 0x1C5680–0x1C628E | 3-pt curves (s16) | phase-13 ramp | MED |
| **shift_press_dn_ph10_ramp_rate** (+ axis) | 6 | 0x1C56A4–0x1C67E0 | 6-pt curves per block (s16) | x: −100..500 | MED |
| **shift_press_dn_ph10_ramp_rate_b** | 5 (3>2 … 8>6) | 0x1C5884–0x1C7404 | 6×1 curves (s16) | x: −100..500; z: 2..20 | MED |
| **shift_press_dn_ramp_grad** (+ axis) | 4 (blocks 2>1, 3>2; 3>1 … 5>1) | 0x1C56DC–0x1C62F0 | 6-pt curves per block (s16) | x: −40..200; z: 10..1000 | MED |
| **shift_press_dn_ramp_sync_time** | 1 (blocks 2>1, 6>5) | 0x1C57B8 | 2×4 curve set | sync-time | MED |
| **shift_press_dn_ramp_sync_time_b** | 7 (3>2, 4>2, 5>3, 7>1) | 0x1C5984–0x1C734C | 4×4 maps (u8) | x: 27..125, y: 47..188; z raw ~121..123 | MED |
| **shift_press_dn_outgrad_add** | 5 (2>1, 4>3, 5>4 + 8×8 variants) | 0x1C5698–0x1C67C8 | 4×1 curves / 8×8 maps (s16) | x: output gradient −500..−30; z: 0 here in the 4×1 curves (the 8×8 variant is a pressure-adder map) | MED |
| **shift_press_dn_oiltemp_curve** | 1 (2to1) | 0x1C563C | 10×1 curve (u8) | x: oil temp | MED |
| **shift_press_dn_temp_curve** | 1 (2to1) | 0x1C17B0 | 4×1 curve (u8) | x: torque index 17..51; z: percent 20..25 | **LOW** |
| **shift_press_dn_grad_map / grad_map2** | 2 (2to1) | 0x1C17D0–0x1C18C8 | 4×6 / 6×6 maps (u16) | x: speed-gradient quantity | **LOW** |
| **shift_press_alt_dn** | 1 (2to1) | 0x1BBF20 | 4×1 parameter set | members +4/+8/+0xc/+0x10 of table 0x503f8 block | MED |

What they do: `trq_press`/`trq_press_b` and `trq_add` are the downshift torque→pressure maps and turbine-speed/torque adders — the downshift counterparts of the upshift `trq_add` family and the main levers for downshift firmness under load. `ph11_press_add` adds pressure during phase 11 over an operating-point grid. The HIGH-confidence `ph9_time` blocks set phase-9 duration per class and gear pair (reader FUN_000e3f52 via the banked block, same mechanism as the upshift phase-9 time); the `sync_time` and `skip_..._sync_time` curves trim synchronisation timing for normal and skip downshifts. The `ph5_base` and `ph9_base_ofs` oil-temp curves set temperature-dependent base pressures/offsets for those phases; `ramp_rate`, `ramp_grad` and `ramp_sync_time` shape the pressure ramps and their timing; `outgrad_add` again keys on output-speed gradient (deceleration). `temp_curve` and the two `grad_map`s are LOW confidence — structurally identified members of the downshift 43-block table whose use is only partially traced.

### Shift pressure: other

13 items, 4 families. Torque-limit and temperature/torque support tables used by the shift logic.

| Family | Members | Address range | Shape/type | What it does | Confidence |
|---|---|---|---|---|---|
| **shift_torque_limit_class0–3 + fallback** | 5 | 0x1CEE96–0x1CEFFE (stride 0x5A) | 9 gears × 5 slots, u16 | Torque limits read by FUN_0012ec10 as `*(u16*)(class_base + (gear*5 + column)*2)`; row = gear 0..8, column = class slot 0..4. The known XHP flash rewrites classes 1–3 entirely to 5000 and rewrites class 0 (37 of 90 bytes) and the fallback (33 of 90) partially — i.e. this is the "torque limit removal" area. | MED |
| **shift_torque_temp_map_set3/5/8** | 3 | 0x1B0B58–0x1B0D9C | 6×4 maps (s16) | x: ±2000, y: temp 30..100; z: ±4000 — torque/temperature map set read by FUN_000dfeb8 | MED |
| **shift_temp_curve_cb3c** (two curve pairs + per-set singles) | 4 | 0x1B0B20–0x1B0D78 | 4-pt curves per set (s16) | temperature curves (x 0..90) in the same banked set-indexed block as the torque_temp maps | MED |
| **shiftpt_curve_fa2** | 1 | 0x1CE198 | 5×1 curve (u16) | x: 0..50; z: 1000..5000 — meaning not analysed beyond reader FUN_0011e95a | LOW |

### Unlabelled: Shift pressure

| Family | Members | Address | Shape/type | What it does | Confidence |
|---|---|---|---|---|---|
| **auto_shift_torque_curve_1af8e4** | 1 | 0x1AF8F0 | 4×1 curve (s16) | Auto-detected structure (x 0..400, z flat 1300), read by `shift_torque_curve`; meaning not analysed | LOW |

Coverage: Covers all 420 items in this group (61 families).
