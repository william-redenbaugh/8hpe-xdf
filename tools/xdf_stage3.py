#!/usr/bin/env python3
"""Shift the ZF8 faster, using the maps a stage-3 tune touches.

The XDF carries a "stage 3" category: 108 items that collect, in one folder,
every map a commercial (XHP-style) stage-3 calibration modifies. This tool
takes the subset of that folder which actually governs how a shift *feels* and
moves it in the faster/firmer direction, as one toggle.

What it changes, and why each group is on or off by default:

  blip      shiftexec_dn_blip_trq_* - the engine-torque blip that rev-matches a
            downshift. HIGH confidence, and the encoding is known: u8 with 128
            meaning "no blip", so the excess over 128 is what gets scaled. More
            blip closes the speed gap sooner, so the clutch engages earlier and
            the downshift feels immediate. ON by default.

  pressure  shift_press_map_b* - shift pressure. More pressure applies the
            clutch harder, which shortens the shift and makes it firmer. These
            are LOW confidence: a stage-3 tune demonstrably rewrites them, but
            their row/column meaning is not proven here, so values are only
            ever raised towards the largest value the same table already
            contains - never beyond what ZF itself commands somewhere in that
            map. ON by default, conservatively.

  torque    shift_torque_limit_class* - the torque ceiling enforced during a
            shift. Raising it lets more torque through the shift, which is
            faster but loads the driveline harder. MED confidence. OFF by
            default; enable deliberately with --torque.

This tool deliberately does not touch shift *timing* tables: phase and sync
durations are xdf_tune.py quickness, and the request-to-engagement delay is
xdf_tune.py shift-response. Run those alongside this for the full effect.

Checksums are not corrected here - sign before flashing, and always gate the
result:

    xdf_verify.py XDF stock.bin out.bin

Examples:
    xdf_stage3.py stock.bin -o out.bin                    # sport level, preview off
    xdf_stage3.py stock.bin --preview                     # show what would change
    xdf_stage3.py stock.bin -o out.bin --level max --torque
    xdf_stage3.py stock.bin -o out.bin --blip-pct 30 --press-pct 0
"""
import argparse
import os
import re
import sys

from xdflib import XDF, load_bin, decode_table, element_offset, write_elem

XDF_DEFAULT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           '..', '8hpe70_cali_v3.xdf')

BLIP_RX = re.compile(r'^(auto_)?shiftexec_dn_blip_trq_', re.I)
PRESS_RX = re.compile(r'^shift_press_map_b\d+$', re.I)
TORQUE_RX = re.compile(r'^shift_torque_limit_class\d+$', re.I)

# Blip tables encode engine torque as an offset around this midpoint: 128 is
# "no blip", so only the excess over it is meaningful to scale.
BLIP_ZERO = 128

LEVELS = {            # blip %, pressure %, torque %
    'mild': (12, 4, 3),
    'sport': (25, 8, 5),
    'max': (40, 14, 8),
}


def stage3_items(xdf):
    """Tables in the XDF's 'stage 3' category, deduplicated by z address.

    Most stage-3 entries are aliases of tables documented elsewhere, and one
    title (shiftexec_dn_blip_trq_k2_6to5) legitimately exists at two different
    addresses, so identity is the address, never the title.
    """
    seen, out = set(), []
    for t in xdf.tables:
        if not any('stage' in c.lower() for c in t.categories):
            continue
        emb = t.z.embedded if t.z else None
        if emb is None or emb.address is None or emb.address in seen:
            continue
        seen.add(emb.address)
        out.append(t)
    return out


def scale_table(buf, table, fn):
    """Apply fn(value) -> new value over every cell. Returns (changed, total)."""
    rows, cols = table.shape()
    emb = table.z.embedded
    d = decode_table(buf, table)
    changed = 0
    for r in range(rows):
        for c in range(cols):
            v = d['z'][r][c]
            new = fn(v)
            if new is None or new == v:
                continue
            write_elem(buf, element_offset(emb, rows, cols, r, c), emb, new)
            changed += 1
    return changed, rows * cols


def elem_max(emb):
    """Largest value the element can hold, for clamping."""
    if emb.is_float:
        return None
    bits = emb.elem_bits
    return (1 << (bits - 1)) - 1 if emb.signed else (1 << bits) - 1


def op_blip(buf, tables, pct, report):
    factor = 1 + pct / 100.0
    total = 0
    for t in tables:
        hi = elem_max(t.z.embedded) or 255

        def fn(v, hi=hi):
            if v <= BLIP_ZERO:          # no blip commanded here; leave it alone
                return None
            return min(hi, BLIP_ZERO + round((v - BLIP_ZERO) * factor))

        n, tot = scale_table(buf, t, fn)
        total += n
        report.append((t.title, t.z.embedded.address, n, tot, 'blip'))
    return total


def op_pressure(buf, tables, pct, report):
    factor = 1 + pct / 100.0
    total = 0
    for t in tables:
        d = decode_table(buf, t)
        ceiling = max(v for row in d['z'] for v in row)   # this map's own maximum

        def fn(v, ceiling=ceiling):
            if v <= 0:
                return None
            return min(ceiling, round(v * factor))

        n, tot = scale_table(buf, t, fn)
        total += n
        report.append((t.title, t.z.embedded.address, n, tot,
                       f'pressure (capped at this map\'s own max {ceiling})'))
    return total


def op_torque(buf, tables, pct, report):
    factor = 1 + pct / 100.0
    total = 0
    for t in tables:
        hi = elem_max(t.z.embedded) or 65535

        def fn(v, hi=hi):
            if v <= 0:
                return None
            return min(hi, round(v * factor))

        n, tot = scale_table(buf, t, fn)
        total += n
        report.append((t.title, t.z.embedded.address, n, tot, 'torque limit'))
    return total


def main():
    ap = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='Run xdf_verify.py on the result before flashing.')
    ap.add_argument('bin', help='stock calibration read')
    ap.add_argument('-o', '--out', help='output bin (omit with --preview)')
    ap.add_argument('--xdf', default=XDF_DEFAULT)
    ap.add_argument('--level', choices=sorted(LEVELS), default='sport',
                    help='preset strength (default: sport)')
    ap.add_argument('--blip-pct', type=float,
                    help='override: downshift blip strength, %% over stock')
    ap.add_argument('--press-pct', type=float,
                    help='override: shift pressure, %% over stock (0 disables)')
    ap.add_argument('--torque', action='store_true',
                    help='also raise the in-shift torque limits (MED confidence, '
                         'loads the driveline harder)')
    ap.add_argument('--torque-pct', type=float,
                    help='override: torque limit, %% over stock (implies --torque)')
    ap.add_argument('--preview', action='store_true',
                    help='report what would change without writing a bin')
    args = ap.parse_args()

    if not args.preview and not args.out:
        ap.error('give -o OUT, or use --preview')

    blip_pct, press_pct, torque_pct = LEVELS[args.level]
    if args.blip_pct is not None:
        blip_pct = args.blip_pct
    if args.press_pct is not None:
        press_pct = args.press_pct
    if args.torque_pct is not None:
        torque_pct = args.torque_pct
        args.torque = True
    for name, val in (('--blip-pct', blip_pct), ('--press-pct', press_pct),
                      ('--torque-pct', torque_pct)):
        if not -50 <= val <= 100:
            sys.exit(f'{name} must be within -50..100')

    xdf = XDF(args.xdf)
    buf = bytearray(load_bin(args.bin))
    items = stage3_items(xdf)
    blip = [t for t in items if BLIP_RX.match(t.title)]
    press = [t for t in items if PRESS_RX.match(t.title)]
    torque = [t for t in items if TORQUE_RX.match(t.title)]
    if not blip and not press:
        sys.exit(f'no stage-3 shift-feel tables found in {args.xdf} - is this the '
                 'E70 XDF?')

    report, total = [], 0
    if blip_pct:
        total += op_blip(buf, blip, blip_pct, report)
    if press_pct:
        total += op_pressure(buf, press, press_pct, report)
    if args.torque and torque_pct:
        total += op_torque(buf, torque, torque_pct, report)

    print(f'stage3-fast [{args.level}]: blip {blip_pct:+g}%, pressure {press_pct:+g}%'
          + (f', torque limit {torque_pct:+g}%' if args.torque else ', torque limit off'))
    for title, addr, n, tot, what in report:
        print(f'  {title[:46]:46s} @0x{addr:X}  {n:3d}/{tot:<3d} cells  {what}')
    print(f'{total} cells changed across {len(report)} tables')
    if press_pct:
        print('note: shift_press_map_b* are LOW confidence - a stage-3 tune rewrites '
              'them, but their row/column meaning is unproven here, so values were '
              'only raised towards each map\'s own existing maximum.')
    print('note: shift timing is separate - use xdf_tune.py quickness (phase/sync '
          'duration) and xdf_tune.py shift-response (request-to-engagement delay).')

    if args.preview:
        print('\npreview only, no file written')
        return
    with open(args.out, 'wb') as f:
        f.write(buf)
    print(f'\nwrote {args.out} (checksum NOT corrected - sign before flashing)')
    print(f'gate it: xdf_verify.py {args.xdf} {args.bin} {args.out}')


if __name__ == '__main__':
    main()
