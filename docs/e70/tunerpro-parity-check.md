# TunerPro parity: settled

**Our tools and TunerPro write the same bytes.** This was an open risk — the XDF format has no
public specification, and `xdflib`'s rule for strided tables was originally derived by matching the
firmware rather than from any documentation. It is now closed, from TunerPro's own artifacts.

## What TunerPro actually does

TunerPro computes the address of table cell (row `r`, column `c`) like this, in bytes:

```
cell  = mmedelementsizebits / 8
M     = (mmedmajorstridebits or mmedelementsizebits) / 8     # 0 means "same as cell size"
N     = (mmedminorstridebits or mmedelementsizebits) / 8
base  = mmedaddress + BASEOFFSET            # subtract="1" makes it mmedaddress - offset

column major (mmedtypeflags & 0x04):
    addr(r, c) = base + c * ((mmedrowcount - 1) * M + N) + r * M
row major:
    addr(r, c) = base + r * ((mmedcolcount - 1) * M + N) + c * M
```

The load-bearing detail is what **Minor Stride** measures. TunerPro's shipped help defines it as
"the number of bytes between the start of the last cell of a column and the start of the first cell
of the next column" — a *gap past the last cell*, not the whole column pitch. So the pitch is
`(rows-1)*major + minor`, which is exactly what `xdflib` implements.

Two traps worth knowing:

- **Units.** The editor labels the fields "Major Stride (Bytes)" and "Minor Stride (Bytes)", but the
  XML attributes are named `...bits`. The stored number is bytes × 8 — a 32-byte minor stride is
  written as `256`.
- **The public help is the wrong revision.** tunerpro.net's web help is the 2009 edition, written
  before strides were added (TunerPro changelog, v5.00.7004.00, 23 Aug 2010). That is why searching
  the web for stride semantics finds nothing. The documentation exists only inside
  `TunerProHelp.chm` in the installer, and in the field tooltips compiled into `XDFEditor.dll`.

Type flags, confirmed from the same sources: `0x01` signed, `0x02` LSB-first, `0x04` column-major,
`0x10000` IEEE-754 float. A negative `mmedmajorstridebits` on an axis reverses its order.

## Verification against this calibration

Applied to `Upshift lines, char 00: 1>2..5>6` (15×5 u16, flags `0x04`, major 0, minor 256), the
formula puts the five gear-pair columns at +0/+60/+120/+180/+240 bytes and column `1>2` reads:

```
325 325 325 325 325 450 475 700 725 875 900 1100 1100 1100 1100
```

That matches the firmware's own shift-line layout recovered by decompiling the reader functions, and
it matches the per-gear-pair single-curve tables that alias the same flash bytes. Across the
calibration, 453 of 469 alias pairs decode byte-identically with **zero value mismatches**; the
remainder are items whose bytes are missing from the test image, not disagreements. Five rival
readings of the stride fields were tested and every one of them disagrees with the data.

## What this means in practice

Edit the block tables or the single curves, in TunerPro or with these tools, in any combination —
the resulting binaries are interchangeable. No workaround is needed and nothing has to be
regenerated.

Still run the safety gate before flashing. It refuses any bin that changes a byte no XDF item
covers, touches a protected region, or breaks a pedal axis:

```sh
/usr/bin/python3 tools/xdf_verify.py 8hpe70_cali_v3.xdf stock.bin tuned.bin
```

## Confirming it yourself

If you want to see it with your own eyes, open the XDF in TunerPro with a stock E70 read, open
`Upshift lines, char 00: 1>2..5>6`, and check the first column against the fifteen values above.
The repo also ships a container that runs TunerPro under Wine for exactly this purpose — see
[docker/README.md](../../docker/README.md).
