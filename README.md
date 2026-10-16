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
| `tools/xdf_gearbias.py` | Pick a higher (or lower) gear when you plant the throttle. |
| `tools/xdf_blip.py` | Blip the throttle harder on downshifts. |
| `tools/xdf_vehicle.py` | Wheel circumference and final drive — what a swapped or re-geared car must get right. |
| `tools/xdf_truemanual.py` | Apply or undo the XDF's `[PATCH] True manual`: no TCU-forced upshift at redline in M. |
| `tools/xdf_gui.py` | Shift pressure, wheel, differential and true manual in a window; start it with `./run.sh`. |
| `tools/xdflib.py` | The XDF parser the tools share. |

Dependency-free Python 3. On macOS use `/usr/bin/python3` — some Homebrew builds ship a broken
`pyexpat`, which `xdflib` works around with its own parser, but the system Python avoids the issue
entirely.

## The GUI

```sh
./run.sh
```

Seven panels, one per thing you might change:

| Panel | What it does |
|---|---|
| Shift pressure | Firmness, with converter lockup riding along at half strength |
| Shift points | When it shifts, **per drive mode** |
| Kickdown gear | Which gear a planted throttle drops to |
| Downshift blip | Rev-match blip strength (all modes) |
| Wheel circumference | Rolling circumference, from a tyre size or millimetres |
| Differential | Your axle ratio against the list the TCU snaps to, and the trim that corrects a wrong learned value |
| True manual | The XDF's patch, on or off |

**Open bin...**, set a panel, **Preview** to see what would change, **Apply** to change the copy in
memory, **Check bin** to run the gate, **Save As...** to write it. Nothing reaches disk until you
save, and **Undo** steps back through every change from any panel. The calibration identity is
checked the moment a bin is opened and shown top-right; if it does not match, every Apply is
blocked.

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

**Converter lockup rides the same slider.** Holding the torque-converter clutch tighter means less
torque is absorbed and released by a slipping converter, so the shift lands more directly. Two maps
move at half the slider's strength: `tcc_press_hold_map` and `tcc_press_fill_map`. Both are HIGH
confidence with units the firmware gives us — 0.01 bar per count — so the report is in bar. Turn it
off with `--no-tcc`, or set it independently with `--tcc-pct`.

Be clear about what this is **not**: nothing in this XDF isolates lockup *during a shift*. These are
the general TCC pressure setpoints, so the converter is tightened everywhere, not only mid-shift.
That is what makes shifts feel direct, but it also puts more drivetrain shock through at low rpm and
makes converter shudder likelier — especially behind an engine the converter was not matched to. If
the car shudders or lugs, `--no-tcc` is the first thing to back off.

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

## Gear choice on kickdown

If planting the pedal drops it one gear further than you want:

```sh
python3 xdf_gearbias.py /path/to/stock.bin --preview      # prints a gear-choice table
python3 xdf_gearbias.py /path/to/stock.bin -o tuned.bin
```

A downshift line is the output-shaft speed below which that downshift is requested, so the gear you
land in is decided by where your speed falls in the ladder of thresholds. To land one gear higher,
each line takes the value its deeper neighbour already held — the numbers come from the calibration
itself, and the shape of the schedule is preserved rather than flattened by a blanket offset. Only
pedal positions at or above `--pedal-from` (default 650 per mille) change, so part throttle stays
stock.

`--bias lower` does the opposite, but expect it to be mostly refused: a downshift line cannot go
above its upshift line without the box downshifting and immediately upshifting again, so the tool
caps it and says so. Holding a lower gear really means raising the **upshift** lines, which is a
different change.

## Downshift blip

On a downshift the TCU asks the engine for a burst of torque to match revs. A bigger blip closes the
speed gap sooner, so the clutch engages earlier and the shift feels crisper.

```sh
python3 xdf_blip.py /path/to/stock.bin --preview
python3 xdf_blip.py /path/to/stock.bin -o tuned.bin            # +15%
python3 xdf_blip.py /path/to/stock.bin -o tuned.bin --pct 30 --pairs 4to3,5to4
```

The encoding is documented in the XDF itself: `torque request (Nm) = z * 6 - 768`, so `z = 128` is
exactly zero and the blip is `(z - 128) * 6` Nm. Only the amount **above** 128 is scaled — cells
asking for no blip stay at zero rather than being pushed up by a percentage — and the preview
reports peak blip in Nm.

Left alone on purpose: the `_scale`, `_outgrad_scale` and `_coolant_scale` maps, which are
multipliers and gates rather than torque; and two maps the XDF declares 16-bit while describing u8
content, where the definition is wrong and writing through it would hit the wrong bytes. The tool
lists what it skipped.

## Wheel circumference and final drive

The TCU has no axle-ratio setting. It derives the final drive from wheel speed and output-shaft
speed, and the only calibration input to that is the dynamic rolling circumference — so a swapped
box, a re-geared diff or a different tyre size all come back to one number.

```sh
python3 xdf_vehicle.py wheel /path/to/stock.bin                    # read it
python3 xdf_vehicle.py wheel /path/to/stock.bin --tire 245/40R18 -o tuned.bin
python3 xdf_vehicle.py wheel /path/to/stock.bin --mm 2185 -o tuned.bin
python3 xdf_vehicle.py diff  /path/to/stock.bin --ratio 3.73
python3 xdf_vehicle.py diff  /path/to/stock.bin --ratio 3.73 --learned 3.91 --fix -o tuned.bin
```

The constant is found through the XDF by title, not by address, and reads **2249 mm** on the
reference E70 image — which is the right answer: the stock 255/55R18 and 255/50R19 fitments both
come to 2248 mm through the XDF's own formula, `pi × (rim × 25.4 + 2 × width × profile/100) × 0.97`.

`diff` does not trust a remembered address for the TCU's fixed ratio list either. It **searches your
image** for a count-prefixed block of ascending ratios: in the reference calibration exactly one
block matches, at `0x19147C`, and its 17 distinct values are exactly the list the XDF documents. In
the sibling `b5yc1313` calibration the same search finds it at `0x1916B4` instead — which is why the
address is reported rather than assumed. Give it your real ratio and it reports the entry the TCU
will snap to and how far off that is; give it the ratio the TCU actually learned and it computes the
circumference trim that makes the next relearn land on the right entry.

After flashing: reset the learned value (Tool32 `steuern_lernfkt_ruecksetzen`, argument 0), drive
above about 24 km/h, then read `status_lernfkt`. Do **not** use this to correct the speedometer —
that is the DSC's coding.

## True manual

```sh
python3 xdf_truemanual.py /path/to/stock.bin --status
python3 xdf_truemanual.py /path/to/stock.bin -o tuned.bin
python3 xdf_truemanual.py tuned.bin --off --stock stock.bin -o back.bin
```

Applies the XDF's own `[PATCH] True manual` — seven writes, 109 bytes, read out of the XDF at run
time so the tool and TunerPro write the same thing. In M the gear you choose is the gear you keep;
the DME rev limiter still protects the engine. `--status` reports each entry and checks that the
untouched ones really hold the stock values the patch description claims (on the reference image
all seven do).

Two things to know. Apply stage-3 map edits **before** this patch: `0x1CECA4` belongs to both. And
four of its spans are not inside any XDF table, so the gate needs `--allow-patch`, which explains
those bytes only where they match the declared patch data exactly — a half-written or
creatively-written patch span still fails.

## Before you flash

```sh
python3 xdf_verify.py ../8hpe70_cali_v3.xdf stock.bin tuned.bin
python3 xdf_verify.py ../8hpe70_cali_v3.xdf stock.bin tuned.bin --allow-patch   # True manual
```

It fails unless the image is the calibration this XDF describes **and** every changed byte lands
inside a table the XDF describes. It additionally refuses a bin that touches the program region, the
calibration header, the `ZFADINFO` identification block or the signature tail, or that leaves a
pedal axis decreasing. A clean run prints `PASS`.

`--allow-patch` widens "inside a table" to include an `XDFPATCH` entry — but only where the tuned
bytes are byte-for-byte the patch data the XDF declares, so it admits a patch that was applied
faithfully and nothing else. Without it, a bin carrying the True manual patch fails on the four
spans no table covers, which is the gate doing its job.

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
