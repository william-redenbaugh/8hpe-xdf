# XDF tools

Small, dependency-free Python 3 scripts for working with `8hpe_cali_v3.xdf`
(and TunerPro XDFs generally) outside of TunerPro — inspecting the definition,
decoding values from a calibration read, diffing bins, and applying the
`[PATCH]` entries from the command line.

The canonical tool for this XDF remains **TunerPro** (Windows; runs under
Wine): it renders the tables, handles editing, and applies patches
interactively. These scripts exist for scripting, auditing and diffing — the
things a GUI is bad at. (Note: the `pyxdf` package on PyPI is for the
*biosignal* XDF format, not TunerPro's — hence these scripts.)

All scripts use only the standard library. On macOS, if Homebrew's Python
fails with a `pyexpat`/`expat` ImportError, use the system interpreter:
`/usr/bin/python3`.

## Scripts

| Script | What it does |
|---|---|
| `xdf_gui.py` | **GUI editor** (tkinter, stdlib only): browse/search all tables, edit any table in a grid, bulk-edit whole families with a slider, and a shift-speed preset that moves selected shift lines across all 23 characteristics at once |
| `xdflib.py` | Library: XDF parser + bin decoder/encoder (import it from your own scripts) |
| `xdf_ls.py` | List/search defined items by name, category, kind or address |
| `xdf_show.py` | Decode and print one table/constant from a calibration read |
| `xdf_export.py` | Export the whole inventory to JSON/CSV, optionally with decoded values |
| `xdf_diff.py` | Diff two bins through the XDF: which defined items changed, cell by cell |
| `xdf_patch.py` | List, preview (`--show`) or apply (`--apply`) the XDF's `[PATCH]` entries |
| `annotate_xdf.py` | Write the educated guesses from `docs/data/unlabelled-guesses.csv` into the XDF's own item descriptions (in place, idempotent, formatting-preserving) |
| `xdf_checksum.py` | Clean-room checksum **search / verify / sign**: confirms the CRC algorithm+region against your stock read once, then signs edited bins (used by the GUI's Sign bin button) |

## GUI

```sh
cd tools
/usr/bin/python3 xdf_gui.py ../8hpe_cali_v3.xdf my_read.bin
```

Like TunerPro, the GUI pairs a **definition** with a **binary**: both can be
given on the command line (XDF first, bin second) or picked in the toolbar
(`Open XDF…`, `Open bin…`). Edits always go into the binary; `Save bin as…`
writes a new file.

- **Table tab** — pick any table or constant on the left, edit cells in a grid
  (axes decoded live from your bin), Apply writes them back in memory.
- **Bulk edit tab** — a regex/category filter selects a whole family of
  related tables (duplicated definitions of the same flash bytes are applied
  once); one offset or percent slider changes all of them, with optional
  sentinel skipping.
- **Shift speed tab** — the sliding-scale shift-point control: pick gear pairs
  and characteristics, drag the rpm offset, and all selected upshift lines
  move together, optionally dragging the matching downshift lines along so the
  up/down hysteresis is preserved. 8000-rpm "shift disabled" sentinels are
  never touched.
- **NA presets tab** — three one-step modes for an NA swap: **Shift
  quickness** (percent slider shortening the documented shift-execution
  phase/sync time tables), **Hold 1st–3rd to redline** (raises the 1>2 / 2>3 /
  3>4 upshift lines of all 23 characteristics to engine redline ÷ gear ratio,
  never lowering anything; keep redline under the ~7100 rpm TCU guard or
  apply True manual first), and **Early upshift (NA)** (pedal-weighted
  lowering of all upshift lines — full effect at closed throttle, zero from
  80% pedal, each point clamped ≥ its downshift line + 100 rpm so the box
  can't hunt).
- **Sign bin / Flash…** — Sign recomputes the calibration checksum using the
  profile `xdf_checksum.py search` confirmed against your stock read; Flash
  explains the validated handoff (save the signed 2 MB image, flash with 8HPe
  Quickflash or your EGS flasher) — in-GUI flashing stays disabled until a
  write path is bench-validated (see docs/analysis/quickflash-interop.md).
- **Changes tab** — everything that differs from the loaded original, with
  per-item revert; plus a global undo stack. Saving always writes a new file.

## Examples

```sh
cd tools

# What categories exist, and how many items in each?
python3 xdf_ls.py ../8hpe_cali_v3.xdf --categories

# Find every TCC slip item, with full descriptions
python3 xdf_ls.py ../8hpe_cali_v3.xdf -s tcc_slip --long

# What lives at/near an address you found in a log or disassembly?
python3 xdf_ls.py ../8hpe_cali_v3.xdf --addr 0x1D0AB6 --slack 64

# Print the wheel circumference programmed in your read
python3 xdf_show.py ../8hpe_cali_v3.xdf my_read.bin Radumfang

# Dump a shift-line table as CSV
python3 xdf_show.py ../8hpe_cali_v3.xdf my_read.bin \
    "Upshift lines, char 00: 1>2..5>6" --csv

# What did a tune actually change, in XDF terms?
python3 xdf_diff.py ../8hpe_cali_v3.xdf stock.bin tuned.bin --cells
# ...and which changed bytes are NOT covered by any defined item?
python3 xdf_diff.py ../8hpe_cali_v3.xdf stock.bin tuned.bin --raw

# Preview, then apply, the True manual patch
python3 xdf_patch.py ../8hpe_cali_v3.xdf my_read.bin --show "True manual"
python3 xdf_patch.py ../8hpe_cali_v3.xdf my_read.bin --apply "True manual" -o my_tm.bin
```

## Things to know

- **The bin must be the full 2 MB image** (calibration at `0x180200`, program
  area blank) — the same requirement TunerPro has with this XDF. Addresses in
  the XDF are file offsets into that image.
- **Checksums are not corrected** by these scripts (or by the XDF). Recompute
  the segment CRC before flashing anything they produce — 8HPe Quickflash
  does this automatically at flash time.
- **Strided tables:** a few hundred tables (shift lines, multi-block
  `ratio_mon`/`set#` families) store their columns non-contiguously. The XDF
  encodes this via `mmedminorstridebits` on column-major data; `xdflib`
  decodes it as `column_pitch_bits = (rows - 1) * element_bits +
  minorstridebits`, which was verified against the slot layout documented in
  the XDF's own descriptions (15 u16 slots on a 60-byte pitch). If you feed
  these scripts a *different* generator's XDF and strided tables look wrong,
  suspect that convention first.
- `xdf_patch.py --apply` refuses to write in place; it always writes a copy.
