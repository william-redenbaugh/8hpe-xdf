# Parameter reference — 8HP45 E84 XDF (ZB 8609556)

What every parameter in `8hpe84_cali_v1.xdf` is, organised by subsystem. The
XDF defines **3,617 tables, 24 constants and 1 clickable patch** in 66
TunerPro categories, for the E84 X1 (gearbox GKE233, TYPTEILENR b5yc1313,
SW Z5YD7900_8HPXY_K790D, cal ZB 8609556 — an 8HP45, ratios
> The bin's full ZFADINFO identifier is `Z5YD7900_8HPXY_BMW_K790D`; the XDF header and these docs abbreviate it to `Z5YD7900_8HPXY_K790D`.
4.714 / 3.143 / 2.106 / 1.667 / 1.285 / 1.000 / 0.839 / 0.667).

This XDF is a **port of the E70 RE** (`8hpe70_cali_v3.xdf`, cal 8646496),
not an independent reverse engineering. Same Bosch iTCU2 / SH-2A family, one
software generation earlier (2012). Read this page before trusting anything
in the chapters.

## The big caveat: calibration-only read

The E84 image behind this XDF is a 2 MB file in which **everything below
0x180200 is erased 0xFF** — the calibration block (0x180200–0x1FFFFF) is
real, the **program ROM is missing**. Verified in the image: the whole
region below 0x180200 is 0xFF. Consequences:

- **No code-level statements are native.** Every claim about *how* a table
  is read (reader functions, selectors, units) inherits from the E70
  decompilation. Layout/content claims are checked against the E84 bytes;
  behaviour claims are E70 evidence applied by analogy.
- **Characteristic-to-drive-mode mapping is unknown.** The shift-line
  pointer tables live in the missing program ROM. The block↔pedal-axis
  pairing in the XDF is **positional (LOW)** — it affects the displayed
  pedal breakpoints only, not z-value edits. Identify the active
  characteristic by logging before retuning it.
- **E70 items whose only anchor was program code could not be ported**
  (the `Ghidra new:` categories below are mostly dropped).

A **full flash read** (bootloader read including 0x0–0x180200) would unlock:
porting the remaining ~4,000 dropped items (packed `shift_press` /
`shiftexec` / `shift_time` internals, the Ghidra-new ratio-monitoring,
coast/sail and system-pressure blocks, code-anchored labels), resolving the
characteristic↔mode mapping from the E84's own pointer tables, porting the
True-manual patch (its overspeed-limit entries are code-anchored), and a
native checksum algorithm search.

## How to read this reference

- **Addresses** are flash addresses = file offsets in the 2 MB image
  (calibration block 0x180200–0x1FFFFF). Multi-byte values are
  **big-endian**, values are **raw** unless the E70 RE proved units.
- **Confidence levels** are preserved from the E70 XDF (HIGH / MED / LOW,
  same definitions as the [E70 reference](../../e70/parameters/README.md)),
  then capped by the port: anything that depends on the missing program ROM
  (axis pairing, characteristic identity, reader behaviour) is at most the
  E70 level and usually a notch below. The XDF description of every item
  carries an explicit `|| E84 8609556:` suffix saying how it got here and
  with what byte delta — that suffix is the ground truth for this build.
- **Every address in these chapters was verified against the E84 image**
  by the port (exact byte match or structure walk). If an E70 parameter is
  not in the E84 XDF, the chapters say "not in the E84 XDF (needs full
  flash read)" — absence is stated, not silent.

## Provenance: how this XDF was made

The chain is: **E70 Ghidra RE → decompile-verified record grammars →
content port into the E84 image.**

1. The E70 XDF (4,200+ items plus Ghidra-enriched labels) was built by
   static RE of the E70 calibration with decompiled reader functions.
2. From the decompilation, the **record grammars** of the calibration
   container are known exactly: curves `[u8 n][u8 n][x…][z…]`, maps
   `[u8 nx][u8 ny][x…][y…][z…]`, u32-count records, shared axis vectors
   `{u16 n; s16[n]}`.
3. Each E70 item was relocated into the E84 image by, in order of
   preference: **exact byte match** (2,119 items), **length-preserved
   interval mapping** (569), **record-stream walking** with the grammars
   above (461), **global signature alignment** (33), **regional delta
   voting** (17), one **manual signature** (the Radumfang constant).
   Total ported: **3,200**. Every ported item's description ends with
   `|| E84 8609556: ported from E70 by content match (<method>), delta
   <±0x…>`.
4. **Shift lines were not ported — they were rebuilt natively** from the
   E84's own structure (**441** items): the E84 has **21 characteristics**
   (E70 had 23), numbered 00..20 in **memory order**. 1>2..5>6 blocks at
   **0x1DBA68** (300 B per characteristic: five 60-byte gear-pair stripes,
   15 u16 upshift column then 15 u16 downshift column; downshift slot =
   upshift slot + 30 B), 6>7 pairs at **0x1DD304** (60 B/char), 7>8 pairs
   at **0x1DD7F0** (60 B/char). Pedal axes `{u16 15; u16[15]}` at
   **0x1D8FA8**, 32-byte stride, values at +2 (char 00 values at 0x1D8FAA).
   The shift-disabled sentinel is **8200** in the E84 (E70 used 8000).
   Characteristics **15 and 16 have all-zero 1>2 stripes** (verified in
   the image) — likely the manual-mode characteristics.

## Coverage: what survived the port

Per E70 category: how many items the E70 XDF had, how many are in the E84
XDF (ported + native), and how many were dropped. **Dropped** = present in
the E70 XDF but not portable to the E84 without a full flash read — mainly
packed `shift_press`/`shiftexec`/`shift_time` internals, the Ghidra-new
ratio-monitoring/coast blocks, and code-anchored labels. A category with 0
kept still exists in the E84 XDF's category list but is empty.

| Category | E70 total | Kept | Dropped |
|---|---|---|---|
| Shift lines: upshift | 69 | 63 | 6 |
| Shift lines: downshift | 69 | 63 | 6 |
| Shift lines: single curves | 322 | 294 | 28 |
| Shift lines: pedal axes | 23 | 21 | 2 |
| Shift strategy: programs / state | 49 | 22 | 27 |
| Shift strategy: gear selection / limits | 14 | 8 | 6 |
| Shift strategy: sport functions (sf##) | 3 | 3 | 0 |
| Shift strategy: driver / driving situation | 3 | 3 | 0 |
| Shift pressure: upshift base (b_up) | 51 | 51 | 0 |
| Shift pressure: upshift phases / torque | 60 | 42 | 18 |
| Shift pressure: downshift base (b_dn) | 142 | 139 | 3 |
| Shift pressure: downshift phases / torque | 153 | 140 | 13 |
| Shift pressure: other | 13 | 7 | 6 |
| Shift execution: upshift | 107 | 98 | 9 |
| Shift execution: downshift | 91 | 91 | 0 |
| Shift execution: timing control | 1 | 0 | 1 |
| Shift execution: other | 79 | 73 | 6 |
| Shift elements: fill / protection | 4 | 4 | 0 |
| Shift elements: other | 47 | 45 | 2 |
| Torque converter: slip | 13 | 12 | 1 |
| Torque converter: pressure / control | 18 | 15 | 3 |
| Torque converter: lock-up / open / close | 14 | 10 | 4 |
| Torque converter: other | 17 | 11 | 6 |
| Adaptation: fill | 17 | 16 | 1 |
| Adaptation: shift | 7 | 6 | 1 |
| Adaptation: driving situation | 26 | 24 | 2 |
| Adaptation: other | 1 | 1 | 0 |
| Standstill: neutral idle | 32 | 30 | 2 |
| Standstill: other | 7 | 7 | 0 |
| Gear ratio monitoring | 35 | 35 | 0 |
| Signals: speeds | 4 | 4 | 0 |
| Signals: temperature / warm-up | 1 | 1 | 0 |
| Signals: torque / losses | 39 | 38 | 1 |
| Additional maps | 20 | 4 | 16 |
| Unlabelled: Shift strategy | 19 | 10 | 9 |
| Unlabelled: Shift pressure | 1 | 1 | 0 |
| Unlabelled: Shift execution | 1 | 1 | 0 |
| Unlabelled: Shift elements | 3 | 1 | 2 |
| Unlabelled: Adaptation | 1 | 1 | 0 |
| Unlabelled: Diagnosis / monitoring | 123 | 97 | 26 |
| Unlabelled: f32 curves | 4 | 2 | 2 |
| Unlabelled: f32 maps | 124 | 100 | 24 |
| Unlabelled: model s16 curves | 5 | 2 | 3 |
| Unlabelled: model u16 curves | 44 | 26 | 18 |
| Unlabelled: model u16 maps | 30 | 5 | 25 |
| Unlabelled: s16 curves | 733 | 507 | 226 |
| Unlabelled: s16 maps | 537 | 448 | 89 |
| Unlabelled: u16 curves | 3 | 1 | 2 |
| Unlabelled: u8 curves | 571 | 357 | 214 |
| Unlabelled: u8 maps | 410 | 368 | 42 |
| stage 3 \* | 108 | 1 | 41 |
| Ghidra new: signals | 50 | 3 | 47 |
| Ghidra new: torque converter | 35 | 4 | 31 |
| Ghidra new: shift strategy | 134 | 18 | 116 |
| Ghidra new: adaptation | 305 | 32 | 273 |
| Ghidra new: other | 68 | 3 | 65 |
| Ghidra new: standstill / engine | 11 | 6 | 5 |
| Ghidra new: shift execution | 741 | 63 | 678 |
| Ghidra new: shift pressure | 1169 | 169 | 1000 |
| Ghidra new: shift elements | 116 | 28 | 88 |
| Ghidra new: ratio monitoring | 268 | 5 | 263 |
| Ghidra new: coast / sail | 175 | 0 | 175 |
| Ghidra new: diagnosis / monitoring | 33 | 0 | 33 |
| Ghidra new: shift lines (model) | 335 | 0 | 335 |
| Patches (click to apply) | 1 | 1 | 0 |
| Ghidra new: system pressure | 31 | 0 | 31 |
| **Total** | **7740** | **3641** | **4033** |

\* The stage-3 category duplicates items documented in other categories;
its remaining 66 items are counted (kept or dropped) in their primary rows.
Of the 3,641 kept items, 3,200 were ported and 441 (the shift lines) are
native E84 structure. The 3,641 report rows plus the `[PATCH]` entry itself
account for all 3,642 items the XDF defines.

## Patches

- **`[PATCH] Start in 2nd (E84) [PARTIAL]`** — the only clickable patch.
  Rebuilt on the native E84 slots: zeroes the 1>2 upshift and 2>1 downshift
  stripes of all 21 characteristics (char 00 at 0x1DBA68/0x1DBA86, stepping
  300 B per characteristic) plus 2 auxiliary entries. **49 auxiliary
  entries (inhibit / min-speed) could not be ported and are omitted** —
  behaviour may differ from the E70 version, hence `[PARTIAL]`.
- **True manual was NOT ported** — 6 of its 7 E70 entries were
  unresolvable in the calibration-only read, including **all overspeed
  limits** (code-anchored). Not in the E84 XDF (needs full flash read).
  Mitigating fact: the stock TCU guard is **~7100 rpm**, so holding gears
  to 7000 rpm (`sport-redline`, `redline-hold`) does not need it.

## Checksums

The E70 checksum algorithm **does not reproduce on the E84 read**:
`xdf_checksum.py search` fails to confirm any profile against this image.
Do not flash a bin signed with the E70 profile. Sign via the flash tool
instead — **xHP corrects checksums itself** when writing. A native
algorithm search needs the program ROM (full flash read).

## Tools quick-start

All repo tools (`tools/`: `xdflib` + `xdf_ls` / `xdf_show` / `xdf_export` /
`xdf_diff` / `xdf_patch` / `xdf_checksum` / `xdf_tune` / `xdf_gui`) work
against the E84 XDF. Where a tool resolves a default XDF (`xdf_tune.py
--xdf`, the GUI), it prefers `8hpe84_cali_v1.xdf`, then `8hpe70_cali_v3.xdf`;
`xdf_ls`/`xdf_show` take the XDF as their first positional argument. On this
Mac use `/usr/bin/python3` (Homebrew Python's expat is broken).

```sh
cd tools
/usr/bin/python3 xdf_ls.py ../8hpe84_cali_v1.xdf -c "Shift lines"   # browse
/usr/bin/python3 xdf_show.py ../8hpe84_cali_v1.xdf ../my_e84_read.bin \
    "Upshift lines, char 00: 1>2..5>6"
/usr/bin/python3 xdf_gui.py ../8hpe84_cali_v1.xdf ../my_e84_read.bin

# New: rev out 1st/2nd to --rpm (default 7000). Raises the 1>2 and 2>3
# upshift lines to rpm/ratio (ratios default to 8HP45 4.714/3.143), only
# from --pedal-from pedal permille up (default 400; 0 = everywhere);
# --chars limits which characteristics are touched.
/usr/bin/python3 xdf_tune.py sport-redline my_e84_read.bin -o out.bin \
    --rpm 7000 --pedal-from 400
```

`xdf_tune.py` never writes in place and does **not** correct checksums —
on the E84 that is deliberate (see Checksums above): flash the output with
a tool that re-signs (xHP). Keep `--rpm` at or under ~7000: the tool warns
above the ~7100 rpm stock TCU guard, and without True manual the guard
cannot be moved.

## Chapters

Same structure as the E70 reference; each chapter states per family whether
it is native, ported (and by which method), or not in the E84 XDF.

| # | Chapter | What's in it |
|---|---|---|
| 1 | [Shift lines (shift schedule)](01-shift-lines.md) | When the box shifts: the native E84 structure — 21 characteristics at 0x1DBA68/0x1DD304/0x1DD7F0, pedal axes at 0x1D8FA8, sentinel 8200 |
| 2 | [Shift strategy](02-shift-strategy.md) | Which schedule/program is active: strategy state attributes, gear limits, sport functions, driver detection (heavily thinned by the port) |
| 3 | [Shift pressure](03-shift-pressure.md) | How firmly clutches are pressed: b_up/b_dn base maps, phase pressures, temperature compensation |
| 4 | [Shift execution](04-shift-execution.md) | How a shift unfolds in time: phase/sync times, ramps, rev-match blip |
| 5 | [Shift elements](05-shift-elements.md) | Per-clutch/brake (A–E) engagement: fill, authority, protection |
| 6 | [Torque converter](06-torque-converter.md) | TCC lock-up & slip control: slip targets, apply pressures, converter model |
| 7 | [Adaptation](07-adaptation.md) | Self-learning rules: when adaptation runs, step sizes, clamps |
| 8 | [Standstill & gear-ratio monitoring](08-standstill-ratio-monitoring.md) | Neutral-idle/standstill decoupling, ratio-plausibility bands |
| 9 | [Signals & diagnosis](09-signals-diagnosis.md) | Input conditioning: speed/torque/temperature models, monitoring thresholds |
| 10 | [Patches, Radumfang & additional maps](10-patches.md) | The Start-in-2nd `[PARTIAL]` patch, the Radumfang constant (0x191404, stock 2003 mm), what of stage-3/additional maps survived |
| 11 | [Unlabelled structures](11-unlabelled.md) | Ported auto-detected curves/maps whose meaning is not analysed — reference material, do not edit |

The E70-only chapter 12 (unlabelled educated guesses) was not redone for
the E84; the [E70 guesses](../../e70/parameters/12-unlabelled-guesses.md)
transfer only where the item's port suffix shows an exact content match.
The [E70 deep dives](../../e70/parameters/README.md#deep-dives) (TCC
lock-up, manual-shift sensor faults, N52K TCC optimization, Quickflash
interop) describe the same control logic and apply by analogy.

## Where this came from

The XDF embeds, in every item description, the E70 evidence (address,
structure, confidence, reader functions) **plus** the E84 port suffix
(`|| E84 8609556: …` — method and byte delta, or `native slot`). This
reference was compiled from those descriptions and the port coverage
report; nothing here is based on vendor documentation, and nothing here
contains vendor data. When this reference and the XDF item description
disagree, trust the XDF description and please open an issue.
