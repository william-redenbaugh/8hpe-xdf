#!/usr/bin/env python3
"""Move the shift points, separately for each drive mode.

Hold gears further up the rev range in manual/sport while leaving normal D
alone, or soften D without touching sport.

Why this can be done per mode. The schedule exists 23 times over - one
"characteristic" each, a full set of up and down lines over a 15-point pedal
axis - and which one is live comes from the strategy state, which is what the
drive mode selects. So editing only the characteristics a mode uses changes
only that mode. (Shift FIRMNESS is a different matter: the pressure maps are
not known to be mode-indexed, so this tool moves when shifts happen, not how
hard they hit. Do not confuse the two - they feel completely different.)

Units. Lines are output-shaft rpm, and engine rpm = output rpm x gear ratio,
so a percentage is the natural control: --up-pct 10 makes every upshift happen
10% further up the rev range, whatever the gear. --up-rpm moves them by a flat
output-rpm amount instead.

    --up-pct    + holds gears longer (shifts later, higher revs)
    --dn-pct    + downshifts earlier/more eagerly

Safety. A downshift line is never allowed within --min-gap of its upshift line,
which is what stops the box hunting between two gears. Upshifts are capped so
the engine speed they imply stays under --max-engine-rpm (the stock TCU guard
is around 7100). Cells holding the disabled sentinel (>= 8000) are left alone.

Which characteristics belong to which mode is NOT recorded in the calibration.
strat_shift_char_index @0x1C9218 maps strategy state (0..99) to characteristic,
but which states a mode occupies lives in the program ROM. You do not have to
wait for that: --identify finds it by experiment.

    xdf_shiftpoints.py stock.bin --identify 8 -o probe.bin

That makes ONE characteristic unmistakable - it holds 2nd gear to the rev cap
and nothing else changes - so you flash it, drive each mode, and whichever mode
suddenly refuses to leave 2nd is the mode that uses characteristic 8. Record it
and move on:

    xdf_shiftpoints.py stock.bin --set-mode sport=8,14

which writes modes.json beside the XDF. After that --mode sport works. The
marker is deliberately a hold-longer change, not a shift-early one, so a
mis-identified characteristic cannot leave the car lugging.

Checksums are not corrected - sign before flashing, and gate the result:

    xdf_verify.py 8hpe70_cali_v3.xdf stock.bin out.bin

Examples:
    xdf_shiftpoints.py stock.bin --chars 8 --up-pct 12 --preview
    xdf_shiftpoints.py stock.bin --mode sport --up-pct 12 -o out.bin
    xdf_shiftpoints.py stock.bin --mode normal --up-pct -5 --dn-pct -5 -o out.bin
"""
import argparse
import json
import os
import re
import sys

from xdflib import (XDF, load_bin, decode_table, element_offset, write_elem,
                    check_calibration)

XDF_DEFAULT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           '..', '8hpe70_cali_v3.xdf')
MODES_FILE = 'modes.json'

UP_RX = re.compile(r'^Upshift char (\d+): (\d)>(\d)$')
DN_RX = re.compile(r'^Downshift char (\d+): (\d)>(\d)$')

SENTINEL = 8000          # >= this means "shift disabled" - never touch it
# 8HP45 ratios, used only to turn an output-rpm line into the engine speed it
# implies so the cap means something. Override with --ratios if yours differ.
RATIOS = {1: 4.714, 2: 3.143, 3: 2.106, 4: 1.667, 5: 1.285, 6: 1.0,
          7: 0.839, 8: 0.667}


def collect(xdf):
    """-> {(char, 'N>M', kind): table}, deduplicated by z address."""
    out, seen = {}, set()
    for t in xdf.tables:
        m, kind = UP_RX.match(t.title), 'up'
        if not m:
            m, kind = DN_RX.match(t.title), 'down'
        if not m:
            continue
        emb = t.z.embedded if t.z else None
        if emb is None or emb.address is None or emb.address in seen:
            continue
        seen.add(emb.address)
        out[(int(m.group(1)), f'{m.group(2)}>{m.group(3)}', kind)] = t
    return out


def load_modes(xdf_path):
    path = os.path.join(os.path.dirname(os.path.abspath(xdf_path)), MODES_FILE)
    if not os.path.exists(path):
        return {}, path
    try:
        with open(path, encoding='utf-8') as f:
            raw = json.load(f)
        return {k: {int(c) for c in v} for k, v in raw.items()}, path
    except (ValueError, TypeError, AttributeError) as e:
        sys.exit(f'{path} is malformed (expected {{"sport": [ints], ...}}): {e}')


def gear_of(pair, kind):
    """The gear being left: 2>3 upshift leaves 2nd; 3>2 downshift leaves 3rd."""
    a, b = (int(x) for x in pair.split('>'))
    return a


def cap_for(pair, kind, max_engine_rpm, ratios):
    """Largest output rpm whose implied engine speed stays under the cap."""
    r = ratios.get(gear_of(pair, kind))
    return None if not r else max_engine_rpm / r


def plan(buf, tables, chars, up_pct=0.0, dn_pct=0.0, up_rpm=0.0, dn_rpm=0.0,
         pedal_from=0.0, min_gap=150, max_engine_rpm=7000, ratios=None):
    """Apply the shift-point move to buf in place.

    Upshifts are done before downshifts so the anti-hunting guard measures
    against the upshift values the box will actually use, not the old ones.
    -> (changed_cells, lines_touched, capped_at_rev_limit, held_below_upshift)
    """
    ratios = ratios or RATIOS
    changed = clamped_gap = clamped_rev = 0
    touched = set()
    for kind, pct, flat in (('up', up_pct, up_rpm), ('down', dn_pct, dn_rpm)):
        if not pct and not flat:
            continue
        for (ch, pair, k), t in sorted(tables.items()):
            if k != kind or ch not in chars:
                continue
            rows, cols = t.shape()
            emb = t.z.embedded
            d = decode_table(buf, t)
            pedal = d['x']
            up_t = tables.get((ch, f'{pair.split(">")[1]}>{pair.split(">")[0]}', 'up'))
            up_z = decode_table(buf, up_t)['z'] if (kind == 'down' and up_t) else None
            cap = cap_for(pair, kind, max_engine_rpm, ratios) if kind == 'up' else None
            for r in range(rows):
                for c in range(cols):
                    v = d['z'][r][c]
                    if v <= 0 or v >= SENTINEL:
                        continue
                    idx = c if cols >= rows else r
                    pv = pedal[idx] if pedal and idx < len(pedal) else 0
                    if isinstance(pv, (int, float)) and pv < pedal_from:
                        continue
                    new = v * (1 + pct / 100.0) + flat
                    if cap is not None and new > cap:
                        new = cap
                        clamped_rev += 1
                    if up_z is not None:
                        u = up_z[r][c]
                        if 0 < u < SENTINEL and new > u - min_gap:
                            new = u - min_gap
                            clamped_gap += 1
                    new = max(0, min(SENTINEL - 1, round(new)))
                    if new != v:
                        write_elem(buf, element_offset(emb, rows, cols, r, c),
                                   emb, new)
                        changed += 1
                        touched.add((ch, pair, kind))
    return changed, len(touched), clamped_rev, clamped_gap


def main():
    ap = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('bin')
    ap.add_argument('-o', '--out')
    ap.add_argument('--xdf', default=XDF_DEFAULT)
    ap.add_argument('--mode', help=f'a key from {MODES_FILE} beside the XDF')
    ap.add_argument('--chars', help='characteristics to edit, e.g. 8,14')
    ap.add_argument('--up-pct', type=float, default=0.0,
                    help='move upshift lines by this %% (+ = hold gears longer)')
    ap.add_argument('--dn-pct', type=float, default=0.0,
                    help='move downshift lines by this %% (+ = downshift sooner)')
    ap.add_argument('--up-rpm', type=float, default=0.0,
                    help='flat output-rpm change on upshift lines instead')
    ap.add_argument('--dn-rpm', type=float, default=0.0)
    ap.add_argument('--pedal-from', type=float, default=0.0,
                    help='only touch pedal positions at or above this per mille')
    ap.add_argument('--min-gap', type=float, default=150,
                    help='keep downshift lines this far below upshift (default 150)')
    ap.add_argument('--max-engine-rpm', type=float, default=7000,
                    help='cap implied engine speed (default 7000; TCU guard ~7100)')
    ap.add_argument('--ratios', help='override gear ratios, e.g. 1:4.7,2:3.1,...')
    ap.add_argument('--identify', type=int, metavar='CH',
                    help='make characteristic CH unmistakable (holds 2nd to the '
                         'rev cap) so you can find which mode uses it by driving')
    ap.add_argument('--set-mode', metavar='NAME=CH[,CH]',
                    help=f'record a mode in {MODES_FILE} beside the XDF and exit')
    ap.add_argument('--any-calibration', action='store_true')
    ap.add_argument('--preview', action='store_true')
    args = ap.parse_args()

    if args.set_mode:
        if '=' not in args.set_mode:
            ap.error('--set-mode looks like  sport=8,14')
        name, chars_s = args.set_mode.split('=', 1)
        groups, path = load_modes(args.xdf)
        groups[name.strip()] = {int(c) for c in chars_s.split(',') if c.strip()}
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({k: sorted(v) for k, v in groups.items()}, f, indent=1)
        print(f'{path}: ' + ', '.join(f'{k} = {sorted(v)}' for k, v in
                                      sorted(groups.items())))
        return
    if not args.preview and not args.out:
        ap.error('give -o OUT, or use --preview')
    if args.identify is None and not any(
            (args.up_pct, args.dn_pct, args.up_rpm, args.dn_rpm)):
        ap.error('nothing to do: give --up-pct/--dn-pct, --up-rpm/--dn-rpm, '
                 '--identify or --set-mode')
    if args.identify is not None:
        # One characteristic, one unmistakable symptom: hold 2nd to the cap.
        args.chars = str(args.identify)
        args.up_pct = 49.0
        args.dn_pct = 0.0
        args.up_rpm = args.dn_rpm = 0.0
        args.pedal_from = 0.0
    for name, v in (('--up-pct', args.up_pct), ('--dn-pct', args.dn_pct)):
        if not -50 <= v <= 50:
            sys.exit(f'{name} must be within -50..50')

    ratios = dict(RATIOS)
    if args.ratios:
        for part in args.ratios.split(','):
            g, r = part.split(':')
            ratios[int(g)] = float(r)

    xdf = XDF(args.xdf)
    stock = load_bin(args.bin)
    ok, msg = check_calibration(stock, os.path.basename(args.bin))
    if ok:
        print(msg)
    elif args.any_calibration:
        print('WARNING: ' + msg, file=sys.stderr)
    else:
        sys.exit(msg + '\n\nRefusing to edit.')

    tables = collect(xdf)
    all_chars = sorted({c for c, _p, _k in tables})
    if args.chars:
        chars = {int(c) for c in args.chars.split(',')}
    elif args.mode:
        groups, path = load_modes(args.xdf)
        if args.mode not in groups or not groups[args.mode]:
            sys.exit(
                f'no characteristics assigned to "{args.mode}". Which '
                'characteristic each drive mode uses is not recorded in the '
                'calibration - it comes from the strategy state table '
                f'strat_shift_char_index @0x1C9218 and needs the program ROM to '
                f'pin down. Either pass --chars, or write {path} as e.g. '
                '{"sport": [8, 14], "normal": [0, 15]}.')
        chars = groups[args.mode]
    else:
        ap.error('say which characteristics: --mode or --chars')
    unknown = chars - set(all_chars)
    if unknown:
        sys.exit(f'no such characteristic(s): {sorted(unknown)} '
                 f'(this XDF has {all_chars[0]}..{all_chars[-1]})')

    buf = bytearray(stock)
    changed, n_lines, clamped_rev, clamped_gap = plan(
        buf, tables, chars, args.up_pct, args.dn_pct, args.up_rpm, args.dn_rpm,
        args.pedal_from, args.min_gap, args.max_engine_rpm, ratios)
    touched_pairs = range(n_lines)

    print(f'characteristics {sorted(chars)}: upshift {args.up_pct:+g}%'
          + (f' {args.up_rpm:+g} rpm' if args.up_rpm else '')
          + f', downshift {args.dn_pct:+g}%'
          + (f' {args.dn_rpm:+g} rpm' if args.dn_rpm else ''))
    print(f'{changed} cells changed across {len(touched_pairs)} lines')
    if clamped_rev:
        print(f'  {clamped_rev} cells capped at {args.max_engine_rpm:g} engine rpm')
    if clamped_gap:
        print(f'  {clamped_gap} downshift cells held {args.min_gap:g} rpm below '
              'their upshift line (anti-hunting)')

    ch0 = sorted(chars)[0]
    print(f'\nchar {ch0:02d} at full pedal, output rpm (implied engine rpm):')
    print('  pair    stock          tuned')
    for pair in ('1>2', '2>3', '3>4', '4>5', '5>6', '6>7', '7>8'):
        t = tables.get((ch0, pair, 'up'))
        if t is None:
            continue
        a = [v for row in decode_table(stock, t)['z'] for v in row][-1]
        b = [v for row in decode_table(buf, t)['z'] for v in row][-1]
        r = ratios.get(gear_of(pair, 'up'), 0)
        print(f'  {pair}  {a:5d} ({a * r:5.0f})   {b:5d} ({b * r:5.0f})')

    if args.preview:
        print('\npreview only, no file written')
        return
    with open(args.out, 'wb') as f:
        f.write(buf)
    print(f'\nwrote {args.out} (checksum NOT corrected - sign before flashing)')


if __name__ == '__main__':
    main()
