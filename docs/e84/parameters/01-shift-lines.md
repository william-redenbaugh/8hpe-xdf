# Shift lines (shift schedule) — E84

E84 X1 (gearbox GKE233, cal ZB 8609556, SW Z5YD7900_8HPXY_K790D, 8HP45). XDF: `8hpe84_cali_v1.xdf`. Unlike almost everything else in that XDF, **the shift lines were rebuilt natively from the E84 binary structure, not ported from the E70** — every address below was walked out of the E84 image itself and verified cell-by-cell. The semantics are identical to the E70 (see `docs/e70/parameters/01-shift-lines.md`): for every gear pair the TCU stores a **shift line** — the output-shaft speed (rpm) at which the shift is requested, looked up over accelerator-pedal position. Pedal is per mille (0–1000, **1100 = kickdown**), speeds are **output-shaft rpm, not road speed** (convert via final drive and tire circumference; stock E84 Radumfang = 2003 mm @ 0x191404). Upshift/downshift lines come in hysteresis pairs; close the gap too much and the box hunts.

Key differences from the E70:

| | E70 (8646496) | E84 (8609556) |
|---|---|---|
| Characteristics | 23 (char 00..22) | **21 (char 00..20)** |
| Char numbering | ROM-pointer-table order (chars scattered in memory) | **memory order** — char N sits at base + N·stride, because the ROM pointer tables live in the missing program region |
| "Shift disabled" sentinel | 8000 | **8200** |
| 1>2..5>6 blocks | 0x1CF21A.. (per-char bases, unordered) | contiguous from **0x1DBA68**, 300 B/char |
| Pedal axes | 0x1CC1CC, 32 B stride | **0x1D8FA8**, 32 B stride |
| Char-to-axis pairing | HIGH (pointer tables 0x5A47C/0x5A984) | **positional, LOW** (no program ROM) |

**E84 char NN is NOT the same driving situation as E70 char NN.** The numbering here is nothing but address order; the E70 numbering came from ROM pointer tables that don't exist in this calibration-only read. Which characteristic maps to which drive mode (D/S/M, Sport button, warm-up, …) lives in the missing program ROM for both cars — on the E84 doubly so. **Identify the active characteristic by logging before you retune it.**

The read itself: the E84 image is **calibration-only** — a 2 MB file where everything below 0x180200 is erased 0xFF. All code-level statements (record grammars, how the strategy state selects a characteristic) inherit from the E70 RE (same Bosch iTCU2 / SH-2A family, earlier 2012-generation software). The XDF exposes the same flash bytes twice — multi-column blocks per characteristic and individual per-gear-pair curves. Overlapping views of identical data; edit whichever is convenient, not both.

## Memory map

Everything lives in one contiguous run **0x1DBA68–0x1DDCDB** (plus the pedal axes at 0x1D8FA8). All values u16 big-endian. Verified: the stride math below reproduces every z-address in the XDF exactly, for all 21 characteristics.

| Region | Base | Stride | Span | Contents |
|---|---|---|---|---|
| 1>2..5>6 blocks | **0x1DBA68** | 300 B (0x12C) per char | 0x1DBA68–0x1DD303 | five 60-byte gear-pair stripes per char |
| 6>7 / 7>6 pairs | **0x1DD304** | 60 B (0x3C) per char | 0x1DD304–0x1DD7EF | one stripe per char |
| 7>8 / 8>7 pairs | **0x1DD7F0** | 60 B (0x3C) per char | 0x1DD7F0–0x1DDCDB | one stripe per char |
| Pedal axes | **0x1D8FA8** | 32 B (0x20) per char | 0x1D8FA8–0x1D9247 | `{u16 n = 15; u16 v[15]}` per char |

The three shift-line regions butt up against each other: the 1>2..5>6 blocks end at 0x1DD303 and the 6>7 slots start at 0x1DD304; 6>7 ends at 0x1DD7EF and 7>8 starts at 0x1DD7F0.

**Stripe layout** (every gear pair, everywhere): 60 bytes = **15 u16 upshift column, then 15 u16 downshift column**. So within any stripe, `downshift slot = upshift slot + 30 (0x1E)`.

**Address formulas** (char N = 0..20, gear pair k = 0..4 for 1>2..5>6):

```
up  (k+1)>(k+2)  = 0x1DBA68 + N*300 + k*60
dn  (k+2)>(k+1)  = 0x1DBA68 + N*300 + k*60 + 30
up  6>7          = 0x1DD304 + N*60
dn  7>6          = 0x1DD304 + N*60 + 30
up  7>8          = 0x1DD7F0 + N*60
dn  8>7          = 0x1DD7F0 + N*60 + 30
pedal axis       = 0x1D8FA8 + N*32   (count u16 = 15, values at +2)
```

Worked check, char 00 (all addresses straight from the XDF): 1>2 @0x1DBA68, 2>3 @0x1DBAA4, 3>4 @0x1DBAE0, 4>5 @0x1DBB1C, 5>6 @0x1DBB58, 6>7 @0x1DD304, 7>8 @0x1DD7F0; downshifts 2>1 @0x1DBA86, 3>2 @0x1DBAC2, 4>3 @0x1DBAFE, 5>4 @0x1DBB3A, 6>5 @0x1DBB76, 7>6 @0x1DD322, 8>7 @0x1DD80E; pedal axis values @0x1D8FAA. Char 01 block @0x1DBB94 (= 0x1DBA68 + 0x12C), char 15 1>2 @0x1DCBFC, char 20 block @0x1DD1D8.

**Sentinel: 8200 = shift disabled** at that pedal point (the E70 used 8000; both are above the `>= 7900` cutoff the repo tools treat as "don't touch"). In the stock-shape E84 schedule every 8200 in the shift-line regions sits in the 7>8/8>7 region — several characteristics disable the 7>8 upshift at high pedal. Confidence: **HIGH** (136 occurrences counted in the repo image, zero occurrences of 8000).

Confidence for the whole map: **HIGH** for layout (native structure walk, record grammar from the E70 decompile, every address cross-checked against the image), **LOW** for which characteristic is which (see below).

### Shift lines: upshift

**`Upshift lines, char NN: 1>2..5>6`** (21 tables, 5×15), **`... 6>7`**, **`... 7>8`** (21 × 1×15 each) — 63 tables, z = output rpm, rows = 15 pedal breakpoints, columns = gear pairs. Raising values holds gears longer. The E70 had 69 (23 chars); the 6 "char 21/22" tables have no E84 counterpart — the E84 simply has 21 characteristics, nothing was lost in the port.

### Shift lines: downshift

**`Downshift lines, char NN: 2>1..6>5` / `7>6` / `8>7`** — 63 tables, the mirror image at upshift slot + 30 B. Raising values makes the box kick down earlier. Same counts as upshift (E70: 69 across 23 chars; E84: 63 across 21).

### Shift lines: single curves

**`Upshift char NN: G>G+1` / `Downshift char NN: G+1>G`** — 294 tables (14 gear pairs × 21 chars), 15×1 views of exactly the same flash bytes as the blocks (E70 had 322 across 23 chars). A change made in a single curve shows up in the corresponding block and vice versa. The tools' shift-line subcommands (below) iterate these, deduplicating by address.

Caveat: some single-curve and block *descriptions* in `8hpe84_cali_v1.xdf` still carry E70 wording — "8000 = disabled" and "pedal axis @0x1cc1cc" are E70 leftovers in the inherited text. The appended `|| E84 8609556: native slot ...` note and the **embedded addresses** (which is what TunerPro and the tools actually use) are the E84 truth. Trust the addresses and this chapter, not 0x1CCxxx strings in description prose. The value strings quoted in the "Pedal axis, char NN" descriptions ("= 0 100 250 300 ...") are likewise E70 values - the E84 bytes at the embedded address (e.g. 0 250 350 400 450 ... for char 00) are what the TCU uses and what this chapter tabulates.

### Shift lines: pedal axes

**`Pedal axis, char NN`** (char 00..20) — 21 tables, 15×1 u16, per mille, 1100 = kickdown. Stored `{u16 n = 15; u16 v[15]}` at **0x1D8FA8 + N·32** (char 00 values @0x1D8FAA, char 20 @0x1D922A); the 30-byte value array plus 2-byte count fills the 32-byte stride exactly, no padding. The count field reads 15 for all 21 axes in the image. Changing an axis re-maps the pedal breakpoints of **every shift line in that characteristic at once**; breakpoints must stay monotonically increasing.

In the repo read (`WBAUU3C59AA541121_GKE233_8609556_0479U10K791Z_tune.bin` — note the `_tune` suffix: this is the car's current state, so axis values may already reflect the installed tune rather than factory bytes) the 21 axes fall into **four distinct value sets**:

| Chars | Axis values (per mille) |
|---|---|
| 00–05, 10–14, 17–20 | 0 250 350 400 450 500 620 640 700 800 820 980 985 1000 1100 |
| 06, 07, **15, 16** | 0 40 45 250 350 450 470 600 620 800 820 980 985 1000 1100 |
| 08 | 0 100 150 300 350 450 470 600 620 800 820 980 985 1000 1100 |
| 09 | 0 40 45 300 350 450 470 600 620 800 820 980 985 1000 1100 |

## The positional axis-pairing caveat

On the E70, which pedal axis belongs to which characteristic block was read out of the ROM pointer tables (HIGH). The E84 read has no program ROM, so the XDF pairs **axis N with block N positionally** — both regions are laid out in the same memory order and have the same count, which makes positional pairing the obvious guess, but it is **LOW confidence**. What this does and doesn't affect:

- **z-value edits are always safe**: a shift-line slot's bytes are what they are regardless of which axis the XDF displays next to them.
- **Displayed pedal breakpoints may be wrong** for some characteristics — a line you think bends at 450‰ might really bend at 470‰. This also means pedal-conditional tooling (`sport-redline --pedal-from`) picks its cells by the *displayed* axis.
- **Axis edits are the risky case**: if the pairing is wrong, editing "char 05's axis" re-maps some *other* characteristic's lines. Don't retune axes until the pairing is confirmed by logging (change one axis, observe which drive mode's shift feel moves).

## Chars 15 and 16: empty 1>2 stripes

Blocks 15 and 16 have **all-zero 1>2 and 2>1 stripes** (verified: all 30 values are 0x0000 in each), while their 2>3 through 7>8 lines are fully populated and identical to each other except in 6>7/7>8. Zero is not the disable sentinel (that's 8200), so these two characteristics simply don't carry a live 1>2 line — consistent with **manual-mode characteristics**, where the 1>2 decision is driver-commanded (LOW confidence interpretation; the selection logic is in the missing program ROM). Both sit on the same "0 40 45 250 …" pedal-axis set as chars 06/07 under the positional pairing. Practical upshot: a blanket edit across "all characteristics" that writes into zero cells would invent a 1>2 line where none existed — the repo tools skip cells with `v <= 0` for exactly this reason.

Related: **`[PATCH] Start in 2nd (E84) [PARTIAL]`** in the XDF zeroes all 21 chars' 1>2/2>1 stripes (44 entries, 0x1E bytes each, starting char00_up @0x1DBA68 / char00_dn @0x1DBA86) — i.e. it makes every characteristic look like chars 15/16 do natively. It is PARTIAL: the E70 version also wrote 49 auxiliary inhibit/min-speed entries that could not be located in the E84 cal, so behaviour may differ.

## Port coverage (vs the E70 XDF)

Per the port report — "native" means rebuilt from E84 structure, "dropped" means the E70 item has no E84 counterpart (here: only because the E84 has 21 characteristics, not 23; nothing in this chapter needs the full flash read):

| Category | E70 total | ported | native | dropped |
|---|---|---|---|---|
| Shift lines: upshift | 69 | 0 | 63 | 6 (char 21/22) |
| Shift lines: downshift | 69 | 0 | 63 | 6 (char 21/22) |
| Shift lines: single curves | 322 | 0 | 294 | 28 (char 21/22) |
| Shift lines: pedal axes | 23 | 0 | 21 | 2 (char 21/22) |

## Worked example: retuning the E84 schedule with xdf_tune

`tools/xdf_tune.py` resolves the XDF automatically (prefers `8hpe84_cali_v1.xdf`), never edits in place, and skips sentinel (`>= 7900`, so both 8000 and 8200) and zero cells. **The E70 checksum algorithm does not reproduce on the E84 read** — `xdf_checksum.py` search fails on it — so don't try to sign locally; flash with a tool that corrects checksums itself (xHP does).

Rev 1st and 2nd out to 7000 rpm, but only from 400‰ pedal up so light-throttle shifts stay stock:

```
$ tools/xdf_tune.py sport-redline WBAUU3C59AA541121_GKE233_8609556_0479U10K791Z_tune.bin \
      -o e84_sport.bin --rpm 7000
sport-redline 7000 rpm from pedal 400: targets (output rpm) {'1>2': 1455, '2>3': 2183}; 454 cells raised
```

The targets are `rpm × (1 − margin) / gear ratio` with the 8HP45 ratios (1st 4.714, 2nd 3.143) and the default 2 % margin: 7000 × 0.98 / 4.714 ≈ 1455 output rpm. Defaults: `--rpm 7000`, `--pedal-from 400` (0 = everywhere), `--chars` limits which characteristics are touched (e.g. `--chars 8,9` once logging has identified the sport characteristic — default is all 21, which is the safe-but-blunt choice while the mapping is unknown). Before/after on char 00:

```
$ tools/xdf_show.py 8hpe84_cali_v1.xdf <bin> "Upshift char 00: 1>2"
     0  250  350  400  450  500  620  640  700  800  820   980   985  1000  1100
-  300  300  300  350  400  450  550  575  675  925  975  1050  1050  1050  1050   (before)
-  300  300  300 1455 1455 1455 1455 1455 1455 1455 1455  1455  1455  1455  1455   (after)
```

Cells below 400‰ untouched; everything from the 400‰ breakpoint up raised to the 1455-rpm target (cells already above the target would be left alone). 7000 rpm clears the ~7100 rpm stock TCU guard, so no "True manual" overspeed patch is needed — which is just as well, since that patch did not survive the port (6 of 7 entries unresolvable, including all overspeed limits: **not in the E84 XDF, needs a full flash read**). The tool warns if you pass `--rpm` above 7100.

Chain a shift-offset on top — e.g. hold 6th and 7th 150 rpm longer (hysteresis is preserved because the matching downshift lines are dragged along by default; `--no-down` to pin them):

```
$ tools/xdf_tune.py shift-offset e84_sport.bin -o e84_final.bin --rpm +150 --pairs '6>7,7>8'
shift-offset +150 rpm: 1063 cells changed
```

(1063 = 21 chars × 2 pairs × 2 directions × 15 cells = 1260, minus the 136 sentinel-8200 cells and 61 cells at 8150, which sit above the tools' `>= 7900` don't-touch cutoff.) Then flash `e84_final.bin` via xHP (checksums corrected there), and log to confirm which characteristic your drive mode actually runs before doing anything surgical per-characteristic.

Coverage: all 441 E84 items in this group (7 families): upshift blocks 3×21 = 63, downshift blocks 3×21 = 63, single curves 2 families (147 + 147 = 294), pedal axes 1×21 = 21.
