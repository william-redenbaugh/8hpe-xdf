# Patches, Stage 3 map list & additional maps

This group is the "operational" part of the XDF: two one-click behaviour patches (`[PATCH] Start in 2nd`, `[PATCH] True manual`), the Radumfang wheel-circumference constant that every swap must set, a **stage 3** folder that collects, in one place, every map a stage-3 (XHP-style) tune touches, and an **Additional maps** folder with the leftover objects the tune edits that did not fit any proven subsystem. The stage 3 folder is deliberately redundant — most of its entries are the same flash objects that are documented in their own subsystem sections (shift lines, torque limits, downshift blip maps) or duplicated from Additional maps; it exists so you can walk one folder and see exactly where a commercial stage-3 calibration differs from stock.

A word on confidence before you edit anything here: this XDF was built by static reverse engineering, and each item carries a HIGH/MED/LOW rating. The shift-line tables are HIGH confidence (geometry verified against pointer tables in the image); the torque-limit and shift-type tables are MED (layout from the reader functions); a large share of the stage 3 / Additional maps entries are LOW — they are emitted so the tune's edits are *visible and editable*, but their row/column meaning is not proven. Treat LOW items as "this is what a stage-3 tune changes", not as maps you understand well enough to retune freely.

### Patches (click to apply)

TunerPro patches are pure overwrites: clicking "apply" writes fixed bytes at fixed addresses. There is no base-data restore, so **work on a copy of your stock read**. Both patches state the same required order:

> **APPLY ORDER: load/apply the Stage 3 maps first, then the patch as a pure overwrite (no basedata); recompute the CRC after all patches** (the declared CRC32 lives at 0x180244 — see `cal_declared_crc32` below).

**[PATCH] Start in 2nd** — 1 patch, 97 entries. Makes the box pull away and hold 2nd gear instead of 1st. What it writes, by revision (the description documents the on-car trail):

| Edit | Bytes | Effect |
|---|---|---|
| R1: zero the 1↔2 shift lines | 46 slots × 15 u16 BE = 1380 bytes: the 1>2 up line and the 2>1 down line (down = up + 0x1E) of **all 23 shift characteristics**, e.g. char00 at 0x1D0AB6/0x1D0AD4, char01 at 0x1CF922/0x1CF940 … char22 at 0x1CFB7A/0x1CFB98 | No 1↔2 shift line can ever trigger. On-car: still D1 at standstill — the strategy clamps the request |
| R2: inhibit bytes | 00 over 0x1D33D8 / 0x1D33E5 / 0x1D3419 (program/global byte 8) | No on-car change observed |
| R3: global inhibit vector | 00 ×13 over 0x1D3411..0x1D341D (mask/debd 0 everywhere); 0x1D341E stays stock | — |
| R4: min-gear floor byte | 01 over 0x1D3A4F (stock 02) | — |
| R5: floor off + availability (per e_work/notes/m1_floor_cal.md sec. 5) | 0x1D3A4F 01→02 (floor off, manual M1 back), 0x1CD938 0001→0002, and the 45 car-2nd min-speed words zeroed | Car 2nd becomes available at 0 speed, so the R1 request finally passes |

The lesson a tuner should take from the R1–R5 trail: zeroing shift lines alone does **not** force a 2nd-gear launch — the gear-availability/min-speed layer has to be opened up too, which is exactly what the later entries do.

**[PATCH] True manual** — 1 patch, 7 entries. Removes the TCU-side forced upshift at redline in manual mode; the DME rev limiter still protects the engine.

| Entry | Address | Write (stock) | What it does |
|---|---|---|---|
| overspeed_limit_1 / _2 | 0x1CECA4 / 0x1CECA6 | 0xFFFF (stock 7100 / 6825 rpm) | Kills guard test 1 in FUN_0012c9b8 (the escalation/forced-upshift test) |
| overspeed_margin_a / _b | 0x1D3A80 / 0x1D3A81 | 0xFF (stock 105) | df32 seeds — raises the test-2 margin |
| revmatch_latch_arm | 0x1D28EC | 0xFFFF (stock 6500 rpm) | Rev-match latch arm point |
| df31_gate_off | 0x1D34B1 | 00 (stock 02) | df31 gate threshold in FUN_0012c660; hinges on runtime def4 — **supervised test only** (the deterministic fix is a program patch at 0x12CA44/56, outside the calibration area) |
| strat_state_attr_3_01 | 0x1C927C, 0x64 bytes | fill 01 | The "K0 lever" (e_work/notes/tm_round5.md): attr_3[100]=01 → dd39≠0 → df31=1 → test-2 threshold (da9c×df32)/100 becomes 2.55× with df32=255, so the ~7200 rpm forced upshift cannot fire |

The description also records an R4 companion edit: the cap at 0x1CC03C raised 7200→10000 (test 2). Note the interaction with the stage 3 list: `escalation_test1_threshold` (0x1CECA4) appears there with the stage-3 value 7200 — this patch overwrites the same word with 0xFFFF, which is why the patch must be applied *after* the stage 3 maps.

**Radumfang — dynamic wheel circumference (mm)** — 1 constant, u16 at 0x195F10. The tyre's *rolling* circumference, not the geometric one. This is the one value every 8HP swap must set correctly, because the TCU derives the final-drive ratio from it.

- Formula (kept exactly as the XDF gives it): `pi x (rim_inch x 25.4 + 2 x width_mm x profile_pct/100) x 0.97`. Worked example: 225/45R17 = 1933 mm. If the tyre maker publishes a rolling circumference (Abrollumfang), use that directly.
- **After flashing**: reset the learned rear-axle value (Tool32 job `steuern_lernfkt_ruecksetzen`, argument 0) and drive above ~24 km/h so it re-learns. Then read `status_lernfkt`: the learned value must equal your real diff ratio. If it is one step off (e.g. 3.91 instead of 3.73), multiply your entry by (real ratio / learned value) and repeat.
- The TCU snaps to the closest entry of a fixed ratio list (2.00 2.35 2.47 2.56 2.65 2.81 2.93 3.08 3.15 3.23 3.38 3.46 3.64 3.73 3.91 4.10 4.27), so the entry only needs to land within about −1 % / +2.5 % of the reference.
- Do **not** use this to correct the speedometer — that is the DSC's coding.

### stage 3

108 items. This folder is the curated list of everything a stage-3 tune touches. By family (an entry marked *dup* is the same flash object as an item documented under Additional maps or in another section of this document):

**Shift lines (upshift/downshift blocks)** — 16 items, 0x1CF21A–0x1D175E. The core of any shift-point retune and the highest-confidence data in this group. Multi-column blocks of the schedule for characteristics 00, 01, 02 and 04 (of the 23 the TCU holds): `Upshift lines, char NN: 1>2..5>6` (5×15), plus separate 1×15 slots for 6>7 and 7>8; `Downshift lines, char NN: 2>1..6>5` (5×15) and `char 02: 7>6`. Axes: the 15 breakpoints are accelerator pedal in per mille (1100 = kickdown; live axes at 0x1CC1CC for upshift and 0x1CC20C for downshift blocks — the lone 6>7/7>8 slots reference further copies of the pedal axis, e.g. 0x1CC24C), the other dimension of a block is the gear pair; z = output-shaft speed in rpm at which the shift is requested; **8000 = shift disabled**. Each slot is 15 u16 (30 B) and the up/down slots of one gear pair alternate (down = up + 30 B, next pair at +60 B). The active characteristic is selected from the strategy state. Geometry verified against pointer tables 0x5A47C/0x5A984 in the image. Confidence **HIGH for the layout, MED for which characteristic is which** — so change a line, drive, and confirm which mode it affected before building a full schedule on it. Raising an upshift line holds gears longer at that pedal position; keeping down lines a safe margin below the corresponding up lines preserves shift-busyness hysteresis.

**Per-gear single shift curves** — 33 items, 15×1 views (`Upshift char 00: 1>2` … `Upshift char 04: 7>8`, `Downshift char 02: 2>1` … `7>6`), same addresses as slices of the blocks above. These exist for convenient single-curve editing in TunerPro; editing a 15×1 item and the matching gear-pair slot of its 5×15 parent edits the same bytes. Same units and confidence as the blocks.

**Shift torque-limit classes** — 5 items: `shift_torque_limit_fallback` 0x1CEE96, `shift_torque_limit_class0..3` at 0x1CEEF0/0x1CEF4A/0x1CEFA4/0x1CEFFE (family stride 0x5A). Each a 9×5 u16 matrix, row = gear 0..8, column = class slot 0..4, read by FUN_0012ec10 as `*(u16*)(class_base + (gear*5 + column)*2)`; the fallback copy is used when no class matches. The stage-3 tune rewrites classes 1–3 entirely to 5000, and class 0 and the fallback partially (37 and 33 of their 90 bytes) — i.e. it effectively removes the per-class torque ceiling during shifts. Confidence **MED**.

**Downshift blip torque maps (`shiftexec_dn_blip_trq_k2_*`)** — 7 items, 6×10 u8 maps in a 7-block family at stride 0x138, 0x1AC0E0–0x1AC830 (values at 0x1AC0F8 `2to1`, 0x1AC230, 0x1AC368 `4to3`, 0x1AC4A0 and 0x1AC5D8 — both of these carry the title `k2_6to5`, because both are byte-identical to the same F-build object (`F 1b2600`), so one of them presumably serves a neighbouring gear pair — 0x1AC710 `7to6`, 0x1AC848 `8to7`). Axes: 6 points (34..188) × 10 points (17..94), z = u8 running from 128 upward (a 0x80-biased "128 = zero" encoding is a plausible reading, but the RE evidence does not state it). These shape the engine-torque blip request during downshifts (the rev-match element of a clutch-to-clutch downshift). Named members are **HIGH** confidence (byte-identical object matches against the reference F build, reader FUN_000c8f92 via the banked block slots); the unresolved `shiftexec_dn_blip_map_6x10` at 0x1AC230 is **LOW** (auto-detected, meaning not analysed, but same family geometry). Gear-pair indices are inferred by k-slot alignment, not directly proven.

**Shift-type condition records** — 15 items, `shift_type_cond_records r00..r14`, 31×1 u8 each at 0x1CB340 + r×0x1F (records 0–14 of 20). Reader FUN_0011733c indexes `&DAT_001cb340 + row*0x1f`. Byte layout: +0x00..+0x12 required condition mask, +0x13/+0x14 up/down flags, +0x15..+0x1D per-gear enable bytes, +0x1E program/selector byte. The tune changes only a handful of bytes. Semantics not proven — Confidence **LOW**; don't hand-edit beyond replicating known-good diffs.

**Shift-type thresholds & selectors** — 4 items: `shift_type_thresholds` 0x1CB658 (6 u16, read by shift_type_select; tune: 950→550, 250→450, 1060→850 ×2 — MED), `shift_element_pair_b` 0x1CAF14 (6 u16 of duplicated bytes, third of three 12-byte pair tables at 0x1CAEFC/0x1CAF08/0x1CAF14, rewritten to equal its 0x1CAF08 sibling; consistent with the per-gear shift-element pair list — MED), `shift_mode_selectors` 0x1CB334 (12 u8, read by shift_mode_index_select via FUN_001164cc — MED, layout not proven), and `per_gear_torque_rows` 0x1CEE00 (1×75 u16, `(&0x1CEE00)[gear]` is the minuend of headroom db62 in shift_torque_headroom_eval, reader FUN_00111b12 — HIGH that it's read there, layout not proven; tune lowers 21 entries). Together these steer which shift *type* variant the executor picks and how much torque headroom the shift logic assumes per gear.

**Shift pressure maps** — 8 items, `shift_press_map_b2..b9`, 6×3 s16 maps at 0x1C756E–0x1C772E (stride 0x40), auto-detected ranges x −200 up to ~390..1190 depending on the map, y 2000..7000, z 3500..19000 (b2: 13000..19000). Meaning not analysed, no reader found. Confidence **LOW**. The value ranges are plausible for pressure-vs-torque/speed scheduling, but that is not proven — included because the stage-3 tune edits them.

**Torque-converter torque-ratio curve** — 1 item, `tc_torque_ratio_curve` 0x19A864, 6-point curve (x 0..920, z 991..1865). Byte-identical to the F-build object of the same name (read by FUN_000b9d10 there). The ~1.9→1.0 shape is what a converter torque-multiplication curve looks like, but the item itself is rated Confidence **LOW**.

**Headroom mode-1 curve** — 1 item, `shift_torque_headroom_mode1_curve` 0x1CED64, 5×1 auto-detected curve (x 3000..6000, z 10280..21845), sibling of the mode-0/gear-0 curves listed under Additional maps. Meaning not analysed — Confidence **LOW**.

**Duplicates of the Additional-maps items** — 18 items (13 tables + 5 constants) that appear in both folders so the stage-3 walk-through is complete in one place: `gearsel_dn_speed_offset_by_char_gear`, `intervention_element_thr_by_index`, `shift_torque_headroom_gears1_4_curve` / `_gear0_curve` / `_mode0_curve`, `gear_display_digit_rule`, `cal_trailer_ptr_triple`, `gearsel_curve_a_6pt` / `_b_6pt`, `cal_id_string`, `gearsel_dn_gear_bound_by_char`, `shiftexec_state_flag_tbl`, `strat_state_mask_tbl`, and the constants `strat_state_mask_vec`, `escalation_test1_threshold`, `shiftprog_phase_2to3_flag`, `shiftprog_param_block_mask`, `cal_declared_crc32`. They are documented once, below.

### Additional maps

20 items. The objects a stage-3 tune edits that could not be bound to a proven subsystem. Almost everything here is **LOW** confidence: structures inferred from edit grids and neighbouring objects, readers mostly unknown. They are in the XDF so the tune's diff is fully visible.

**Gear-selection small objects (`gearsel_*`)** — 4 items near the shift-schedule data. All structure-not-proven, Confidence **LOW**; the stage-3 edits consistently push the x/first values upward or halve bounds, consistent with later/laxer downshift behaviour, but that reading is not proven:

| Parameter | Address | Shape | What the tune does |
|---|---|---|---|
| gearsel_dn_speed_offset_by_char_gear | 0x1CC79E | 2×3 s16 pairs | First element of each pair raised (e.g. −1000→−600, −500→−240) |
| gearsel_curve_a_6pt | 0x1CC7D0 | 2×6 u16 (x,y) pairs | Only x of each pair raised (0→738 … 2249→2698) |
| gearsel_curve_b_6pt | 0x1CC7F4 | 2×6 u16 (x,y) pairs | Only x of each pair raised; same shape as curve_a |
| gearsel_dn_gear_bound_by_char | 0x1CB80C | 2×1 u16 | Both values halved: 4→2, 2→1 |

**Shift torque headroom curves** — 3 items (plus the mode-1 sibling in stage 3): `shift_torque_headroom_mode0_curve` 0x1CED4E (5-pt mdl curve, x 3000..6700; tune raises the 2nd/3rd breakpoints and edits 4 of the 5 values — not all upward: 10280→9767), `shift_torque_headroom_gear0_curve` 0x1CEDA6 (5-pt curve, x 3000..6500), `shift_torque_headroom_gears1_4_curve` 0x1CEDB0 (4×5 u16 block, row stride 10 B; tune lowers 15 of 20 cells, last row untouched). They sit directly beside `per_gear_torque_rows`, which *is* proven to feed shift_torque_headroom_eval, so the family plausibly scales how much engine torque the shift logic budgets for — but each item's own meaning is not analysed. Confidence **LOW**.

**intervention_element_thr_by_index** — 1 item, 0x1CE634, 9×3 u16 (row stride 0x12). Stock rows repeat a 1700/6500/1700 motif; the tune rewrites 12 cells that stock at 1700 up to 6500/4500/3500/3000 — i.e. it raises rpm-looking intervention thresholds. Reader unknown, stride inferred from the edits. Confidence **LOW**.

**gear_display_digit_rule** — 1 item, 0x1914C8, 4 records × 8 bytes. Byte 0 of each record is the per-object display-source selector read by disp_gear_digit_select (0xAFC12 via FUN_0009ACF0): 0 = no digit, 1/2 = raw sources, 3 = gear number 1..8. The tune sets byte 0 of every record 0x00→0x03, i.e. **it makes the cluster show the actual gear number** — the cosmetic companion to the True-manual patch. This one has a traced reader; effectively the best-understood item in the folder.

**Calibration metadata** — 3 items: `cal_id_string` 0x1911F0 (16 ASCII bytes, '0M4B20K681B2A4' → '0N3B20K681B2A4' in the tune — the calibration ID text, not a tunable; MED), `cal_declared_crc32` 0x180244 (u32 in the header area; the tune rewrites it 0x5C92EDAB→0xF767FB4B — **this is the CRC you must recompute after any edit or patch**; LOW as to exact algorithm/role), and `cal_trailer_ptr_triple` 0x180266 (5 s16 in the header area, meaning not proven; LOW). Rule of thumb: don't creatively edit header-area items — change them only the way a known-good tune does, and keep the CRC consistent.

**Unresolved XHP-gap objects** — 3 items: `xhp_gap_a_obj` 0x199AA0 (10 u16, tune changes 7 of 12 words by +45..+82 %; only reference is a data pointer, no reader found), `shiftexec_state_flag_tbl` 0x1AE9EC (50 u16; the tune rewrites this 100-byte block in bulk, doubling every changed word; only reference is table 0x4DDB0, whose readers are the FUN_000AC4A0 / FUN_000DE8AC family, but no reader is proven to reach this block — structure not proven), `xhp_gap_b_obj` 0x1AE9E8 (the u32 count word in front of the same block; no layout evidence). Confidence **LOW** throughout — these are "the tune changes something here" markers, not understood maps.

**Strategy state masks** — 2 items: `strat_state_mask_tbl` 0x1C95E5 (the tune rewrites 34 values on a constant 12-byte stride — one 2-byte field of a 6-field record; emitted as a 34×6 grid so row 0 of each column is editable; MED that the stride is real, not validated against reader code) and `strat_state_mask_vec` 0x1CADD8 (u16, low byte 0x0100→0x0101; the identical edit also appears at 0x19611A; LOW).

**Shift-program flags & escalation threshold** — 3 constants: `shiftprog_phase_2to3_flag` 0x19611A (u16 0x0100→0x0101, mirror of the 0x1CADD8 edit; LOW), `shiftprog_param_block_mask` 0x195E18 (lone u16 0xFFFF→0x0001, a sentinel/disable flag by position only; LOW), `escalation_test1_threshold` 0x1CECA4 (u16 7100→7200 in the stage-3 tune — the same word the True-manual patch later sets to 0xFFFF, and the same 7200 the tune writes into the 18-u16 block at 0x1CC03C; LOW as a standalone item, but its role in guard test 1 is corroborated by the patch evidence).

Coverage: Covers all 131 items in this group — 3 in Patches (2 patches + Radumfang), 108 in stage 3 (16 + 33 + 5 + 7 + 15 + 4 + 8 + 1 + 1 + 18 duplicates) and 20 in Additional maps (4 + 3 + 1 + 1 + 3 + 3 + 2 + 3) — in 21 families as grouped above.
