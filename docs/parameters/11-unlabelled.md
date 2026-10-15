# Unlabelled auto-detected structures

This is the largest group in the XDF: **2,461 tables** (no constants or patches) that the static
scanner `e_calscan.py` found by recognizing the TCU's standard calibration-structure layouts in
the flash image, but whose *meaning has not been analysed*. Every single item in this group is
**Confidence LOW**, carries the note "Meaning not analysed", has no units on any axis, and — with
one exception noted below — "Read by: unknown" (no code reference has been traced to it yet). They
are included so the full calibration area is visible and diffable in TunerPro, not because they
are understood.

Why they exist at all: the Bosch ITCU2 firmware accesses almost all of its calibration through a
small set of generic interpolation helpers (1-D curve lookup, 2-D map lookup, and the
transmission-model variants). Each helper expects a fixed on-flash record: a short header with the
axis breakpoints, followed by the output (z) data. The scanner walks the calibration block
(0x180200–0x1FFFFF) and flags every byte run that matches one of those record layouts with
plausible, monotonic axis values. Statistically, these unlabelled records are the long tail of the
same subsystems documented elsewhere in this XDF — shift-schedule details, clutch pressure/fill
shaping, torque-converter slip control, thermal and adaptation models — but *which* record belongs
to *which* function is exactly what has not been established. **Treat the entire group as
read-only reference: do not edit any of these tables.** A wrong guess here can change clutch
pressures or model behaviour with no way to predict the effect, and none of these items has been
validated against a running transmission.

### How to read these entries (applies to every item in this group)

* **Title** `auto_<hex>` — the flash address of the *start of the structure* (its embedded axis
  header). Example: `auto_1a1a40` starts at 0x1A1A40 (file offset +0x21840 in the 2 MB image;
  the description always gives both). Ten items in the group carry a provisional descriptive
  name instead (`shift_press_map_b2`…`b9`, `shift_torque_headroom_mode1_curve`,
  `shiftexec_dn_blip_map_6x10`) — those names are working hypotheses only: the items are just as
  LOW-confidence and "Meaning not analysed" as the rest, and their structure address is in the
  description's leading `@0x…`.
* **XDF address** — points at the z-data block *inside* the structure, i.e. 6–72 bytes past the
  structure address, because the axis breakpoints sit in the header before the data. TunerPro
  shows the axes from that header; do not be surprised that the two addresses differ.
* **Evidence string** — e.g. `cal_curve_s16 7x1, x -10..200, z 0..250`: the helper layout that
  matched, the detected shape, and the *raw* (unscaled) min..max of each axis and of the data.
  No scaling factors are known for these items, so values display as raw integers/floats.
* **`Read by:`** — the firmware function(s) found referencing the structure. For 2,460 of the
  2,461 items this is "unknown". The single exception is `auto_191394` (s16 map 10x8 @0x191394),
  which is read by `FUN_000f4ba6` and `FUN_000f7530` — still unanalysed, but it is the one item
  in this group with a confirmed code path.
* **Helper name** (`cal_curve_*`, `cal_map_*`, `mdl_*`, `e_hdr_*`) — which record layout matched.
  `cal_*` are the ordinary calibration curve/map layouts; `mdl_*` are the transmission-model
  table layout (for model maps, rows = x input, columns = y input, as the descriptions note);
  `e_hdr_*` is a header-style variant of the same curve/map records (5 items total, spread across
  the s16/u8 categories below).

**Where they live:** the group spans flash 0x1902E4–0x1D3CEC — the middle of the calibration
block. Density by 32 KB region, to give a feel for the clustering:

| Region | Items | | Region | Items |
|---|---|---|---|---|
| 0x190000–0x197FFF | 79 | | 0x1B8000–0x1BFFFF | 482 |
| 0x198000–0x19FFFF | 183 | | 0x1C0000–0x1C7FFF | 358 |
| 0x1A0000–0x1A7FFF | 317 | | 0x1C8000–0x1CFFFF | 101 |
| 0x1A8000–0x1AFFFF | 497 | | 0x1D0000–0x1D3FFF | 11 |
| 0x1B0000–0x1B7FFF | 433 | | | |

In the dense 0x1A8000–0x1C8000 band, many same-shape records recur at regular address strides —
the pattern one would expect from per-gear-pair / per-drive-program repetition, which is typical
of 8HP shift and pressure calibration — but that reading is an inference from the addresses and
shapes alone, and no individual assignment is claimed.

### Unlabelled: s16 curves

**Family: `cal_curve_s16` auto-detected curves** — 731 members, 0x190920–0x1D3984. 1-D curves
(signed 16-bit data over a signed 16-bit breakpoint axis), shapes 2x1 to 12x1; most common 6x1
(162), 4x1 (157), 2x1 (111), 10x1 (105), 3x1 (95), 8x1 (75). Signed 16-bit is the TCU's workhorse
format for physical quantities (torques, pressures, temperatures, speed differences), so this
family plausibly holds interpolation curves for pressure/torque shaping, temperature
corrections and similar — but no individual meaning is analysed. Axes/units unknown; raw values
only. Confidence LOW. Do not edit.

**Family: `e_hdr_curve_s16` header-variant curves** — 2 members (`auto_19f23c`, 3x1 @0x19F23C;
`auto_191394`-adjacent `auto_191474`, 19x1 @0x191474). Same idea, alternate header layout; the
19-point curve is the longest curve in the whole group. Confidence LOW. Do not edit.

### Unlabelled: u8 curves

**Family: `cal_curve_u8` auto-detected curves** — 570 members, 0x1916A4–0x1CC784. 1-D curves with
unsigned 8-bit data, dominated by small shapes: 4x1 (347), 3x1 (98), 6x1 (93). u8 data in this
TCU is typical for enumerations, small factors, counters and percent-like quantities; many of
these may be selection/blend curves rather than physical tables. Meaning not analysed; raw
values only. Confidence LOW. Do not edit.

**Family: `e_hdr_curve_u8` header-variant curve** — 1 member (`auto_1d35f0`, 2x1 @0x1D35F0, raw
z = 0..0). Confidence LOW. Do not edit.

### Unlabelled: s16 maps

**Family: `cal_map_s16` auto-detected maps** — 536 members, 0x191394–0x1C8DC0. 2-D maps with
signed 16-bit data; common shapes 4x4 (150), 8x10 (69), 8x4 (68), 6x6 (64), 4x6 (42), 6x4 (38),
5x5 (37), 8x8 (28). The 8x10 and 8x8 shapes match the size class of the labelled shift-schedule
and pressure maps elsewhere in this XDF, and the many same-shape records at regular address
strides look like per-gear-pair / per-character repetition — but none is assigned. This family
includes the group's only item with traced readers: `auto_191394` (10x8 @0x191394, read by
`FUN_000f4ba6` and `FUN_000f7530`, raw z = 0..0 in this calibration). It also contains the eight
provisionally named `shift_press_map_b2`…`shift_press_map_b9` (all 6x3, consecutive at
0x1C7554–0x1C7714, raw z spanning 3500..19000) — the name is a hypothesis from their stride and
value pattern only; they remain LOW confidence, "Read by: unknown". Confidence LOW. Do not edit.

**Family: `e_hdr_map_s16` header-variant map** — 1 member (`auto_1943e8`, 4x4 @0x1943E8).
Confidence LOW. Do not edit.

### Unlabelled: u8 maps

**Family: `cal_map_u8` auto-detected maps** — 409 members, 0x19A128–0x1C74F4. 2-D maps with
unsigned 8-bit data; common shapes 4x4 (185), 4x6 (106), 6x6 (45), 6x10 (29), 10x3 (27),
8x8 (17). Plausibly small correction/selection surfaces (the u8 range caps raw values at 255).
One member carries the provisional name `shiftexec_dn_blip_map_6x10` (6x10 @0x1AC218) — a naming
hypothesis only, still LOW confidence and "Read by: unknown". Meaning not analysed. Confidence
LOW. Do not edit.

**Family: `e_hdr_map_u8` header-variant map** — 1 member (`auto_1902e4`, 2x3 @0x1902E4, raw
z = 0..0) — the lowest-addressed item in the group. Confidence LOW. Do not edit.

### Unlabelled: f32 maps

**Family: `cal_map_f32` auto-detected float maps** — 124 members, in a tight band
0x19ADE8–0x1A34F0. 2-D maps with 32-bit float data; shapes 6x6 (52), 4x6 (39), 4x4 (15), 8x6 (6)
and a few others. Floating-point calibration is unusual on this platform and the whole family is
packed into one ~34 KB region, which suggests a single coherent subsystem (e.g. a physical model
computed in float). Representative detected ranges are physical-looking (e.g. x -150..150,
y -240..240, z 0.01..0.5), but no meaning or units are established. Confidence LOW. Do not edit.

### Unlabelled: f32 curves

**Family: `cal_curve_f32` auto-detected float curves** — 4 members, 0x19ABC0–0x19E5D8 (two 4x1,
two 6x1), sitting at the edge of the same float band as the f32 maps. Confidence LOW. Do not edit.

### Unlabelled: u16 curves

**Family: `cal_curve_u16` auto-detected curves** — 3 members, 0x1A3390–0x1CB784 (two 2x1, one
10x1), unsigned 16-bit data. Confidence LOW. Do not edit.

### Unlabelled: model u16 curves

**Family: `mdl_curve_u16_u16` model curves** — 39 members, and **family: `mdl_curve_s16_u16`
model curves** — 5 members; together 44 items, 0x190D48–0x1D39CC. These use the transmission-model
curve record (`mdl_*` helper layouts: u16 or s16 breakpoint axis, u16 data); shapes 2x1–10x1,
mostly 5x1 (20). The model table layout is the one the TCU's internal plant/estimation models
read, as opposed to the ordinary `cal_*` lookups. One member carries the provisional name
`shift_torque_headroom_mode1_curve` (`mdl_curve_u16_u16` 5x1 @0x1CED58) — a naming hypothesis
only, still LOW confidence and "Read by: unknown". Meaning not analysed. Confidence LOW. Do not
edit.

### Unlabelled: model s16 curves

**Family: `mdl_curve_u16_s16` model curves** — 5 members, 0x191208–0x1CE9E8, all 5x1 (u16 axis,
s16 data; e.g. detected raw z -2000..-55 on `auto_1cb83c`). Confidence LOW. Do not edit.

### Unlabelled: model u16 maps

**Family: `mdl_map_u16_u16` model maps** — 30 members, 0x1961FC–0x1D3CEC; shapes 3x5 (15),
5x5 (10), 2x2 (3), 5x2, 4x4. These carry the explicit note "Model map layout: rows = x input,
columns = y input" — the display shape in TunerPro is the transpose of the helper's storage
order, so read the axes as the description states. Meaning not analysed. Confidence LOW. Do not
edit.

### Practical guidance

* **Do not edit anything in this group.** Nothing here has an analysed meaning, scaling, or a
  validated effect. Every documented, tunable parameter lives in the labelled sections of this
  XDF.
* These items are valuable as a **diff surface**: when comparing two calibrations (e.g. your ZB
  against another 8HP file), a change showing up inside one of these structures tells you the
  address and shape of what differs even before it has a name.
* If you reverse-engineer one of these (trace its `Read by:` function, find its scaling), that is
  exactly the evidence needed to promote it out of this group — the title's address is the
  structure start to look up in the firmware.

Coverage: Covers all 2461 items in this group (15 families).

See also: [educated guesses for every unlabelled item](12-unlabelled-guesses.md) — speculative subsystem and meaning hypotheses from address clustering and axis signatures.
