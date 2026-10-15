# Parameter reference — 8HP E-series XDF (ZB 8646496)

What every parameter in `8hpe_cali_v3.xdf` is, organised by subsystem. The XDF
defines **4,252 tables, 17 constants and 2 clickable patches** in 52 TunerPro
categories, produced by static reverse engineering of the ZF 8HP E-series TCU
(Bosch ITCU2, SH-2A) calibration.

## How to read this reference

- **Addresses** are flash addresses, which equal file offsets in the required
  2 MB image (calibration block `0x180200–0x1FFFFF`). All multi-byte values
  are **big-endian**, and all values are **raw** — physical units (bar, Nm)
  are only claimed where the RE evidence proved them.
- **Confidence levels** come from the XDF itself and are preserved honestly:
  - **HIGH** — layout *and* use proven (decompiled reader function, or
    geometry verified against ROM pointer tables).
  - **MED** — solid structural evidence (byte-identical object match against
    a labelled reference build, cross-version variation) but meaning or units
    not fully proven.
  - **LOW** — auto-detected structure or positional inference only. Treat as
    a hypothesis; don't tune against it.
- Repetitive families (the 23 shift characteristics, per-gear-pair copies,
  `set0..set8` blocks, `_c0/_c1/_c2` class variants) are documented **once**
  as a family with the member pattern and address scheme, not as hundreds of
  rows. Every one of the 4,271 items is accounted for in exactly this way —
  each chapter ends with a coverage statement.
- Many parameters exist in several runtime-selected copies (characteristic,
  set, class). A change only works if you edit **the copy the TCU is actually
  using** — or all copies consistently. Where the selector is unproven, the
  chapter says so.

## Chapters

| # | Chapter | Items | What's in it |
|---|---|---|---|
| 1 | [Shift lines (shift schedule)](01-shift-lines.md) | 483 | When the box shifts: up/down shift lines over pedal × output speed, 23 switchable characteristics, pedal breakpoint axes |
| 2 | [Shift strategy](02-shift-strategy.md) | 88 | Which schedule/program is active: the ~100-state strategy machine, characteristic selection, gear limits, sport functions, driver detection |
| 3 | [Shift pressure](03-shift-pressure.md) | 420 | How firmly clutches are pressed during shifts: torque→pressure base maps, phase pressures, oil-temperature compensation, torque limits |
| 4 | [Shift execution](04-shift-execution.md) | 279 | How a shift unfolds in time: phase durations, ramps, overlap, rev-match blip |
| 5 | [Shift elements](05-shift-elements.md) | 54 | Per-clutch/brake (A–E) engagement: fill pressure/time, torque→pressure authority, protection |
| 6 | [Torque converter](06-torque-converter.md) | 62 | TCC lock-up & slip control: slip targets, PID gains, apply pressures, converter model |
| 7 | [Adaptation](07-adaptation.md) | 52 | The rules of self-learning: when adaptation runs, step sizes, clamp limits |
| 8 | [Standstill & gear-ratio monitoring](08-standstill-ratio-monitoring.md) | 74 | Neutral-idle/standstill decoupling, and the ratio-plausibility bands behind slip fault detection |
| 9 | [Signals & diagnosis](09-signals-diagnosis.md) | 167 | Input conditioning: speed/torque/temperature models, drag-torque losses, monitoring thresholds |
| 10 | [Patches, Stage 3 & additional maps](10-patches-stage3.md) | 131 | The two `[PATCH]` items (Start in 2nd, True manual), the Radumfang constant, the stage-3 map list, tune-touched extras |
| 11 | [Unlabelled structures](11-unlabelled.md) | 2,461 | Auto-detected curves/maps whose meaning is not yet analysed — reference material, do not edit |

Counts sum to 4,271 (items that appear in two categories — e.g. the stage-3
duplicates — are counted in each chapter that documents them).

## Deep dives

- [TCC lock-up behaviour, in depth](../analysis/tcc-lockup.md)
- [Sensor/monitoring faults during manual shifting](../analysis/manual-shift-sensor-faults.md)
- [Optimizing the torque converter for an N52K (NA) swap](../analysis/n52k-tcc-optimization.md)

## Where this came from

The XDF embeds, in every item description, the address, structure, confidence
and RE evidence (reader functions from decompilation, byte-identical object
matches against a labelled reference build, cross-version comparisons across
21 factory calibrations). This reference was compiled from those descriptions;
nothing here is based on vendor documentation, and nothing here contains
vendor data. When this reference and the XDF item description disagree, trust
the XDF description and please open an issue.
