# ZF 8HP (E70) TCU calibration definition

A TunerPro XDF for the ZF 8HP E-series transmission controller (Bosch iTCU2, SH-2A, big-endian),
plus a small Python tool that raises shift pressure and a checker that proves a modified binary is
safe to flash.

**Target: one specific calibration — `TYPTEILENR b5yc1111`, cal-ID `C118`.** Nothing else is
supported, and both tools now refuse to run against anything else.

This matters more than it sounds. Every address in this XDF exists in *any* 2 MB image, so pointed
at the wrong calibration the tools would read and write perfectly "valid-looking" bytes that in
fact mean something else entirely. Check yours before anything else:

```sh
python3 -c "b=open('your.bin','rb').read(); print(b[0x180224:0x18022C], b[0x1FFD60:0x1FFD64])"
# must print  b'b5yc1111' b'C118'
```

If it prints something else — `b5yc1313`/`C138`, for instance — this definition is **not** for your
car and you need one built for your own calibration.

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
| `tools/xdf_gui.py` | The same thing with a window; start it with `./run.sh`. |
| `tools/xdflib.py` | The XDF parser the tools share. |

Dependency-free Python 3. On macOS use `/usr/bin/python3` — some Homebrew builds ship a broken
`pyexpat`, which `xdflib` works around with its own parser, but the system Python avoids the issue
entirely.

## The GUI

```sh
./run.sh
```

Then **Open bin...**, pick a level or an exact percentage, **Preview** to see what would change,
**Apply**, **Check bin**, and **Save As...**. Nothing is written to disk until you save, and
**Undo** steps back through every change. The calibration identity is checked the moment a bin is
opened and shown top-right; if it does not match, editing stays blocked.

`run.sh` picks a Python whose Tk actually works - Apple's `/usr/bin/python3` ships Tk 8.5, which
recent macOS refuses to start, so a Homebrew Python with `brew install python-tk` is preferred when
present.

## Raising shift pressure (command line)

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

**Read this before trusting it.** Those maps are rated **LOW confidence**, and the XDF's own
evidence line for them says *"Structure auto-detected by e_calscan.py … Meaning not analysed. Read
by: unknown."* Two things are therefore unproven:

- **That they are shift pressure at all.** The name came from a structural scanner, not from the
  firmware. The shape is consistent with it — 6×3 signed 16-bit, values 3500–19000 (plausible mbar)
  over an axis spanning 2000–7000 (plausible rpm) — but no reader function has been identified.
- **That an XHP tune changes them.** They sit in the XDF's `stage 3` category, documented as the
  list of maps such a tune touches, but this has not been checked byte for byte (see below).

**What is verified.** A cell is only ever raised *towards the largest value that same map already
contains*, so nothing is pushed past a value ZF itself writes somewhere in that map; and the edit
provably touches those eight maps and nothing else. That is why there is no unlimited setting and
why `--pct` stops at 50. Change it in small steps and check the car.

**Verifying against a real XHP tune.** To confirm the toggle changes only what XHP changes, two
files are needed *for the same calibration this XDF addresses*: a stock read and the XHP stage-3
version of it. Diff them, and compare the changed byte ranges with the toggle's. The off-the-shelf
tune available during development targeted a different calibration (`b0bc2323`, while this XDF
addresses `b5yc1111`), where the same addresses hold entirely different structures, so that
comparison was not possible.

## Before you flash

```sh
python3 xdf_verify.py ../8hpe70_cali_v3.xdf stock.bin tuned.bin
```

It fails unless the image is the calibration this XDF describes **and** every changed byte lands
inside a table the XDF describes. It additionally refuses a bin that touches the program region, the
calibration header, the `ZFADINFO` identification block or the signature tail, or that leaves a
pedal axis decreasing. A clean run prints `PASS`.

Two honest limits on what a `PASS` means. It says the edit was structurally contained; it cannot
say the calibration is good for your car. And if your read is calibration-only (everything below
`0x180200` is `0xFF` padding), the program-region check compares padding with padding and proves
nothing — the tool now says so rather than passing quietly.

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
