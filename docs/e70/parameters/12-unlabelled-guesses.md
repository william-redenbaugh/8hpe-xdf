# Educated guesses for the unlabelled parameters

The XDF carries 2,609 items whose meaning the reverse engineering never
analysed (the `auto_*` structures plus the provisional `Unlabelled: <subsystem>`
items). This chapter assigns each one an **educated guess** — and is explicit
that that is all it is. Every guess here is **SPECULATIVE**: weaker than the
XDF's own LOW confidence, because nothing below comes from decompiled readers
or object matches. Use it to decide *where to look next*, never to tune.

The complete per-item table is
[docs/data/unlabelled-guesses.csv](../data/unlabelled-guesses.csv) — one row
per item with its address, structure, shape, value ranges, nearest labelled
neighbours, the per-item signal guess, and the cluster interpretation.

**The guesses are also embedded in the XDF itself**: every unlabelled item's
description in `8hpe_cali_v3.xdf` ends with a `SPECULATIVE GUESS (…)` sentence
carrying its guess and cluster interpretation, so TunerPro and the GUI show
them in place (`tools/annotate_xdf.py` wrote them and can re-apply after the
CSV is regenerated).

## How the guesses were made

Three mechanical signals, combined per item:

1. **Address clustering.** Sorted by flash address, the unlabelled items fall
   into 33 clusters (gap threshold 0x300). Calibration data for one function
   is laid out contiguously, so a cluster bracketed by labelled items of one
   subsystem almost certainly belongs to that subsystem.
2. **Nearest labelled neighbours.** For each cluster, the closest labelled
   item before and after it (with its documented category) anchors the
   subsystem guess.
3. **Axis-signature classification.** The auto-scan recorded each structure's
   x and z value ranges. Ranges are distinctive: `-30..150` is an oil/coolant
   temperature axis, `0..7000` a shaft speed, `0..1000/1100` the accelerator
   pedal in per mille (1100 = kickdown), `1..8` a gear index, symmetric
   `-n..+n` a slip/gradient/error input, `z = 0..0` an unused or disabled
   slot. These give the "input looks like / output looks like" guesses.

What this cannot do: identify *which* copy/variant a table is, prove units,
or distinguish a live table from a dead one the code never reads. 40 items
(mostly isolated singletons) got no cluster interpretation at all.

## The clusters

Interpretations for every cluster of 8+ items (covering ~2,520 of the 2,609).
Address spans are the first..last item start addresses.

| Cluster | Span | Items | Dominant types | What it most likely is |
|---|---|---|---|---|
| 1 | 0x19092E–0x1916E0 | 19 | s16 curves | TCC slip-controller / shift-program CAL-block auxiliaries — signed-error inputs with pressure-scale outputs, sitting between the `tccslip` pointer block and the shift-program parameter area |
| 8 | 0x197094–0x1994D8 | 113 | s16 curves+maps | Adaptation scoring and engine-time compensation support, across the adaptation fill/shift area (0x198xxx); many warm-temperature inputs and constant-90 percent outputs |
| 9 | 0x199928–0x19A174 | 18 | s16 maps | Torque/converter model support — surrounds the `tcmodel_K_curve`/`tcmodel_mu_curve` pair (0x1999B0/0x1999E4) and the torque-loss blend; rpm × torque inputs |
| 10 | 0x19A7BC–0x19AED4 | 35 | s16 curves | Torque-signal conditioning and limits, after the per-gear `trqloss` maps and before the neutral-idle torque limit; several constant-10000 ceilings |
| 12 | 0x19B628–0x1A125C | 157 | f32 maps, s16 | Neutral-idle and TCC slip/pressure support. Includes the five unlabelled 6×6 f32 maps at 0x1A0754–0x1A0C04 that very likely complete the slip-PID gain family around `tcc_slip_pid_gain_e4`/`_ec` |
| 13 | 0x1A1574–0x1A5B6E | 216 | s16+f32 maps | TCC pressure/phase data transitioning into the shift-execution region (starts right at `tcc_slip_target_map`); rpm × torque inputs, percent outputs |
| 15 | 0x1A6746–0x1AE904 | 558 | u8 curves+maps | **Shift-execution timing/trim family members** — the per-gear-pair, per-variant-block (k0..k3) copies that were never individually labelled; torque-indexed u8 times/factors exactly like their labelled `shiftexec_*` siblings around them |
| 16 | 0x1AF8F0–0x1B29F4 | 304 | u8, s16 | Downshift execution and base-pressure support, between the execution state tables and the `b_dn` base-pressure maps |
| 17 | 0x1B2D24–0x1B6218 | 116 | s16 curves+maps | Shift-pressure class/gear-pair tables inside the `b_dn`/`b_up` base-pressure region; about a third are all-zero (unused slots) |
| 18 | 0x1B6588–0x1C2D20 | 683 | s16+u8 | **The bulk: shift-pressure phase tables** — per-phase, per-class (`c0..c2`), per-gear-pair pressure/time members of the same families as the labelled `shift_press_*` items that bracket them; torque-indexed, u8 times and raw pressure scales |
| 19 | 0x1C31CC–0x1C4630 | 44 | u8, s16 | Downshift phase pressure/time members (inside the dn ph11 / trq_add region) |
| 20 | 0x1C4BF4–0x1C7BD4 | 192 | s16 curves | Downshift pressure tail plus ratio-monitoring lead-in; many all-zero slots |
| 21 | 0x1C8120–0x1C9198 | 45 | s16 | Ratio-monitoring / strategy-state boundary data, between `ratio_mon_lower_band_map_set8` and `strat_state_attr_2` |
| 22 | 0x1CAF74–0x1CB2FA | 20 | (headers) | Strategy pedal-condition records — pedal-permille inputs with 32000 sentinels, directly before the `shift_type_cond_records` at 0x1CB340 |
| 25 | 0x1CC6CE–0x1CCB6E | 10 | (headers) | Unused/padding shift-line slots (all-zero, after the char-22 pedal axis) |
| 28 | 0x1CDE08–0x1CED90 | 30 | (headers) | Gear-selection speed/torque thresholds, between `shift_type_by_gear` and the torque-headroom curves; near the car-2nd minimum-speed words at 0x1CD938 |
| 29 | 0x1D1FBC–0x1D2496 | 9 | (headers) | Strategy gear-limit curves, beside the multi-downshift pedal curves |

The remaining small clusters (and the 40 items with no interpretation) are
isolated structures whose only guess is their nearest neighbour, recorded
per item in the CSV.

## What stands out

- **Most "undocumented" items are extra members of documented families.** The
  two giant clusters (15 and 18, together 1,241 items — nearly half the
  unlabelled set) sit inside the shift-execution and shift-pressure regions
  and have the same shapes, data types, and torque-indexed axes as the
  labelled tables around them. They are almost certainly the per-gear-pair /
  per-class / per-variant copies the RE labelled only partially.
- **The TCC slip-PID family is probably larger than labelled.** The six
  unlabelled 6×6 f32 maps at 0x1A07xx–0x1A0C94 match `tcc_slip_pid_gain_e4`/
  `_ec` in shape, type and location — relevant if you tune TCC behaviour
  (see the [N52K notes](../analysis/n52k-tcc-optimization.md)).
- **A lot of it is dead weight.** Hundreds of structures are all-zero or
  constant (disabled features, unused slots, padding) — the scanner recorded
  them, but there is likely nothing behind them to find.

## How to firm a guess up

1. Read the item's row in the CSV: neighbours, shape, ranges.
2. Dump its values from a real bin: `tools/xdf_show.py 8hpe_cali_v3.xdf
   my_read.bin auto_<addr>` — a live table has plausible, smooth data.
3. Diff against a differently-optioned factory calibration (`tools/
   xdf_diff.py`) — tables that vary across versions are live calibration.
4. The real proof is a reader function in the disassembly; until then, treat
   every entry in this chapter as a hypothesis.
