#!/usr/bin/env python3
"""Bias which gear the box picks when you plant the throttle.

The complaint this exists for: punch the pedal and it drops one gear further
than you wanted. The reverse (it will not drop far enough) is the same control
with the sign flipped.

How gear choice works. A downshift line gives, per pedal position, the
output-shaft speed BELOW which that downshift is requested. On a hard pedal
application the box keeps stepping down while the current output speed is
below the next line, so the gear it lands in is decided by where the speed
falls in the ladder of thresholds. Stock char 00 at kickdown:

    2>1 975   3>2 1850   4>3 2950   5>4 3900   6>5 4800   7>6 6500   8>7 7750

At 3000 rpm output it clears 8>7, 7>6 and 6>5, then takes 5>4 because
3000 < 3900, and stops at 4th.

What this tool does. To land one gear higher it re-indexes each line onto the
values of its neighbour one step shallower: 5>4 takes what 4>3 held (2950), so
3000 no longer triggers it and the box stays in 5th. Nothing is invented - the
new numbers are the calibration's own, from the adjacent gear pair - and the
shape of the schedule across the whole speed range is preserved rather than
being flattened by an offset.

    --bias higher   one gear higher (less downshift)  - the default
    --bias lower    one gear lower  (more downshift)

Only pedal positions at or above --pedal-from are touched (default 650 per
mille), so part-throttle behaviour stays stock and only a deliberate stab
changes. Hysteresis is checked: a downshift line is never allowed within
--min-gap of the matching upshift line, which is what stops the box hunting.

Checksums are not corrected - sign before flashing, and gate the result:

    xdf_verify.py 8hpe70_cali_v3.xdf stock.bin out.bin

Examples:
    xdf_gearbias.py stock.bin --preview            # includes a gear-choice table
    xdf_gearbias.py stock.bin -o out.bin
    xdf_gearbias.py stock.bin -o out.bin --bias lower --pedal-from 800
"""
import argparse
import os
import re
import sys

from xdflib import (XDF, load_bin, decode_table, element_offset, write_elem,
                    check_calibration)

XDF_DEFAULT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           '..', '8hpe70_cali_v3.xdf')

DN_RX = re.compile(r'^Downshift char (\d+): (\d)>(\d)$')
UP_RX = re.compile(r'^Upshift char (\d+): (\d)>(\d)$')

# Downshift pairs from shallowest (targets the highest gear) to deepest.
PAIRS = ['8>7', '7>6', '6>5', '5>4', '4>3', '3>2', '2>1']


def collect(xdf):
    """-> (downshifts, upshifts) as {(char, 'N>M'): table}, deduped by address."""
    dn, up, seen = {}, {}, set()
    for t in xdf.tables:
        m = DN_RX.match(t.title)
        target = dn
        if not m:
            m = UP_RX.match(t.title)
            target = up
        if not m:
            continue
        emb = t.z.embedded if t.z else None
        if emb is None or emb.address is None or emb.address in seen:
            continue
        seen.add(emb.address)
        target[(int(m.group(1)), f'{m.group(2)}>{m.group(3)}')] = t
    return dn, up


def upshift_name(dn_pair):
    """'5>4' -> '4>5': the upshift that mirrors this downshift."""
    hi, lo = dn_pair.split('>')
    return f'{lo}>{hi}'


def plan(buf, dn, up, bias, pedal_from, min_gap):
    """-> (writes, notes). writes = [(emb, rows, cols, r, c, value)]."""
    # PAIRS runs shallow -> deep and thresholds fall along it (8>7 is the
    # largest, 2>1 the smallest). To land one gear HIGHER a line must trigger
    # later, i.e. take the SMALLER value of its deeper neighbour: index + 1.
    step = 1 if bias == 'higher' else -1
    writes, notes, clamped = [], [], []
    chars = sorted({c for c, _p in dn})
    for ch in chars:
        decoded = {}
        for p in PAIRS:
            t = dn.get((ch, p))
            if t is not None:
                decoded[p] = decode_table(buf, t)
        for i, p in enumerate(PAIRS):
            t = dn.get((ch, p))
            if t is None:
                continue
            src_i = i + step          # shallower neighbour for 'higher'
            d = decoded[p]
            pedal = d['x']
            rows, cols = t.shape()
            emb = t.z.embedded
            ut = up.get((ch, upshift_name(p)))
            uz = decode_table(buf, ut)['z'] if ut is not None else None
            for r in range(rows):
                for c in range(cols):
                    idx = c if cols >= rows else r
                    pv = pedal[idx] if pedal and idx < len(pedal) else 0
                    if not isinstance(pv, (int, float)) or pv < pedal_from:
                        continue
                    cur = d['z'][r][c]
                    if cur <= 0:
                        continue
                    if 0 <= src_i < len(PAIRS) and PAIRS[src_i] in decoded:
                        new = decoded[PAIRS[src_i]]['z'][r][c]
                    else:
                        # The end of the ladder has no neighbour to borrow from.
                        # Leave it: zeroing 8>7 would stop the box ever leaving
                        # 8th, and zeroing 2>1 would deny 1st at low speed.
                        continue
                    if new == cur:
                        continue
                    if uz is not None:
                        u = uz[r][c]
                        if 0 < u < 8000 and new > u - min_gap:
                            new = max(0, u - min_gap)
                            clamped.append((ch, p))
                    if new != cur:
                        writes.append((emb, rows, cols, r, c, int(new)))
    if clamped:
        pairs = sorted({f'{c:02d} {p}' for c, p in clamped})
        notes.append(
            f'{len(clamped)} of {len(writes) + len(clamped)} intended changes were '
            f'capped to stay {min_gap} rpm below the matching upshift line, across '
            f'{len(pairs)} characteristic/pair combinations.')
        if bias == 'lower' and len(clamped) > len(writes) / 2:
            notes.append(
                'Most of them. Deeper downshifts cannot be had from the downshift '
                'lines alone: raising one above its upshift line would make the box '
                'downshift and immediately upshift again. To actually hold a lower '
                'gear you have to raise the UPSHIFT lines too, so the gear is held '
                'to higher revs in the first place.')
    return writes, notes


def gear_at(thresholds, speed):
    """Gear the ladder settles on at this output speed, starting from top."""
    gear = 8
    for p in PAIRS:
        if p not in thresholds:
            continue
        if speed < thresholds[p]:
            gear = int(p.split('>')[1])
        else:
            break
    return gear


def kickdown_table(buf, dn, ch):
    out = {}
    for p in PAIRS:
        t = dn.get((ch, p))
        if t is None:
            continue
        z = [v for row in decode_table(buf, t)['z'] for v in row]
        out[p] = z[-1]
    return out


def main():
    ap = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('bin')
    ap.add_argument('-o', '--out')
    ap.add_argument('--xdf', default=XDF_DEFAULT)
    ap.add_argument('--bias', choices=['higher', 'lower'], default='higher',
                    help="'higher' = one gear higher, less downshift (default); "
                         "'lower' = one gear lower, more downshift")
    ap.add_argument('--pedal-from', type=float, default=650,
                    help='only change pedal positions at or above this per mille '
                         '(default 650; 1100 = kickdown)')
    ap.add_argument('--min-gap', type=float, default=150,
                    help='keep a downshift line at least this many rpm below its '
                         'upshift line (default 150)')
    ap.add_argument('--chars', help='limit to these characteristics, e.g. 0,8,9')
    ap.add_argument('--any-calibration', action='store_true')
    ap.add_argument('--preview', action='store_true')
    args = ap.parse_args()

    if not args.preview and not args.out:
        ap.error('give -o OUT, or use --preview')

    xdf = XDF(args.xdf)
    stock = load_bin(args.bin)
    ok, msg = check_calibration(stock, os.path.basename(args.bin))
    if ok:
        print(msg)
    elif args.any_calibration:
        print('WARNING: ' + msg, file=sys.stderr)
    else:
        sys.exit(msg + '\n\nRefusing to edit.')

    dn, up = collect(xdf)
    if args.chars:
        keep = {int(c) for c in args.chars.split(',')}
        dn = {k: v for k, v in dn.items() if k[0] in keep}
    if not dn:
        sys.exit('no downshift line tables found - is this the E70 XDF?')

    buf = bytearray(stock)
    writes, notes = plan(buf, dn, up, args.bias, args.pedal_from, args.min_gap)
    for emb, rows, cols, r, c, val in writes:
        write_elem(buf, element_offset(emb, rows, cols, r, c), emb, val)

    chars = sorted({c for c, _p in dn})
    print(f'gear bias: one gear {args.bias}, pedal >= {args.pedal_from:g} per mille, '
          f'{len(chars)} characteristics')
    print(f'{len(writes)} cells changed')
    for n in notes:
        print('  ' + n)

    ch = chars[0]
    before, after = kickdown_table(stock, dn, ch), kickdown_table(buf, dn, ch)
    print(f'\nchar {ch:02d} kickdown thresholds (output rpm):')
    print('  pair    stock   tuned')
    for p in PAIRS:
        if p in before:
            print(f'  {p}  {before[p]:7d} {after[p]:7d}')
    print('\ngear chosen at full pedal, by output-shaft speed:')
    print('  out rpm   stock   tuned')
    for s in (1000, 1500, 2000, 2500, 3000, 3500, 4000, 5000, 6000, 7000):
        print(f'  {s:7d}   {gear_at(before, s):5d}   {gear_at(after, s):5d}')

    if args.preview:
        print('\npreview only, no file written')
        return
    with open(args.out, 'wb') as f:
        f.write(buf)
    print(f'\nwrote {args.out} (checksum NOT corrected - sign before flashing)')


if __name__ == '__main__':
    main()
