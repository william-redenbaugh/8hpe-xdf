# Shift lines (shift schedule)

This is the heart of the shift schedule: the tables that decide *when* the 8HP changes gear. For every gear pair (1>2 up through 7>8, and 2>1 down through 8>7) the TCU stores a **shift line**: the output-shaft speed (rpm) at which the shift is requested, looked up over accelerator-pedal position. Pedal position is in per mille (0–1000, with **1100 = kickdown**), and the speed values are **output-shaft rpm, not road speed** — convert with your final-drive ratio and tire circumference when planning changes. A value of **8000 rpm means "shift disabled"** at that pedal point. Upshift and downshift lines come in pairs with deliberate hysteresis between them: the downshift line for a gear pair sits below the upshift line, so the box doesn't hunt between gears when you hold a steady speed near a shift point.

The whole schedule exists in **23 parallel "characteristics"** (char 00..22) — complete copies of all 14 shift lines plus their own pedal breakpoint axis — and the TCU selects one at runtime from the **strategy state** (the shift-strategy logic — in the 8HP this typically reacts to drive mode, driving style, and conditions, though the RE evidence here only establishes *that* the selection comes from the strategy state). The RE evidence pins down the *layout* with HIGH confidence (slot geometry verified against the ROM pointer tables at 0x5A47C/0x5A984), but **which characteristic number corresponds to which driving situation is only MED confidence** — identify the active characteristic by observation/logging before you retune it. Note the XDF exposes the same flash bytes twice: once as multi-column blocks per characteristic, and once as individual per-gear-pair curves. These are overlapping views of identical data — edit whichever is more convenient, not both.

### Shift lines: upshift

**Upshift line blocks, char 00..22** — 69 tables (3 per characteristic × 23 characteristics), u16 big-endian, z = output rpm, rows = 15 pedal breakpoints (live axis per characteristic, base 0x1CC1CC), columns = gear pairs.

| Member pattern | Count | Shape | Covers | Address scheme |
|---|---|---|---|---|
| `Upshift lines, char NN: 1>2..5>6` | 23 | 5×15 | gears 1>2, 2>3, 3>4, 4>5, 5>6 | block base (per char, see table below) + k·60 per gear pair |
| `Upshift lines, char NN: 6>7` | 23 | 1×15 | gear 6>7 | separate slot (char 00: 0x1D11FA) |
| `Upshift lines, char NN: 7>8` | 23 | 1×15 | gear 7>8 | separate slot (char 00: 0x1D175E) |

Each slot is 15 u16 (30 B); the up and down slots of one gear pair alternate, **downshift slot = upshift slot + 30 B**. The 1>2..5>6 slots step by 60 B per gear pair within a characteristic's block. The 6>7 and 7>8 lines live in their own regions higher up (6>7 slots at 0x1D0D0E–0x1D1236, 7>8 slots at 0x1D1272–0x1D179A); entire group spans 0x1CF21A–0x1D179A. Raising values here holds gears longer (later upshifts); 8000 disables the upshift at that pedal point. Confidence: **HIGH** for layout, **MED** for which characteristic is which.

Characteristic block base addresses (upshift 1>2 slot; the chars are *not* stored in numeric order — order comes from the ROM pointer tables):

| char | base | char | base | char | base |
|---|---|---|---|---|---|
| 00 | 0x1D0AB6 | 08 | 0x1D0156 | 16 | 0x1D0606 |
| 01 | 0x1CF922 | 09 | 0x1CFEFE | 17 | 0x1CF7F6 |
| 02 | 0x1CFDD2 | 10 | 0x1D0282 | 18 | 0x1CF6CA |
| 03 | 0x1D0BE2 | 11 | 0x1D04DA | 19 | 0x1D0732 |
| 04 | 0x1CF21A | 12 | 0x1CFCA6 | 20 | 0x1D098A |
| 05 | 0x1CF346 | 13 | 0x1D085E | 21 | 0x1CFA4E |
| 06 | 0x1CF472 | 14 | 0x1CF59E | 22 | 0x1CFB7A |
| 07 | 0x1D03AE | 15 | 0x1D002A | | |

### Shift lines: downshift

**Downshift line blocks, char 00..22** — 69 tables, the mirror image of the upshift blocks: output-shaft rpm at which the downshift is requested, over the same per-characteristic pedal axis. Same encoding (u16 BE, per mille pedal, 1100 = kickdown, 8000 = disabled).

| Member pattern | Count | Shape | Covers | Address scheme |
|---|---|---|---|---|
| `Downshift lines, char NN: 2>1..6>5` | 23 | 5×15 | gears 2>1, 3>2, 4>3, 5>4, 6>5 | upshift block base + 0x1E, + k·60 per gear pair |
| `Downshift lines, char NN: 7>6` | 23 | 1×15 | gear 7>6 | upshift 6>7 slot + 0x1E (char 00: 0x1D1218) |
| `Downshift lines, char NN: 8>7` | 23 | 1×15 | gear 8>7 | upshift 7>8 slot + 0x1E (char 00: 0x1D177C) |

Group spans 0x1CF238–0x1D17B8. Raising downshift values makes the box kick down earlier (more eager); the gap between a gear pair's downshift and upshift lines is the shift hysteresis — close it too much and the transmission will hunt. Confidence: **HIGH** layout, **MED** characteristic mapping.

### Shift lines: single curves

**Per-gear-pair single curves, char 00..22** — 322 tables (14 gear pairs × 23 characteristics), 15×1 u16 each, x = accel pedal per mille (per-characteristic axis), z = output rpm, 8000 = disabled. These are **one-column views of exactly the same flash bytes as the blocks above**, provided so you can graph/edit one shift line at a time in TunerPro. Two member patterns:

| Family | Members | Gear pairs | Address rule |
|---|---|---|---|
| `Upshift char NN: G>G+1` | 7 × 23 = 161 | 1>2, 2>3, 3>4, 4>5, 5>6, 6>7, 7>8 | same slot addresses as the blocks: char base + k·60 for 1>2..5>6; own slots for 6>7, 7>8 |
| `Downshift char NN: G+1>G` | 7 × 23 = 161 | 2>1, 3>2, 4>3, 5>4, 6>5, 7>6, 8>7 | matching upshift slot + 30 B |

For char 00 the slots are: 1>2 @0x1D0AB6, 2>3 @0x1D0AF2, 3>4 @0x1D0B2E, 4>5 @0x1D0B6A, 5>6 @0x1D0BA6, 6>7 @0x1D11FA, 7>8 @0x1D175E (each downshift = +0x1E). For 1>2..5>6 the other characteristics follow the base-address table above; the 6>7 and 7>8 slots have their own per-characteristic addresses (take them from the XDF item itself). Group spans 0x1CF21A–0x1D17B8. Because they alias the blocks, a change made in a single curve shows up in the corresponding block and vice versa. Confidence: **HIGH** layout, **MED** characteristic mapping.

### Shift lines: pedal axes

**Pedal breakpoint axes** (`Pedal axis, char NN`, char 00..22) — 23 tables, 15×1 u16, the accelerator-pedal breakpoints (per mille, 1100 = kickdown) that all 14 up- and downshift lines of one characteristic are interpolated over. Stored as `{u16 n = 15; u16 v[15]}` with a **32-byte stride from 0x1CC1CC** (value arrays 0x1CC1CE..0x1CC48E); layout taken from the ROM pointer tables 0x5A47C/0x5A984 and verified in the image. The axes are *live* (read at runtime), and they differ between characteristics — e.g. char 00 uses `0 100 250 300 350 450 470 650 670 800 820 980 985 1000 1100` while chars 05/22 and others concentrate points low in the pedal range (`0 40 45 250 ...`); the 23 axes fall into seven distinct value sets. Changing an axis re-maps the pedal breakpoints of **every shift line in that characteristic at once**, and the breakpoints must stay monotonically increasing. Confidence: **MED** (axis-to-characteristic order is structural; the values are read live).

Coverage: Covers all 483 items in this group (9 families): upshift blocks 3×23 = 69, downshift blocks 3×23 = 69, single curves 2 families (161 + 161 = 322), pedal axes 1×23 = 23.
