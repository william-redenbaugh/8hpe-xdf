#!/usr/bin/env python3
"""One-shot tuning operations on a calibration bin, from the analysis docs.

Every subcommand reads BIN, applies one documented change, and writes -o OUT
(never in place). Chain them by feeding one output into the next command.
Checksums are not corrected here - run xdf_checksum.py sign (or let your
flash tool correct them) before flashing.

  shift-offset   move shift points: +/- rpm on the selected upshift lines
                 (optionally dragging the matching downshift lines along)
  quickness      shorten the documented shift-execution phase/sync time
                 tables by a percentage (faster, firmer shifts)
  sport-redline  rev out 1st and 2nd to --rpm (default 7000) by raising the
                 1>2/2>3 upshift lines, only from --pedal-from permille up
  redline-hold   raise the 1>2/2>3/3>4 upshift lines of all
                 characteristics to engine redline / gear ratio
  early-upshift  NA mode: lower all upshift lines pedal-weighted (full at
                 closed throttle, zero from 80% pedal), clamped >= the
                 matching downshift line + 100 rpm
  wheel          show or set the Radumfang wheel circumference (mm), with
                 --tire 225/45R17-style calculation
  diff-check     check a diff ratio against the TCU's fixed learn list and
                 suggest the circumference trim that makes learning land
  tcc-na         NA converter strategy: scale TCC slip targets / pedal
                 weighting / coast micro-slip (see n52k-tcc-optimization.md)
  copy-tables    import named tables (e.g. the tcmodel K/mu converter model
                 from an N20 or N55 donor read) decoded via the donor's XDF

Examples:
  xdf_tune.py shift-offset  my.bin -o out.bin --rpm +300
  xdf_tune.py quickness     my.bin -o out.bin --pct 15
  xdf_tune.py sport-redline my.bin -o out.bin --rpm 7000
  xdf_tune.py redline-hold  my.bin -o out.bin --redline 7000
  xdf_tune.py early-upshift my.bin -o out.bin --rpm 400
  xdf_tune.py wheel         my.bin -o out.bin --tire 245/40R18
  xdf_tune.py diff-check    my.bin --ratio 3.73 --learned 3.91 --fix -o out.bin
  xdf_tune.py tcc-na        my.bin -o out.bin --slip-pct -15 --pedal-pct -20
  xdf_tune.py copy-tables   my.bin -o out.bin --donor n20_read.bin \\
      --donor-xdf n20.xdf --tables tcmodel_K_curve,tcmodel_mu_curve
"""
import argparse
import math
import os
import re
import sys

from xdflib import XDF, decode_table, decode_constant, element_offset, write_elem

def _default_xdf():
    here = os.path.dirname(os.path.abspath(__file__))
    for name in ('8hpe84_cali_v1.xdf', '8hpe70_cali_v3.xdf', '8hpe_cali_v3.xdf'):
        cand = os.path.join(here, '..', name)
        if os.path.exists(cand):
            return cand
    return os.path.join(here, '..', '8hpe84_cali_v1.xdf')


XDF_DEFAULT = _default_xdf()
SENTINEL = 7900
UP_CURVE = re.compile(r'^Upshift char (\d+): (\d)>(\d)$')
DN_CURVE = re.compile(r'^Downshift char (\d+): (\d)>(\d)$')
QUICK_RX = re.compile(r'(ph\d+_time|sync_time|phase.*time|_time_|rampout)', re.I)
EXEC_CATS = ('Shift execution: upshift', 'Shift execution: downshift',
             'Shift execution: timing control', 'Shift execution: other')
RATIO_LIST = [2.00, 2.35, 2.47, 2.56, 2.65, 2.81, 2.93, 3.08, 3.15, 3.23,
              3.38, 3.46, 3.64, 3.73, 3.91, 4.10, 4.27]


# ---------------------------------------------------------------- helpers

def shift_curves(xdf, kinds=('up', 'down'), pairs=None, chars=None):
    """Deduped per-gear-pair single shift-line curves."""
    out, seen = [], set()
    for t in xdf.tables:
        m, kind = UP_CURVE.match(t.title), 'up'
        if not m:
            m, kind = DN_CURVE.match(t.title), 'down'
        if not m or kind not in kinds:
            continue
        emb = t.z.embedded
        if emb.address is None or emb.address in seen:
            continue
        char = int(m.group(1))
        lo, hi = sorted((m.group(2), m.group(3)))
        pair = f'{lo}>{hi}'
        if pairs is not None and pair not in pairs:
            continue
        if chars is not None and char not in chars:
            continue
        seen.add(emb.address)
        out.append((t, kind, char, pair))
    return out


def edit_cells(buf, table, fn):
    """fn(r, c, value, decoded) -> new value or None; returns changed count."""
    rows, cols = table.shape()
    emb = table.z.embedded
    d = decode_table(buf, table)
    n = 0
    for r in range(rows):
        for c in range(cols):
            new = fn(r, c, d['z'][r][c], d)
            if new is None or new == d['z'][r][c]:
                continue
            write_elem(buf, element_offset(emb, rows, cols, r, c), emb, new)
            n += 1
    return n


def find_constant(xdf, needle):
    hits = [c for c in xdf.constants if needle.lower() in c.title.lower()]
    if len(hits) != 1:
        sys.exit(f'{len(hits)} constants match {needle!r}')
    return hits[0]


def tire_circumference(spec):
    """'225/45R17' -> rolling circumference in mm (x0.97 dynamic factor)."""
    m = re.match(r'^(\d{3})/(\d{2})\s*R?\s*(\d{2}(?:\.\d)?)$', spec.strip(), re.I)
    if not m:
        raise ValueError(f'cannot parse tire size {spec!r} (expected like 225/45R17)')
    width, profile, rim = float(m.group(1)), float(m.group(2)), float(m.group(3))
    return math.pi * (rim * 25.4 + 2 * width * profile / 100) * 0.97


# ---------------------------------------------------------------- operations

def op_shift_offset(buf, xdf, rpm, pairs=None, chars=None, move_down=True):
    kinds = ('up', 'down') if move_down else ('up',)
    total = 0
    for t, _k, _c, _p in shift_curves(xdf, kinds, pairs, chars):
        total += edit_cells(buf, t, lambda r, c, v, d:
                            None if (v <= 0 or v >= SENTINEL)
                            else max(0, v + rpm))
    return total


def op_quickness(buf, xdf, pct):
    factor = 1 - pct / 100.0
    total, tables = 0, 0
    seen = set()
    for t in xdf.tables:
        emb = t.z.embedded if t.z else None
        if (not emb or emb.address is None or emb.address in seen
                or emb.elem_bits != 8 or emb.is_float
                or not any(c in EXEC_CATS for c in t.categories)
                or not QUICK_RX.search(t.title)):
            continue
        seen.add(emb.address)
        tables += 1
        total += edit_cells(buf, t, lambda r, c, v, d:
                            None if (v <= 0 or v >= 250)
                            else max(1, round(v * factor)))
    return total, tables


def op_redline_hold(buf, xdf, redline, margin_pct, ratios):
    """ratios: {'1>2': r1st, '2>3': r2nd, '3>4': r3rd}"""
    targets = {p: round(redline * (1 - margin_pct / 100.0) / r)
               for p, r in ratios.items()}
    total = 0
    for t, _k, _c, pair in shift_curves(xdf, ('up',), set(targets)):
        tgt = targets[pair]
        total += edit_cells(buf, t, lambda r, c, v, d:
                            None if (v <= 0 or v >= SENTINEL)
                            else max(v, tgt))
    return total, targets


def op_sport_redline(buf, xdf, rpm, margin_pct, ratios, pedal_from, chars=None):
    """Hold 1st/2nd (pairs in ratios) to `rpm` from `pedal_from` permille up.

    Raises the matching upshift lines to rpm/ratio only at pedal breakpoints
    >= pedal_from, so light-throttle shifts stay stock and the box revs out
    when pushed. chars limits which characteristics are touched (default all;
    the E84 char-to-drive-mode mapping lives in the missing program ROM, so
    identify the sport characteristic by logging, or edit all).
    """
    targets = {p: round(rpm * (1 - margin_pct / 100.0) / r)
               for p, r in ratios.items()}
    total = 0
    for t, _k, _c, pair in shift_curves(xdf, ('up',), set(targets), chars):
        tgt = targets[pair]

        def fn(r, c, v, d):
            if v <= 0 or v >= SENTINEL:
                return None
            pedal = d['x'][c] if d['x'] and isinstance(d['x'][c], (int, float)) else 0
            if pedal < pedal_from:
                return None
            return max(v, tgt)

        total += edit_cells(buf, t, fn)
    return total, targets


def op_early_upshift(buf, xdf, rpm):
    down = {(c, p): t for t, _k, c, p in shift_curves(xdf, ('down',))}
    total = clamped = 0
    for t, _k, char, pair in shift_curves(xdf, ('up',)):
        dt = down.get((char, pair))
        dvals = decode_table(buf, dt)['z'] if dt is not None else None

        def fn(r, c, v, d, dvals=dvals):
            nonlocal clamped
            if v <= 0 or v >= SENTINEL:
                return None
            pedal = d['x'][c] if d['x'] and isinstance(d['x'][c], (int, float)) else 0
            weight = max(0.0, 1 - pedal / 800.0)
            if weight <= 0:
                return None
            new = v - rpm * weight
            if dvals is not None and dvals[r][c] < SENTINEL and dvals[r][c] > 0:
                floor = dvals[r][c] + 100
                if new < floor:
                    new = floor
                    clamped += 1
            return max(0, round(new))

        total += edit_cells(buf, t, fn)
    return total, clamped


def op_wheel(buf, xdf, mm=None):
    const = find_constant(xdf, 'Radumfang')
    emb = const.embedded
    old = decode_constant(buf, const)
    if mm is not None:
        write_elem(buf, emb.address, emb, round(mm))
    return old, (round(mm) if mm is not None else old)


def diff_report(ratio, learned=None, circ=None):
    nearest = min(RATIO_LIST, key=lambda x: abs(x - ratio))
    dev = (ratio - nearest) / nearest * 100
    lines = [f'real diff ratio {ratio:.3f}: nearest TCU list entry {nearest:.2f} '
             f'({dev:+.2f}% off; acceptance window is about -1%/+2.5%)']
    suggestion = None
    if learned is not None and circ is not None:
        if abs(learned - nearest) < 1e-6 or abs(learned - ratio) / ratio < 0.005:
            lines.append(f'learned value {learned:.2f} already matches - no change needed.')
        else:
            suggestion = circ * ratio / learned
            lines.append(
                f'learned {learned:.2f} != real {ratio:.3f}: set circumference to '
                f'{suggestion:.0f} mm (= {circ:.0f} x {ratio:.3f}/{learned:.2f}), '
                'reflash, reset the learned value (Tool32 '
                'steuern_lernfkt_ruecksetzen 0) and drive >24 km/h to re-learn.')
    return lines, suggestion


def op_copy_tables(buf, xdf, donor_buf, donor_xdf, titles):
    """Copy named tables from a donor bin (decoded via ITS xdf) into buf."""
    copied = []
    for title in titles:
        src = [t for t in donor_xdf.tables if t.title == title]
        dst = [t for t in xdf.tables if t.title == title]
        if not src or not dst:
            raise ValueError(f'{title!r}: found {len(src)} in donor XDF, '
                             f'{len(dst)} in target XDF (need exactly 1 each)')
        s, t = src[0], dst[0]
        if s.shape() != t.shape():
            raise ValueError(f'{title!r}: donor shape {s.shape()} != target {t.shape()}')
        vals = decode_table(donor_buf, s)['z']
        rows, cols = t.shape()
        emb = t.z.embedded
        for r in range(rows):
            for c in range(cols):
                write_elem(buf, element_offset(emb, rows, cols, r, c), emb,
                           vals[r][c])
        # axes too, when both sides store live axes of equal length
        for axid in ('x', 'y'):
            sa, ta = s.axes.get(axid), t.axes.get(axid)
            if (sa and ta and sa.embedded.address is not None
                    and ta.embedded.address is not None
                    and (sa.count or 0) == (ta.count or 0)):
                avals = decode_table(donor_buf, s)  # axes decoded above
                src_axis = avals[axid]
                for k, v in enumerate(src_axis or []):
                    if isinstance(v, (int, float)):
                        write_elem(buf, element_offset(
                            ta.embedded, 1, ta.count, 0, k), ta.embedded, v)
        copied.append((title, rows * cols))
    return copied


def op_tcc_na(buf, xdf, slip_pct=0, pedal_pct=0, negslip_pct=0):
    """Directional NA adjustments from docs/analysis/n52k-tcc-optimization.md.
    Percentages are applied to raw values; negative = reduce slip/weight."""
    jobs = [('tcc_slip_target_map', slip_pct),
            ('tcc_pedal_weight_curve', pedal_pct),
            ('tcc_neg_slip_curve', negslip_pct)]
    done = []
    for title, pct in jobs:
        if not pct:
            continue
        hits = [t for t in xdf.tables if t.title == title]
        if len(hits) != 1:
            raise ValueError(f'{title}: {len(hits)} matches in XDF')
        factor = 1 + pct / 100.0
        n = edit_cells(buf, hits[0], lambda r, c, v, d:
                       None if v == 0 else
                       (v * factor if isinstance(v, float) else round(v * factor)))
        done.append((title, pct, n))
    return done


# ---------------------------------------------------------------- CLI

def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--xdf', default=XDF_DEFAULT)
    sub = ap.add_subparsers(dest='cmd', required=True)

    def common(p, needs_out=True):
        p.add_argument('bin')
        p.add_argument('-o', '--out', required=needs_out)

    p = sub.add_parser('shift-offset')
    common(p)
    p.add_argument('--rpm', type=float, required=True)
    p.add_argument('--pairs', help='e.g. 1>2,2>3 (default: all)')
    p.add_argument('--chars', help='e.g. 0,1,2 (default: all 23)')
    p.add_argument('--no-down', action='store_true',
                   help='do not drag the matching downshift lines along')

    p = sub.add_parser('quickness')
    common(p)
    p.add_argument('--pct', type=float, required=True, help='0-40, faster by %%')

    p = sub.add_parser('sport-redline')
    common(p)
    p.add_argument('--rpm', type=float, default=7000,
                   help='engine rpm to rev out to in 1st/2nd (default 7000)')
    p.add_argument('--margin', type=float, default=2, help='%% below --rpm')
    p.add_argument('--r1', type=float, default=4.714, help='1st gear ratio (8HP45)')
    p.add_argument('--r2', type=float, default=3.143, help='2nd gear ratio (8HP45)')
    p.add_argument('--pedal-from', type=float, default=400,
                   help='apply from this pedal permille up (default 400; 0 = everywhere)')
    p.add_argument('--chars', help='characteristic numbers, e.g. 8,9 (default: all)')

    p = sub.add_parser('redline-hold')
    common(p)
    p.add_argument('--redline', type=float, default=7000)
    p.add_argument('--margin', type=float, default=2, help='%% below redline')
    p.add_argument('--r1', type=float, default=4.714, help='1st gear ratio')
    p.add_argument('--r2', type=float, default=3.143)
    p.add_argument('--r3', type=float, default=2.106)

    p = sub.add_parser('early-upshift')
    common(p)
    p.add_argument('--rpm', type=float, required=True,
                   help='reduction at closed throttle (0-800)')

    p = sub.add_parser('wheel')
    common(p, needs_out=False)
    p.add_argument('--mm', type=float)
    p.add_argument('--tire', help='e.g. 225/45R17 (overrides --mm)')

    p = sub.add_parser('diff-check')
    common(p, needs_out=False)
    p.add_argument('--ratio', type=float, required=True, help='real diff ratio')
    p.add_argument('--learned', type=float,
                   help='learned value from Tool32 status_lernfkt')
    p.add_argument('--fix', action='store_true',
                   help='write the suggested circumference (needs -o and --learned)')

    p = sub.add_parser('tcc-na')
    common(p)
    p.add_argument('--slip-pct', type=float, default=0,
                   help='e.g. -15 lowers tcc_slip_target_map 15%%')
    p.add_argument('--pedal-pct', type=float, default=0,
                   help='e.g. -20 lowers tcc_pedal_weight_curve 20%%')
    p.add_argument('--negslip-pct', type=float, default=0,
                   help='e.g. -50 halves coast micro-slip (tcc_neg_slip_curve)')

    p = sub.add_parser('copy-tables')
    common(p)
    p.add_argument('--donor', required=True, help='donor bin (e.g. N20/N55 read)')
    p.add_argument('--donor-xdf', help='XDF matching the donor (default: --xdf)')
    p.add_argument('--tables', default='tcmodel_K_curve,tcmodel_mu_curve')

    args = ap.parse_args()
    xdf = XDF(args.xdf)
    buf = bytearray(open(args.bin, 'rb').read())
    if len(buf) != 0x200000:
        print(f'warning: {args.bin} is {len(buf)} bytes, expected 2 MB',
              file=sys.stderr)

    if args.cmd == 'shift-offset':
        pairs = set(args.pairs.split(',')) if args.pairs else None
        chars = {int(c) for c in args.chars.split(',')} if args.chars else None
        n = op_shift_offset(buf, xdf, args.rpm, pairs, chars,
                            move_down=not args.no_down)
        print(f'shift-offset {args.rpm:+.0f} rpm: {n} cells changed')
    elif args.cmd == 'quickness':
        n, tables = op_quickness(buf, xdf, args.pct)
        print(f'quickness -{args.pct:.0f}%: {n} cells across {tables} time tables')
    elif args.cmd == 'sport-redline':
        chars = ({int(x) for x in args.chars.split(',')} if args.chars else None)
        n, targets = op_sport_redline(buf, xdf, args.rpm, args.margin,
                                      {'1>2': args.r1, '2>3': args.r2},
                                      args.pedal_from, chars)
        print(f'sport-redline {args.rpm:.0f} rpm from pedal {args.pedal_from:.0f}: '
              f'targets (output rpm) {targets}; {n} cells raised')
        if args.rpm > 7100:
            print('warning: above the ~7100 rpm stock TCU guard', file=sys.stderr)
    elif args.cmd == 'redline-hold':
        n, targets = op_redline_hold(buf, xdf, args.redline, args.margin,
                                     {'1>2': args.r1, '2>3': args.r2, '3>4': args.r3})
        print(f'redline-hold: targets (output rpm) {targets}; {n} cells raised')
        if args.redline >= 7100:
            print('warning: redline >= the ~7100 rpm stock TCU guard - apply '
                  'the True manual patch first', file=sys.stderr)
    elif args.cmd == 'early-upshift':
        n, clamped = op_early_upshift(buf, xdf, args.rpm)
        print(f'early-upshift -{args.rpm:.0f} rpm pedal-weighted: {n} cells '
              f'({clamped} clamped to downshift+100)')
    elif args.cmd == 'wheel':
        mm = tire_circumference(args.tire) if args.tire else args.mm
        old, new = op_wheel(buf, xdf, mm)
        if mm is None:
            print(f'programmed wheel circumference: {old} mm')
            return
        print(f'wheel circumference: {old} -> {new} mm'
              + (f' (from tire {args.tire})' if args.tire else ''))
        if not args.out:
            sys.exit('setting the value needs -o OUT')
    elif args.cmd == 'diff-check':
        const = find_constant(xdf, 'Radumfang')
        circ = decode_constant(buf, const)
        print(f'programmed circumference: {circ} mm')
        lines, suggestion = diff_report(args.ratio, args.learned, circ)
        print('\n'.join(lines))
        if args.fix:
            if suggestion is None:
                sys.exit('--fix needs --learned with a mismatching value')
            if not args.out:
                sys.exit('--fix needs -o OUT')
            op_wheel(buf, xdf, suggestion)
            print(f'written: circumference {circ} -> {round(suggestion)} mm')
        elif not args.out:
            return
    elif args.cmd == 'tcc-na':
        done = op_tcc_na(buf, xdf, args.slip_pct, args.pedal_pct, args.negslip_pct)
        for title, pct, n in done:
            print(f'{title}: {pct:+.0f}% on {n} cells')
        print('REMINDER: reset TCC adaptation after flashing and probe for '
              'low-rpm shudder (see docs/analysis/n52k-tcc-optimization.md)')
    elif args.cmd == 'copy-tables':
        donor_xdf = XDF(args.donor_xdf) if args.donor_xdf else xdf
        donor = bytearray(open(args.donor, 'rb').read())
        copied = op_copy_tables(buf, xdf, donor, donor_xdf,
                                [t.strip() for t in args.tables.split(',')])
        for title, n in copied:
            print(f'copied {title}: {n} cells (+ live axes where present)')

    if args.out:
        with open(args.out, 'wb') as f:
            f.write(buf)
        print(f'wrote {args.out} (checksum NOT corrected - sign before flashing)')


if __name__ == '__main__':
    main()
