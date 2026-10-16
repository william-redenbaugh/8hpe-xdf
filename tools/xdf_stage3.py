#!/usr/bin/env python3
"""Raise ZF 8HP shift pressure, using the maps a stage-3 tune touches.

The XDF carries a "stage 3" category: the maps a commercial (XHP-style)
stage-3 calibration modifies. This tool takes the shift-pressure maps from
that folder - shift_press_map_b* - and raises them, which applies the clutch
harder so the shift is shorter and firmer.

Torque converter lockup rides along with the slider. Holding the converter
clutch tighter means less torque is absorbed and released by a slipping
converter, so the shift lands more directly. Two maps are raised:
tcc_press_hold_map (the clutch holding pressure) and tcc_press_fill_map (the
fill stage). Both are HIGH confidence with units the firmware tells us -
0.01 bar per count - so the report is printed in bar.

Be clear about what this is NOT: nothing in this XDF isolates lockup *during a
shift*. These are the general TCC pressure setpoints, so raising them tightens
the converter everywhere, not only mid-shift. That is what makes shifts feel
more direct, but it also means more drivetrain shock reaches you at low rpm
and converter shudder becomes likelier - especially on an engine the converter
was not matched to. Disable it with --no-tcc if the car starts to shudder or
lug, and treat it as the first thing to back off.

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

from xdflib import (XDF, load_bin, decode_table, element_offset, write_elem,
                    check_calibration)

XDF_DEFAULT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           '..', '8hpe70_cali_v3.xdf')

PRESS_RX = re.compile(r'^shift_press_map_b\d+$', re.I)
# TCC clutch pressure setpoints. HIGH confidence, 0.01 bar per count, reader
# function identified in the firmware. These are general lockup pressures, not
# a shift-phase-only control - see the note above.
TCC_TITLES = ('tcc_press_hold_map', 'tcc_press_fill_map')
TCC_BAR_PER_COUNT = 0.01

# Percentages are not the real limit: every cell is additionally capped at
# its own map's maximum, and at +14% nothing is saturating yet (cells need
# +26%..+443%, median +90%, to reach that cap). 'firm' and 'hard' exist for
# people who want the headroom; above ~30% cells start pinning at the cap.
LEVELS = {'mild': 4, 'sport': 8, 'max': 14, 'firm': 25, 'hard': 40}
# TCC moves with the slider but more gently: the converter clutch has far less
# headroom than the shift pressures and is what you feel at steady cruise.
TCC_FRACTION = 0.5


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


def tcc_tables(xdf):
    """The TCC pressure setpoint maps, deduplicated by z address."""
    seen, out = set(), []
    for t in xdf.tables:
        if t.title not in TCC_TITLES:
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
    ap.add_argument('--level', choices=sorted(LEVELS), default='sport',
                    help='mild +4%%, sport +8%%, max +14%%, firm +25%%, hard +40%% '
                         '(default: sport)')
    ap.add_argument('--pct', type=float,
                    help='exact percentage instead of --level (0..100); the '
                         "per-map cap still applies, so the effect saturates")
    ap.add_argument('--tcc-pct', type=float,
                    help='override the converter-lockup pressure rise, %% over '
                         'stock (default: half the shift-pressure figure)')
    ap.add_argument('--no-tcc', action='store_true',
                    help='leave the torque converter alone; shift pressure only')
    ap.add_argument('--any-calibration', action='store_true',
                    help='edit even if the image is a different calibration from '
                         'the one this XDF describes (the addresses then mean '
                         'something else - almost always wrong)')
    ap.add_argument('--preview', action='store_true',
                    help='report what would change without writing a bin')
    args = ap.parse_args()

    if not args.preview and not args.out:
        ap.error('give -o OUT, or use --preview')
    pct = args.pct if args.pct is not None else LEVELS[args.level]
    if not 0 <= pct <= 100:
        sys.exit('--pct must be within 0..100')
    tcc_pct = 0.0 if args.no_tcc else (
        args.tcc_pct if args.tcc_pct is not None else round(pct * TCC_FRACTION, 1))
    if not 0 <= tcc_pct <= 100:
        sys.exit('--tcc-pct must be within 0..100')

    xdf = XDF(args.xdf)
    buf_probe = load_bin(args.bin)
    ok, msg = check_calibration(buf_probe, os.path.basename(args.bin))
    if ok:
        print(msg)
    elif args.any_calibration:
        print('WARNING: ' + msg, file=sys.stderr)
        print('continuing anyway because --any-calibration was given',
              file=sys.stderr)
    else:
        sys.exit(msg + '\n\nRefusing to edit. Pass --any-calibration only if you '
                 'know why the identity differs.')

    tables = pressure_tables(xdf)
    if not tables:
        sys.exit(f'no stage-3 shift_press_map_b* tables in {args.xdf} - '
                 'is this the E70 XDF?')

    buf = bytearray(buf_probe)
    total = 0
    label = f'+{pct:g}%' + ('' if args.pct is not None else f' ({args.level})')
    print(f'stage-3 shift pressure {label}'
          + (f', converter lockup +{tcc_pct:g}%' if tcc_pct else ', converter lockup off'))
    for t in tables:
        n, cells, ceiling = raise_pressure(buf, t, pct)
        total += n
        print(f'  {t.title[:28]:28s} @0x{t.z.embedded.address:X}  '
              f'{n:2d}/{cells:<2d} cells raised  (capped at this map\'s max {ceiling})')
    tcc = tcc_tables(xdf) if tcc_pct else []
    if tcc_pct and not tcc:
        print('note: no TCC pressure maps found in this XDF - skipping lockup')
    for t_ in tcc:
        before = [v for r in decode_table(buf, t_)['z'] for v in r]
        n, cells, ceiling = raise_pressure(buf, t_, tcc_pct)
        after = [v for r in decode_table(buf, t_)['z'] for v in r]
        total += n
        print(f'  {t_.title[:28]:28s} @0x{t_.z.embedded.address:X}  '
              f'{n:2d}/{cells:<2d} cells raised  '
              f'{min(before) * TCC_BAR_PER_COUNT:.2f}-{max(before) * TCC_BAR_PER_COUNT:.2f}'
              f' -> {min(after) * TCC_BAR_PER_COUNT:.2f}-{max(after) * TCC_BAR_PER_COUNT:.2f} bar'
              f'  (cap {ceiling * TCC_BAR_PER_COUNT:.2f} bar)')
    print(f'{total} cells changed across {len(tables) + len(tcc)} tables')
    if tcc_pct:
        print('note: the TCC maps are general lockup pressures, NOT a shift-only '
              'control - the converter is tightened everywhere, not just mid-shift. '
              'Back this off first (--no-tcc) if you get shudder or lugging at low '
              'rpm, which is the likeliest complaint on a converter that was not '
              'matched to the engine.')
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
