#!/usr/bin/env python3
"""Raise ZF 8HP shift pressure, using the maps a stage-3 tune touches.

The XDF carries a "stage 3" category: the maps a commercial (XHP-style)
stage-3 calibration modifies. This tool takes the shift-pressure maps from
that folder - shift_press_map_b* - and raises them, which applies the clutch
harder so the shift is shorter and firmer.

Read this before trusting it. These maps are rated LOW confidence, and the
XDF's own evidence line for them says "Structure auto-detected by e_calscan.py
... Meaning not analysed. Read by: unknown." So two things are unproven:

  * that they are shift pressure at all. The name is a guess made by a
    structural scanner, not a conclusion from the firmware. The shape is at
    least consistent with it - 6x3 s16, values 3500..19000 (plausible mbar)
    over an axis spanning 2000..7000 (plausible rpm) - but no reader function
    has been identified.
  * that an XHP stage-3 tune changes them. They sit in the XDF's "stage 3"
    category, which is documented as the list of maps such a tune touches, but
    the only off-the-shelf tune available for comparison here targets a
    different calibration (b0bc2323; this XDF addresses b5yc1111), so that
    claim has not been checked byte for byte.

What IS verified: a cell is only ever raised towards the largest value that
same map already contains, so nothing is pushed past a value ZF itself writes
somewhere in that map; and the edit touches those eight maps and nothing else.
That is why there is no "unlimited" setting. Change this in small steps and
check the car.

Checksums are not corrected - sign before flashing, and always gate the result:

    xdf_verify.py 8hpe70_cali_v3.xdf stock.bin out.bin

Examples:
    xdf_stage3.py stock.bin --preview          # show what would change
    xdf_stage3.py stock.bin -o out.bin         # sport (default, +8%)
    xdf_stage3.py stock.bin -o out.bin --level max
    xdf_stage3.py stock.bin -o out.bin --pct 6
"""
import argparse
import os
import re
import sys

from xdflib import XDF, load_bin, decode_table, element_offset, write_elem

XDF_DEFAULT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           '..', '8hpe70_cali_v3.xdf')

PRESS_RX = re.compile(r'^shift_press_map_b\d+$', re.I)

LEVELS = {'mild': 4, 'sport': 8, 'max': 14}


def pressure_tables(xdf):
    """shift_press_map_b* in the 'stage 3' category, deduplicated by address.

    Identity is the z address, never the title: most stage-3 entries alias
    tables that also appear in their own subsystem folders, so matching on
    title alone would apply an edit twice.
    """
    seen, out = set(), []
    for t in xdf.tables:
        if not any('stage' in c.lower() for c in t.categories):
            continue
        if not PRESS_RX.match(t.title):
            continue
        emb = t.z.embedded if t.z else None
        if emb is None or emb.address is None or emb.address in seen:
            continue
        seen.add(emb.address)
        out.append(t)
    return sorted(out, key=lambda t: t.z.embedded.address)


def raise_pressure(buf, table, pct):
    """Scale cells by pct, capped at this map's own maximum. -> (changed, total)"""
    rows, cols = table.shape()
    emb = table.z.embedded
    d = decode_table(buf, table)
    ceiling = max(v for row in d['z'] for v in row)
    factor = 1 + pct / 100.0
    changed = 0
    for r in range(rows):
        for c in range(cols):
            v = d['z'][r][c]
            if v <= 0:
                continue
            new = min(ceiling, round(v * factor))
            if new == v:
                continue
            write_elem(buf, element_offset(emb, rows, cols, r, c), emb, new)
            changed += 1
    return changed, rows * cols, ceiling


def main():
    ap = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='Run xdf_verify.py on the result before flashing.')
    ap.add_argument('bin', help='stock calibration read')
    ap.add_argument('-o', '--out', help='output bin (omit with --preview)')
    ap.add_argument('--xdf', default=XDF_DEFAULT)
    ap.add_argument('--level', choices=['mild', 'sport', 'max'], default='sport',
                    help='how much more pressure: mild +4%%, sport +8%%, max +14%% '
                         '(default: sport)')
    ap.add_argument('--pct', type=float,
                    help='exact percentage instead of --level (0..50)')
    ap.add_argument('--preview', action='store_true',
                    help='report what would change without writing a bin')
    args = ap.parse_args()

    if not args.preview and not args.out:
        ap.error('give -o OUT, or use --preview')
    pct = args.pct if args.pct is not None else LEVELS[args.level]
    if not 0 <= pct <= 50:
        sys.exit('--pct must be within 0..50')

    xdf = XDF(args.xdf)
    tables = pressure_tables(xdf)
    if not tables:
        sys.exit(f'no stage-3 shift_press_map_b* tables in {args.xdf} - '
                 'is this the E70 XDF?')

    buf = bytearray(load_bin(args.bin))
    total = 0
    label = f'+{pct:g}%' + ('' if args.pct is not None else f' ({args.level})')
    print(f'stage-3 shift pressure {label}')
    for t in tables:
        n, cells, ceiling = raise_pressure(buf, t, pct)
        total += n
        print(f'  {t.title[:28]:28s} @0x{t.z.embedded.address:X}  '
              f'{n:2d}/{cells:<2d} cells raised  (capped at this map\'s max {ceiling})')
    print(f'{total} cells changed across {len(tables)} tables')
    print("note: shift_press_map_b* are LOW confidence - the XDF says their meaning "
          'is not analysed and no reader function is known, so "shift pressure" is a '
          'structural guess. Raised only towards each map\'s own existing maximum, '
          'never beyond it. Change in small steps and check the car.')

    if args.preview:
        print('\npreview only, no file written')
        return
    with open(args.out, 'wb') as f:
        f.write(buf)
    print(f'\nwrote {args.out} (checksum NOT corrected - sign before flashing)')
    print(f'gate it: xdf_verify.py {args.xdf} {args.bin} {args.out}')


if __name__ == '__main__':
    main()
