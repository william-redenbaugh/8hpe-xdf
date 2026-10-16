# ZF 8HP (E70) TCU calibration definition

A TunerPro XDF for the ZF 8HP E-series transmission controller (Bosch iTCU2, SH-2A, big-endian),
plus a small Python tool that raises shift pressure and a checker that proves a modified binary is
safe to flash.

**Target: E70, calibration ZB 8646496.** Nothing else is supported.

The XDF contains independently reverse-engineered *descriptive metadata* — addresses, data types,
scaling and labels. It contains no vendor firmware and no calibration data. You supply the
calibration read yourself: a 2 MB image whose calibration block is `0x180200`–`0x1FFFFF`, where
addresses in the XDF are file offsets.

## Files

| | |
|---|---|
| `8hpe70_cali_v3.xdf` | The definition. Open it in TunerPro with your own read. |
| `tools/xdf_stage3.py` | Raise shift pressure using the maps a stage-3 tune touches. |
| `tools/xdf_verify.py` | Prove a modified bin changes nothing it shouldn't. Run before flashing. |
| `tools/xdflib.py` | The XDF parser both tools use. |

Dependency-free Python 3. On macOS use `/usr/bin/python3` — some Homebrew builds ship a broken
`pyexpat`, which `xdflib` works around with its own parser, but the system Python avoids the issue
entirely.

## Raising shift pressure

More shift pressure applies the clutch harder, so the shift is shorter and firmer.

```sh
cd tools
python3 xdf_stage3.py /path/to/stock.bin --preview            # show what would change
python3 xdf_stage3.py /path/to/stock.bin -o tuned.bin         # sport, +8%
python3 xdf_stage3.py /path/to/stock.bin -o tuned.bin --level max   # +14%
python3 xdf_stage3.py /path/to/stock.bin -o tuned.bin --pct 6       # exact amount
```

Levels are `mild` (+4%), `sport` (+8%, default) and `max` (+14%).

It edits the eight `shift_press_map_b*` maps from the XDF's **stage 3** category — the folder that
collects the maps a commercial XHP-style stage-3 calibration modifies.

**What keeps this safe.** Those maps are rated **LOW confidence**: a stage-3 tune demonstrably
rewrites them, but their row/column meaning is not proven by the reverse engineering behind this
definition. So a cell is only ever raised *towards the largest value that same map already
contains* — never past a pressure ZF itself commands somewhere in that map. That is why there is no
unlimited setting, and why `--pct` stops at 50.

## Before you flash

```sh
python3 xdf_verify.py ../8hpe70_cali_v3.xdf stock.bin tuned.bin
```

It fails unless every changed byte lands inside a table the XDF describes, and it additionally
refuses a bin that touches the program region, the calibration header, the `ZFADINFO` identification
block or the signature tail, or that leaves a pedal axis decreasing. A clean run prints `PASS`.

Checksums are **not** handled here. Sign the image with your flash tool (xHP corrects checksums
itself) after any edit.

## Caveats

- Work on a copy of your stock read. Keep the original.
- The tool writes raw values and corrects no checksum; it is not a substitute for knowing what you
  are changing.
- `xdf_verify.py` proves a bin is *structurally* sound — that it only altered bytes this definition
  accounts for. It cannot tell you whether the resulting calibration is good for your car.

## Licence

See `LICENSE`.
