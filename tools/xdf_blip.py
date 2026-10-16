#!/usr/bin/env python3
"""Blip the throttle harder on downshifts.

On a downshift the TCU asks the engine for a burst of torque to spin the
input shaft up to the speed the lower gear needs. A bigger blip closes that
speed gap sooner, so the clutch engages earlier and the shift feels crisper
instead of soft and drawn out.

The encoding is known, from the XDF's own description of these maps:

    engine torque request (Nm) = z * 6 - 768

so z = 128 is exactly zero torque and the blip is (z - 128) * 6 Nm. Only the
amount ABOVE 128 is the blip, which is what this tool scales. Multiplying the
raw byte instead would be wrong - it would shift the zero point and command
torque where the calibration asks for none - so cells sitting at 128 are left
untouched and never pushed up by a percentage.

What it edits: the 8-bit shiftexec_dn_blip_trq_* maps (HIGH confidence on the
ones carrying a rating) and shiftexec_dn_blip_map_6x10. What it deliberately
does NOT edit:

  * shiftexec_dn_blip_scale_*, _outgrad_scale, _coolant_scale - these are
    multipliers and gates on the blip, not the torque itself, on a different
    scale entirely. Scaling them would compound unpredictably.
  * two maps named shiftexec_dn_blip_trq_k1_3to2 and _k1_5to4 that the XDF
    declares 16-bit while describing u8 content. Their values decode as 30,
    30, 25, 15 and 0, 1, 2 - u8 bytes read two at a time - so the definition
    is wrong for them and writing through it would hit the wrong bytes. They
    are skipped and reported.

Checksums are not corrected - sign before flashing, and gate the result:

    xdf_verify.py 8hpe70_cali_v3.xdf stock.bin out.bin

Examples:
    xdf_blip.py stock.bin --preview
    xdf_blip.py stock.bin -o out.bin                 # +15%, a little more
    xdf_blip.py stock.bin -o out.bin --pct 30
    xdf_blip.py stock.bin -o out.bin --pairs 4to3,5to4
"""
import argparse
import os
import re
import sys

from xdflib import (XDF, load_bin, decode_table, element_offset, write_elem,
                    check_calibration)

XDF_DEFAULT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           '..', '8hpe70_cali_v3.xdf')

TRQ_RX = re.compile(r'^(auto_)?shiftexec_dn_blip_trq', re.I)
MAP_RX = re.compile(r'^(auto_)?shiftexec_dn_blip_map', re.I)
PAIR_RX = re.compile(r'(\dto\d)')

BLIP_ZERO = 128          # z = 128 is zero torque
NM_PER_STEP = 6          # torque request (Nm) = z * 6 - 768


def blip_tables(xdf, pairs=None):
    """-> (usable, skipped). Deduplicated by z address; title is not unique."""
    usable, skipped, seen = [], [], set()
    for t in xdf.tables:
        if not (TRQ_RX.match(t.title) or MAP_RX.match(t.title)):
            continue
        emb = t.z.embedded if t.z else None
        if emb is None or emb.address is None or emb.address in seen:
            continue
        seen.add(emb.address)
        if pairs:
            m = PAIR_RX.search(t.title)
            if not m or m.group(1) not in pairs:
                continue
        if emb.elem_bits != 8:
            skipped.append((t, f'declared {emb.elem_bits}-bit but the map is u8 - '
                               'the definition is wrong here, so it is left alone'))
            continue
        usable.append(t)
    return usable, skipped


def scale_blip(buf, table, pct):
    """Scale the amount above 128. -> (changed, cells, peak_nm_before, peak_nm_after)"""
    rows, cols = table.shape()
    emb = table.z.embedded
    d = decode_table(buf, table)
    factor = 1 + pct / 100.0
    changed, before_peak, after_peak = 0, BLIP_ZERO, BLIP_ZERO
    for r in range(rows):
        for c in range(cols):
            v = d['z'][r][c]
            before_peak = max(before_peak, v)
            if v <= BLIP_ZERO:          # no blip asked for here; leave it
                after_peak = max(after_peak, v)
                continue
            new = min(255, BLIP_ZERO + round((v - BLIP_ZERO) * factor))
            after_peak = max(after_peak, new)
            if new != v:
                write_elem(buf, element_offset(emb, rows, cols, r, c), emb, new)
                changed += 1
    return (changed, rows * cols,
            (before_peak - BLIP_ZERO) * NM_PER_STEP,
            (after_peak - BLIP_ZERO) * NM_PER_STEP)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('bin')
    ap.add_argument('-o', '--out')
    ap.add_argument('--xdf', default=XDF_DEFAULT)
    ap.add_argument('--pct', type=float, default=15,
                    help='how much more blip, %% over stock (default 15; -50..100)')
    ap.add_argument('--pairs', help='limit to these gear pairs, e.g. 4to3,5to4')
    ap.add_argument('--any-calibration', action='store_true')
    ap.add_argument('--preview', action='store_true')
    args = ap.parse_args()

    if not args.preview and not args.out:
        ap.error('give -o OUT, or use --preview')
    if not -50 <= args.pct <= 100:
        sys.exit('--pct must be within -50..100')

    xdf = XDF(args.xdf)
    stock = load_bin(args.bin)
    ok, msg = check_calibration(stock, os.path.basename(args.bin))
    if ok:
        print(msg)
    elif args.any_calibration:
        print('WARNING: ' + msg, file=sys.stderr)
    else:
        sys.exit(msg + '\n\nRefusing to edit.')

    pairs = set(args.pairs.split(',')) if args.pairs else None
    tables, skipped = blip_tables(xdf, pairs)
    if not tables:
        sys.exit('no blip torque maps matched'
                 + (f' --pairs {args.pairs}' if pairs else ''))

    buf = bytearray(stock)
    total = 0
    rows_out = []
    for t in tables:
        n, cells, nm_before, nm_after = scale_blip(buf, t, args.pct)
        total += n
        rows_out.append((t.title, t.z.embedded.address, n, cells, nm_before, nm_after))

    print(f'downshift blip {args.pct:+g}% on {len(tables)} maps')
    print('  map                                     cells      peak blip')
    for title, addr, n, cells, nmb, nma in rows_out:
        arrow = f'{nmb:4.0f} -> {nma:4.0f} Nm' if nmb else '   no blip here'
        print(f'  {title[:38]:38s} @0x{addr:X} {n:3d}/{cells:<3d} {arrow}')
    print(f'{total} cells changed')
    if skipped:
        print('\nskipped:')
        for t, why in skipped:
            print(f'  {t.title[:40]:40s} @0x{t.z.embedded.address:X}  {why}')
    print('\nnote: z = 128 is zero torque and only the amount above it is scaled, '
          'so maps that ask for no blip stay at zero. Blip scale/gate maps '
          '(_scale, _outgrad_scale, _coolant_scale) are deliberately untouched.')

    if args.preview:
        print('\npreview only, no file written')
        return
    with open(args.out, 'wb') as f:
        f.write(buf)
    print(f'\nwrote {args.out} (checksum NOT corrected - sign before flashing)')


if __name__ == '__main__':
    main()
