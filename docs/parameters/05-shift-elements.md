# Shift elements (clutch/brake fill and protection)

The 8HP has no bands or one-way clutches in the shift path: every gear change is a clutch-to-clutch handover between its five shift elements (brakes A/B and clutches C/D/E). For each engaging element the TCU runs a phase sequence — fast-fill the piston cavity, hold a low fill/kiss pressure, then ramp pressure through the torque-handover and inertia phases as a function of input torque. The tables in this group are the per-element building blocks of that sequence: fill times, base/fill pressures over elapsed phase time, pressure-from-torque characteristics, speed- and temperature-dependent corrections, timeouts, and element-protection (thermal/energy) limits that derate or abort abusive shifts.

Most families here are named `set0..set8`, many with several per-set copies present, and for the per-set items the RE evidence shows the same 9-slot reader (`FUN_000de8ac`, slot index k = 0..8, where k matches the set number) resolving them through a handful of per-family slot tables; the two `elemfill` copies are the exception, with no reader bound at all. The sets are therefore selected by one runtime index — plausibly per shift element or per shift situation — but the descriptions do not prove which, so treat the set meaning as unconfirmed and change sets one at a time while logging. Units are mostly raw table values ("unit not proven" in the RE notes); the pressure-like z ranges (150..12750) are consistent with mbar, and one table in this group is explicitly confirmed in mbar, but only that one is proven.

### Shift elements: fill / protection

**elem_fill_time_curve_set1** — 1 item, `0x1BC6A8`, 10x1 curve, s16. x: 10 pt (10..160), z: 10 pt (flat 300 in this calibration). Confidence **MED** (byte-identical to the F-build object `elem_fill_time_curve_set1`; read via the 9-slot reader at k=1, unit not proven). By its transferred name this is a fill-time characteristic: how long the fast-fill pulse runs for this element/set as a function of the x input. Shortening fill time risks an unfilled element (flare); lengthening it risks a bind/bump at engagement. In this calibration the curve is flat at 300, so there is no input dependence to exploit without adding one.

**elemfill_e1_range_t3_off** — 2 items (two copies: bank1 `0x1A3ADC`, bank0 `0x1A40C0`), 4x4 maps, s16. x: 4 pt (608..2496), y: 4 pt (-48..300), z: all zero in this calibration. Confidence **LOW** — membership in a calibration block is proven, but no reader reaches these copies; name comes from a byte-identical F-build object. Nominally an element-1 fill offset over a speed-like x and a temperature-like y input, active in some range/condition ("range_t3"). Both copies are zero here, so stock behaviour has no offset; given the LOW confidence and absent reader evidence, leave these alone.

**elemprot_scale_curve** — 1 item, `0x198214`, 4x1 curve, s16. x: element value (0..1000), z: % (flat 100). Confidence **HIGH** — the strongest-evidenced item in this group: E→F label transfer with byte-identical axes, and the decompiled reader shows exactly how it is used: `cal_curve_u16(DAT_fff849dc+0x50, param_2) -> sat_s16(param_3 + (u16*param_1[2])/100)` — i.e. the curve output is applied as a percent scale added to the input (kept exactly as the RE note gives it). This sits in the element-protection path (`elemprot_bc072`): it scales a protection quantity as a function of an element value. Stock it is flat at 100%, i.e. neutral. Raising it makes the scaled protection term larger, lowering it smaller — but the RE does not establish which direction tightens or relaxes the intervention, so do not change it casually; element protection is what keeps a slipping clutch from cooking itself.

### Shift elements: other

This category holds the per-set working tables of the engagement sequence. The `k4` / `ph4` / `ph16` / `ph11` fragments in the transferred names plausibly refer to a specific clutch (K4) and to phase numbers of the shift state machine (e.g. ph4 = a base-pressure phase, ph16/ph11 = later timed phases), but the descriptions do not prove that reading — take the phase/element attribution as naming evidence only.

**elem_a_launch_speed_press_map_set1** — 1 item, `0x1B4954`, 4x6 map, s16. x: 4 pt (1000..4000, speed-like), y: 6 pt (10..1000), z: 24 pt (-200..0). Confidence **MED** (byte-identical F object; read via the same 9-slot reader at k=1, through a different slot table than the `0x1BC1xx` region). By its transferred name, a launch-related pressure map for element "a" (plausibly brake A, which is applied in the launch gears): z is everywhere ≤ 0, so it behaves as a pressure reduction/offset over speed and the y input, not a main setpoint. Unit not proven.

**elem_k4_ph4_base_press (set0/2/4/6)** — 5 items, 10x1 curves, s16, `0x1BC330`–`0x1BD908` (set0 appears twice: `0x1BC330` at slot k=0 and `0x1BC6D4` at slot k=1). x: 10 pt (10..180), z: pressure-like (150..6000, unit not proven, mbar-consistent). Confidence **MED** (byte-identical F objects; 9-slot reader, k = set). Base pressure for a shift phase ("ph4") as a curve over a 10..180 input (a time- or torque-like quantity). This is the backbone of how hard the element is pressed in that phase: raising z firms the phase, lowering softens it. The large z-range differences between sets (set0 up to 6000 vs set2 topping at 400) show the sets cover very different operating situations — identify which set your target shift uses before editing.

| Member | Address | Shape | z range |
|---|---|---|---|
| set0 (slot k=0) | 0x1BC330 | 10x1 | 200..6000 |
| set0 copy (slot k=1) | 0x1BC6D4 | 10x1 | 200..6000 |
| set2 | 0x1BCA78 | 10x1 | 200..400 |
| set4 | 0x1BD1C0 | 10x1 | 150..1150 |
| set6 | 0x1BD908 | 10x1 | 200..1200 |

**elem_k4_ph16_time_press_curve (+ axis)** — 2 items (one block table `0x1BC9AE` holding 7 copies, set2..set8, plus its axis table `0x1BC9A8`), 7x3 layout, s16. Per block: x = time 3 pt (0..60), z = pressure-like 3 pt (0..12750). Confidence **MED**. A time→pressure ramp for phase "ph16": pressure as a function of elapsed time in the phase, with per-set breakpoints in the companion axis table (column = block/set, row = point — edit the axis there, not in the values table). This is the shape of a pressure ramp during a timed part of the shift; steeper = quicker torque transfer, harsher feel.

**elem_out_speed_curve_40 (+ axis)** — 2 items (block table `0x1BC284` with 8 copies set0..set7, axis `0x1BC27C`), 8x4, s16. Per block: x = 4 pt (20..4000, speed-like), z = 4 pt (0..10). Confidence **MED**. A small output-speed-dependent factor or offset used in the element sequence; z is a low-magnitude quantity (0..10), so this is a trim, not a main pressure. Meaning of the "_40" suffix is not resolved.

**elem_out_speed_curve_50 (+ axis)** — 2 items (block table `0x1BC2A4` with 9 copies set0..set8, axis `0x1BC29C`), 9x4, s16. Per block: x = 4 pt (0..4000), z = all zero in this calibration. Confidence **MED**. Sibling of the `_40` curve; zeroed stock, so it is inert here.

**elem_output_speed_corr_set1** — 1 item, `0x1BC804`, 2x1 curve, s16. x: 2 pt (10..30), z: 2 pt (-5..0). Confidence **MED**. A small negative correction over a 2-point input — a trim on an element quantity at low values of the input. Only set1 appears in this calibration region.

**elem_ph11_time_press_curve_set8** — 1 item, `0x1BE09A`, 3x1 curve, s16. x: time 3 pt (0..40), z: zero. Confidence **MED**. Same pattern as the ph16 time→pressure curves but for phase "ph11"; only the set8 copy is defined here and it is zeroed (inert stock).

**elem_press_curve_dc4_4c** — 1 item, `0x1ADECA`, 3x1 curve, s16. x: obj field 0..70, z: **0..12500 mbar** (the one explicitly unit-confirmed pressure table in this group). Confidence **LOW** on the name (E→F label transfer only), but it has a known reader: it feeds the element pressure setpoint path (`elem_press_setpoint` / `FUN_000df1cc`). A characteristic converting an internal element quantity to a pressure setpoint in mbar.

**elem_press_torque_map_70 (set1..set8)** — 8 items, 8x10 maps, s16, `0x1BC750`–`0x1BE0CC` (one per set, slot k = set). x: 8 pt (~6..219), y: torque-like 10 pt (~-102..552), z: pressure-like 80 pt (0..8050, unit not proven). Confidence **MED** (byte-identical or 90% value-match F objects; set6/set7 additionally shown to vary across 21 calibration versions, i.e. ZF actually tunes them per application). These are the main pressure-from-torque maps of the engagement: for a given x (likely a phase/ratio-related quantity) and input torque, they set the element pressure. This is where "holds the clutch at this torque" lives — raising z increases clamping for a given torque (crisper, more holding margin, harsher), lowering it softens the shift and increases slip. set8 is all zero in this calibration.

| Member | Address | z range |
|---|---|---|
| set1 | 0x1BC750 | 400..3300 |
| set2 | 0x1BCAF4 | 300..4000 |
| set3 | 0x1BCE98 | 300..6200 |
| set4 | 0x1BD23C | 200..6100 |
| set5 | 0x1BD5E0 | 750..8050 |
| set6 | 0x1BD984 | 650..8050 (varies across versions) |
| set7 | 0x1BDD28 | 750..7850 (varies across versions) |
| set8 | 0x1BE0CC | 0 (inert) |

**elem_press_torque_map (set0..set2)** — 3 items, 4x6 maps, s16, `0x1BC1A0`, `0x1BC544`, `0x1BC8E8`. x: 4 pt (-1000..2000, signed — plausibly a speed-difference/slip-like input), y: torque-like 6 pt (-50..400; set0 -25..400), z: 0..450 (low-magnitude, unit not proven). Confidence **MED**. A smaller companion to the `_70` maps — given the low z magnitude, likely a pressure correction/adder over slip and torque rather than the main setpoint.

**elem_ramp_press_curve_set8** — 1 item, `0x1BDE9E`, 3x1 curve, s16. x: 3 pt (100..200), z: zero. Confidence **MED**. A pressure-ramp characteristic; only the set8 copy is in this group and it is inert stock.

**elem_speed_offset_curve_set0** — 1 item, `0x1BC210`, 2x1 curve, s16. x: 2 pt (250..400), z: 2 pt (0..200). Confidence **MED**. A speed offset applied in the element sequence (e.g. a target-speed or threshold offset over an input in the 250..400 range).

**elem_temp_weight_curve (set2..set3 block + set8)** — 2 items, u8 curves: a block table at `0x1B4A16` holding set2 and set3, and a standalone set8 copy at `0x1B4E86`. x: temperature 6 pt (15..80), z: weighting 0..100 (set8 flat at 100). Confidence **MED**. A temperature weighting factor: blends or scales an element quantity (0–100%) as oil temperature rises from 15 to 80. This is how cold-oil behaviour is faded out — flattening it to 100 removes the cold-temperature blend for that set.

**elem_timeout_time_set0** — 1 item, `0x1AF900` (data @`0x1AF8F8`), 2x1 curve, s16. x: 2 pt (30..50), z: time-like 2 pt (250..400). Confidence **MED**. A timeout for an element sequence step: if the phase has not completed by this time, the TCU moves on or falls back. Lengthening timeouts can mask a fill problem instead of fixing it.

**elem_torque_curve_14 (set0..set2 block, axis, set6/set8 block)** — 3 items: values block `0x1BC16C` (set0..set2) with axis table `0x1BC164`, and a second block `0x1BD744` (set6, set8). Per block: x = torque-like 4 pt (-50..300), z = 4 pt (5..25 for set0..2; zero for set6/8). Confidence **MED**. A small torque-dependent characteristic (z magnitude 0..25) — a trim/threshold over input torque. Per-set breakpoints for the first block live in the companion axis table.

**elem_torque_curve_20 (+ axis)** — 2 items: values block `0x1BCCCC` holding 6 copies (set3..set8), axis `0x1BCCC0`. Per block: x = torque-like 6 pt (-50..400), z = 6 pt (20..40). Confidence **MED**. Same pattern as curve_14 at a different magnitude — a torque-dependent trim used by the element sequence.

**elem_torque_curve_24 (set0..set8)** — 10 items, 6x1 curves, s16, `0x1BC1FC`–`0x1BDF70`, one per set at slot k = set, with set8 present twice (`0x1BDF1C`, `0x1BDF70`). x: torque-like 6 pt (-50..500; -100..400 for set8), z: 6 pt (0..1000; set8 zero). Confidence **MED**. The most completely populated per-set family in the group: a torque→value characteristic (z up to 1000) evaluated per set — by magnitude plausibly a pressure or torque-share term in the handover. Address scheme: consecutive sets sit ~0x3A4 apart, mirroring the per-set layout of the whole `0x1BC1xx`–`0x1BE0xx` region (each set's tables are grouped in one ~0x3A4-byte block).

**elem_torque_press_max2_set5** — 1 item, `0x1BD458`, 6x1 curve, s16. x: torque-like 6 pt (-100..400), z: 6 pt (5..40). Confidence **MED**; notably it varies across 21 calibration versions (3 distinct value sets), so ZF tunes it per application. By name, a maximum-pressure (or pressure-limit) characteristic over torque for set5 — a ceiling on what the element pressure request may reach. Raising a max-limit without understanding the element's thermal budget defeats a protection.

### Unlabelled: Shift elements

**auto_elemprot_* (auto-detected protection curves)** — 3 items, s16 curves near the elemprot region, all Confidence **LOW** (structure auto-detected by the calibration scanner; meaning not analysed — only the reading function names are known):

| Parameter | Address | Shape | Detected ranges | Read by |
|---|---|---|---|---|
| auto_elemprot_bae90_19815c | 0x198166 (data @0x19815C) | 3x1 | x 15..35, z 100..500 | FUN_000b0a72, elemprot_bae90 |
| auto_elemprot_value_a_margin_198230 | 0x19823C (data @0x198230) | 4x1 | x 8..35, z 1..5000 | elemprot_value_a_margin |
| auto_elemprot_value_c_limit_19821c | 0x198228 (data @0x19821C) | 4x1 | x 4..35, z 1..5000 | elemprot_value_c_limit |

The reader names say these feed the element-protection value comparisons — a margin for quantity "a" and a limit for quantity "c" — with x ranges that look temperature-like (4..35). Together with `elemprot_scale_curve` above they form the tunable surface of element protection. Because their meaning is unanalysed, the safe stance is: read them to understand when protection intervenes, don't raise limits to "fix" a harsh or aborted shift — find the pressure/fill cause instead.

Coverage: Covers all 54 items in this group (22 families).
