# Unlabelled auto-detected structures (E84)

The E70 XDF carries 2,609 unlabelled items: 2,461 auto-detected structures (the ten
`Unlabelled: <type>` structural families) plus 148 provisional `Unlabelled: <subsystem>` items
with traced E70 readers. **1,927 of them (74%) survived the port into `8hpe84_cali_v1.xdf`; the
other 682 are not in the E84 XDF (needs full flash read).** Everything that applies to the E70
group applies here, plus one layer: every E84 item is a *ported* record, located by content
matching against a calibration-only read, not by a scan of the E84 image itself. All items remain
**Confidence LOW**, "Meaning not analysed", no units, raw values only. **Treat the entire group as
read-only reference: do not edit any of these tables.**

The E84 read contains no program code (everything below 0x180200 is erased), so *every*
code-level statement in these items — `Read by:` functions, Ghidra context, semantic label
hypotheses — is inherited from the E70 RE (same Bosch iTCU2 / SH-2A family, earlier 2012 software
generation) and cannot be re-verified against E84 code.

Coverage by category (E70 total → ported into the E84 XDF; E84 data-address span):

| Category | E70 | E84 | E84 span |
|---|---|---|---|
| Unlabelled: s16 curves | 733 | 507 | 0x190A2E–0x1DA886 |
| Unlabelled: u8 curves | 571 | 357 | 0x191744–0x1DFEB3 |
| Unlabelled: s16 maps | 537 | 448 | 0x193B1C–0x1D4FA8 |
| Unlabelled: u8 maps | 410 | 368 | 0x1903ED–0x1D24E8 |
| Unlabelled: f32 maps | 124 | 100 | 0x19BA5C–0x1A7818 |
| Unlabelled: f32 curves | 4 | 2 | 0x1A211C–0x1A2470 |
| Unlabelled: u16 curves | 3 | 1 | 0x1D84A4 |
| Unlabelled: model u16 curves | 44 | 26 | 0x190E54–0x1DEBF8 |
| Unlabelled: model s16 curves | 5 | 2 | 0x1DAE28–0x1DB194 |
| Unlabelled: model u16 maps | 30 | 5 | 0x1A338E–0x1E0362 |
| *structural families subtotal* | *2,461* | *1,816* | |
| Unlabelled: Shift strategy | 19 | 10 | 0x1D792A–0x1DE7E6 |
| Unlabelled: Shift pressure | 1 | 1 | 0x1B4F44 |
| Unlabelled: Shift execution | 1 | 1 | 0x1B2654 |
| Unlabelled: Shift elements | 3 | 1 | 0x198436 |
| Unlabelled: Adaptation | 1 | 1 | 0x1994A8 |
| Unlabelled: Diagnosis / monitoring | 123 | 97 | 0x1972C4–0x1D49D8 |
| *subsystem buckets subtotal* | *148* | *111* | |
| **Total** | **2,609** | **1,927** | |

The helper-layout split survived intact: `cal_curve_*`/`cal_map_*` are the ordinary calibration
lookups, `mdl_*` the transmission-model layout (rows = x input, columns = y input in TunerPro),
and all five `e_hdr_*` header-variant records made it across (see the family notes below).

### How to read an E84 entry

* **Title** — unchanged from the E70 XDF. `auto_<hex>` is the **E70** structure-start address,
  *not* an E84 address: `auto_190920` now lives at E84 0x190A2E. 1,224 items keep the plain
  `auto_<hex>` name, 85 the longer `auto_<hint>_<hex>` style (subsystem buckets), and 618 carry
  a promoted working name (609 from the Ghidra label sync, plus the 9 surviving legacy
  provisional names: `shift_press_map_b2`…`b9` and `shiftexec_dn_blip_map_6x10`;
  `shift_torque_headroom_mode1_curve` did not port). Titles are unique within this group, so
  `tools/xdf_show.py` lookup by title is unambiguous.
* **Leading `@0x… (file +0x…)` in the description** — the **E84** address the XDF points at
  (the z-data inside the structure; file offset = address − 0x180200). This is the address to
  use on the E84; it is the same value as the XDF's embedded z address.
* **Evidence string** (`cal_curve_s16 5x1, x -640..2240, z 7..4250` etc.) — carried over from
  the **E70 scan**. For items ported `exact` the E84 bytes are identical, so the quoted raw
  ranges hold; for any other method, dump the table from your E84 read before trusting them.
* **`Read by:`** — E70 program-code functions. In the ten structural families this is "unknown"
  on all 1,816 items (the single E70 exception, `auto_191394`, did not port — see below). All
  111 subsystem-bucket items name an E70 reader (`FUN_…` or a labelled function); none of these
  can be confirmed on the E84 without a full flash read.
* **`|| Ghidra hp8_sh …` section** — two forms, both in **E70 address space**:
  * `Ghidra hp8_sh context: …` (816 items) — neighbourhood only: the enclosing/preceding data
    block, its E70 reader, and the nearest labelled E70 item with its distance.
  * `Ghidra hp8_sh (2026-10-15): <name> @0x… - MAP/CURVE x=… y=… z=… (LOW) [reader]`
    (733 items) — a semantic hypothesis from the E70 decompile pass, with axis meanings, value
    ranges and the reading module. 609 of these items were retitled to the hypothesis name;
    124 keep their `auto_<hex>` title with the semantics only in the description. All of it is
    LOW confidence; the `@0x…` is the E70 address.
  * 378 items have no Ghidra section at all.
* **`|| E84 8609556: …` sentence** — the port provenance, present on every one of the 1,927
  items. Explained next.

### How to read the port provenance

Every ported description ends with:

```
|| E84 8609556: ported from E70 by content match (<method>), delta <±0x…>.
```

`delta` is this item's E84 address minus its E70 address. **The E84 layout is not a constant
shift of the E70**: deltas across the group run from −0x35E8 to +0xDEB4 and differ per region
(most common +0x6F54 on 288 items, then +0x5D9C, +0x4A68, +0x4FC8, +0x5C68). Never translate an
E70 address by a single global offset — use the item's own delta, or just use the leading `@0x…`.

`<method>`, in decreasing order of strength:

| Method | Items | What it means |
|---|---|---|
| `exact` | 1,151 | The structure's bytes were found byte-identical in the E84 image. Strongest: location and content both confirmed. |
| `interval` | 396 | Length-preserved interval mapping: the item sits between exactly-matched anchors and the gap lengths agree, so the slot is inferred. Content may differ from the E70 values. |
| `walk` | 352 | Record-stream walking: the porter re-parsed the record grammar (curves `[u8 n][u8 n][x][z]`, maps `[u8 nx][u8 ny][x][y][z]`, u32-count records, shared axis vectors `{u16 n; s16[n]}`) forward from a matched anchor and counted records to the slot. Structure shape confirmed, identity inferred from position. |
| `regvote` | 17 | Regional delta voting: neighbours in the same region agreed on a delta and it was applied. |
| `globalign` | 11 | Global signature alignment only. Weakest — treat the address as a hint. |

Practical reading: `exact` items you can quote directly; for everything else, confirm with
`tools/xdf_show.py 8hpe84_cali_v1.xdf <your_e84_read.bin> <title>` that the dumped table looks
like a plausible structure (smooth data, sane axis monotonicity) before even *reading* values
off it. Since these items are not to be edited in either calibration, the main cost of a
mis-anchored port is a misleading diff, not a bad flash.

### Where they live (E84)

The structural families (1,816 items) span 0x1903ED–0x1E0362. Density by 32 KB region:

| Region | Items | | Region | Items |
|---|---|---|---|---|
| 0x190000–0x197FFF | 65 | | 0x1C0000–0x1C7FFF | 333 |
| 0x198000–0x19FFFF | 81 | | 0x1C8000–0x1CFFFF | 124 |
| 0x1A0000–0x1A7FFF | 120 | | 0x1D0000–0x1D7FFF | 145 |
| 0x1A8000–0x1AFFFF | 275 | | 0x1D8000–0x1DFFFF | 23 |
| 0x1B0000–0x1B7FFF | 407 | | 0x1E0000–0x1E7FFF | 1 |
| 0x1B8000–0x1BFFFF | 242 | | | |

Same picture as the E70 shifted up by the regional deltas: the dense 0x1A8000–0x1C8000 band is
the per-gear-pair / per-class repetition zone of the shift-execution and shift-pressure regions.

### Family notes (what survived, what stands out)

* **s16 curves (507/733)** — the workhorse family. Both `e_hdr_curve_s16` header-variant curves
  survived: `auto_191474` (19x1, still the longest curve in the group) at 0x1916D6 (`exact`,
  delta +0x238) and `auto_19f23c` (3x1) at 0x1A336E (`exact`, delta +0x4128).
* **u8 curves (357/571)** — worst absolute loss (214 dropped). The `e_hdr_curve_u8`
  `auto_1d35f0` (2x1, raw z 0..0) survived at 0x1DFEB3 (`exact`, delta +0xC8BD).
* **s16 maps (448/537)** — `e_hdr_map_s16` `auto_1943e8` (4x4) survived at 0x193B1C (`exact`,
  delta **−0x8E0** — one of the few negative-delta regions). The eight provisionally named
  `shift_press_map_b2`…`b9` (6x3) all ported, at 0x1D25CA–0x1D274A — but see the collision
  caveat below: `b2` and `b3` resolve to the *same* E84 address, so treat `b2`'s slot as
  suspect. **`auto_191394` — the E70 group's only structural item with traced readers
  (`FUN_000f4ba6`/`FUN_000f7530`) — is not in the E84 XDF** (needs full flash read); its E70
  z-data is all zero, which leaves content matching little unique to anchor on.
* **u8 maps (368/410)** — best port rate of the big families (90%). `e_hdr_map_u8`
  `auto_1902e4` (2x3, z 0..0) survived at 0x1903ED and is still the lowest-addressed item in
  the group. `shiftexec_dn_blip_map_6x10` (6x10) ported to 0x1B10EC (`walk`, delta +0x4EBC).
* **f32 maps (100/124)** — still one tight float band (0x19BA5C–0x1A7818 on the E84). Of the
  6x6 maps flagged on the E70 as likely members of the TCC slip-PID gain family, five survived,
  all `interval` with delta +0x41A8: `auto_1a08ac` @0x1A4A8C, `auto_1a0a3c` @0x1A4C1C,
  `auto_1a0b04` @0x1A4CE4, `auto_1a0bcc` @0x1A4DAC, `auto_1a0c94` @0x1A4E74. Being `interval`
  ports, dump them from a real E84 read before leaning on them for TCC analysis.
* **f32 curves (2/4)** — `auto_19e0ec` (6x1) @0x1A211C (`walk`) and `auto_19e5d8` (4x1, z 0..0)
  @0x1A2470 (`interval`).
* **u16 curves (1/3)** — only `auto_1cb784` (10x1) @0x1D84A4 (`exact`, delta +0xCD08).
* **model u16 curves (26/44)** — the dropped 18 include `shift_torque_headroom_mode1_curve`,
  the last of the E70's ten legacy provisional names: **not in the E84 XDF** (needs full flash
  read).
* **model s16 curves (2/5)** — `auto_1ce9bc` @0x1DAE28 and `auto_1ce9e8` @0x1DB194 (both
  `exact`, 5x1, rpm-looking x axes with negative z).
* **model u16 maps (5/30)** — worst port rate in the group (17%). The `mdl_*` map region around
  E70 0x1CBxxx evidently diverged heavily between the two calibrations; treat the five
  survivors with extra suspicion.

### The provisional subsystem buckets (111/148)

Unlike the structural families, these items have **traced E70 readers** — that is why they were
given subsystem categories on the E70. The E84 copies keep the reader names
(`Read by: FUN_0012d150`, `Read by: shiftexec_dn_blip_outgrad_scale`, …), which refer to E70
program code only.

* **Diagnosis / monitoring (97/123)** — the bulk; mixed `auto_cal_*`-titled curves/maps spread
  0x1972C4–0x1D49D8.
* **Shift strategy (10/19)** — `auto_mdl_*`-titled model records at 0x1D792A–0x1DE7E6, inside
  the native shift-line/strategy region.
* **Shift pressure (1/1)**, **Shift execution (1/1)** (`auto_shiftexec_dn_blip_outgrad_scale_1ad67c`
  @0x1B2654), **Shift elements (1/3)**, **Adaptation (1/1)**.

### What did not port — 682 items

Everything in this section is **not in the E84 XDF (needs full flash read)**: 645 structural
items and 37 subsystem items for which no sufficiently confident content match existed in the
calibration-only read. The drop lists in the port report cluster heavily in the E70
0x1A3000–0x1A6000 band (TCC / shift-execution border) and the E70 0x1CBxxx `mdl_*` region —
the areas where the two calibrations' content diverged most. Named casualties worth remembering:
`auto_191394` (traced readers) and `shift_torque_headroom_mode1_curve`. If you need any of
these on the E84, the path is a full flash read of an E84 TCU, then re-running the scan +
port against it.

### Known port artifacts: address collisions

13 pairs of unlabelled items resolve to the **same E84 z-data address**. Each pair means at
least one of the two is mis-anchored (different methods/deltas voted onto one slot). Until one
is re-verified, read both entries of a pair as "somewhere near here":

| E84 addr | Items |
|---|---|
| 0x19E3A8 | `auto_19c130`, `auto_19d1f4` |
| 0x19F440 | `auto_19cbd8`, `auto_19da34` |
| 0x1A9B70 | `auto_1a4e30`, `auto_1a5414` |
| 0x1B179A | `auto_1ac434`, `auto_1ac914` |
| 0x1B1BA2 | `shiftexec_up_trq_rampout_noti_k2_k1_2to3_1ac7d8`, `auto_1accbc` |
| 0x1B1BDC | `auto_1ac810`, `auto_1accf0` |
| 0x1B4FC0 | `auto_1af940`, `auto_1af958` |
| 0x1B6344 | `auto_1b0934`, `auto_1b0940` |
| 0x1BE5D2 | `auto_1b79dc`, `auto_1b766c` |
| 0x1C7AB4 | `auto_1bf500`, `auto_1bf694` |
| 0x1C7B28 | `shift_press_b_up_oiltemp_press_ofs_c2_4to5`, `auto_1bf520` |
| 0x1D25CA | `shift_press_map_b2`, `shift_press_map_b3` |
| 0x1D792A | `auto_mdl_map_s16_u16_1cb2e8`, `shift_press_up_time_trim_c1_7to8` |

In the `b2`/`b3` case the deltas disagree (+0xB05C `walk` vs +0xB01C `globalign`) while
`b4`…`b9` all sit on the +0xB01C grid at 0x1D260A–0x1D274A, so `b2`'s true slot is most likely
0x40 below `b3` — but that is an inference, not a verified match.

### The E70 educated guesses on the E84

The E70's speculative per-item guesses ([chapter 12](../../e70/parameters/12-unlabelled-guesses.md),
[CSV](../../e70/data/unlabelled-guesses.csv)) were **not carried into the E84 XDF** — no E84
description contains a `SPECULATIVE GUESS` sentence. You can still use them: the CSV is keyed by
E70 address, which is exactly what the E84 titles encode, so look an item up by its title hex.
Two caveats: all cluster spans and neighbour addresses in that chapter are E70-space (apply the
item's delta), and a guess that was already SPECULATIVE on the E70 is a 2012-generation,
different-calibration guess on the E84 — weaker still. The cluster-level reading (shift-execution
and shift-pressure per-gear-pair families making up the bulk, the f32 band as one float
subsystem) should transfer, since the port preserved relative layout.

### Practical guidance

* **Do not edit anything in this group**, on the E84 even more so than on the E70: meaning,
  scaling and effect are all unanalysed, *and* 776 of the 1,927 items are located by inference
  (`interval`/`walk`/`regvote`/`globalign`) rather than byte-exact match.
* The group remains a **diff surface**: diffing your E84 ZB against another 8609556-family
  calibration with `tools/xdf_diff.py` will show changes inside these structures with address
  and shape, even unnamed. xdf_diff takes the XDF as its first positional argument (`tools/xdf_diff.py 8hpe84_cali_v1.xdf stock.bin tuned.bin`); only xdf_tune and xdf_gui default to the E84 XDF.
* To sanity-check any single item: `tools/xdf_show.py 8hpe84_cali_v1.xdf <your_e84_read.bin>
  <title>` and look for smooth, plausible data at the slot.
* **Promoting an item out of this group requires E70 code work or an E84 full flash read.**
  The fast path today: take the title's E70 address, trace its reader in the E70 Ghidra project
  (`hp8_sh`), and carry the semantics across — flagged as E70-inherited, like the 733 existing
  semantic labels.

Coverage: covers all 1,927 unlabelled items in `8hpe84_cali_v1.xdf` (16 categories), and
accounts for the 682 E70 unlabelled items that did not port.

See also: [E70 chapter 11](../../e70/parameters/11-unlabelled.md) — the scanner, record layouts
and family descriptions in full; [E70 chapter 12](../../e70/parameters/12-unlabelled-guesses.md)
— the speculative guesses and cluster interpretations referenced above.
