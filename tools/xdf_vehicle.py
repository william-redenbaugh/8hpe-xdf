#!/usr/bin/env python3
"""Wheel circumference and final drive - what a swapped or re-geared car must get right.

Two subcommands:

  wheel   read, or set, the Radumfang constant: the dynamic (rolling) wheel
          circumference in mm. Give it a tyre size or a number of millimetres.
  diff    check a real final-drive ratio against the fixed list the TCU snaps
          to, and work out the circumference trim that makes it learn the
          right entry.

The two belong together because the TCU has no "axle ratio" setting. It
derives the final drive from wheel speed and output-shaft speed, and the only
calibration input to that is the circumference. Get the circumference wrong
and the box learns the wrong axle, which moves every shift point and every
ratio-monitor band with it.

What is verified here, on the reference read (b5yc1111 / C118):

  * Radumfang is the only constant in the XDF whose title mentions a wheel
    circumference; it is a u16 big-endian at 0x195F10 and decodes to 2249 mm.
    That is a sane value and it is the right one for this car: the E70's
    stock 255/55R18 and 255/50R19 fitments both come out at 2248 mm through
    the formula below, 1 mm from what is programmed. The address is looked up
    through the XDF by title at run time, not hardcoded.
  * The ratio list is really in the image. This tool finds it by structure
    rather than by address: a u32 big-endian count followed by that many u16
    big-endian hundredths, ascending, in a plausible ratio range. In the
    reference image exactly one block in the whole calibration matches, at
    0x19147C (count word 20 at 0x191478, 20 slots, 17 distinct values, the
    top entry repeated to fill the rest). Those 17 values are exactly the
    list the XDF's own Radumfang description names. A sibling calibration is
    documented as holding it at 0x1916B4; that address holds something else
    here, which is why the tool searches instead of trusting it.

What is NOT verified, and matters:

  * No reader function is known for the list block. The XDF covers those
    bytes only as the auto-detected x axis of 'auto_191474', an item rated
    LOW confidence whose evidence line says "Meaning not analysed. Read by:
    unknown". The count-prefixed layout is consistent with its neighbours in
    the same region (0x1914A4 holds a count-6 table in the same shape) but
    that is a reading, not proof.
  * That the TCU snaps to the nearest entry at all, and the -1%/+2.5%
    acceptance window, come from the XDF's Radumfang description, not from
    traced code. Same for the trim arithmetic: the description says to
    multiply your entry by (real ratio / learned value) and repeat, which is
    what --learned computes. It assumes the learned ratio moves in direct
    proportion to the programmed circumference.

After flashing a new circumference: reset the learned rear-axle value (Tool32
job steuern_lernfkt_ruecksetzen, argument 0) and drive above about 24 km/h so
it re-learns, then read status_lernfkt - the learned value must equal your
real diff ratio. One step off means another pass of 'diff --learned'. Do not
use this to correct the speedometer; that is the DSC's coding.

Checksums are not corrected - sign before flashing, and always gate the result:

    xdf_verify.py 8hpe70_cali_v3.xdf stock.bin out.bin

Examples:
    xdf_vehicle.py wheel stock.bin                        # read it
    xdf_vehicle.py wheel stock.bin --tire 245/40R18 --preview
    xdf_vehicle.py wheel stock.bin --tire 245/40R18 -o out.bin
    xdf_vehicle.py wheel stock.bin --mm 2185 -o out.bin
    xdf_vehicle.py diff  stock.bin                        # just show the list
    xdf_vehicle.py diff  stock.bin --ratio 3.46
    xdf_vehicle.py diff  stock.bin --ratio 3.73 --learned 3.91 --fix -o out.bin
"""
import argparse
import math
import os
import re
import struct
import sys

from xdflib import (XDF, load_bin, decode_constant, write_elem,
                    check_calibration)

XDF_DEFAULT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           '..', '8hpe70_cali_v3.xdf')

CAL_START, CAL_END = 0x180200, 0x200000

# Uninitialised 0xFF stretches seen in the reference read. A value read out of
# one of these is unverifiable, not zero and not empty - say so rather than
# concluding anything from it.
HOLES = ((0x180280, 0x190100), (0x1D3D2A, 0x1FFD60))

# The list the XDF's Radumfang description names. Only a cross-check: the
# ratios actually used come from the image (find_ratio_list).
DOCUMENTED_RATIOS = (2.00, 2.35, 2.47, 2.56, 2.65, 2.81, 2.93, 3.08, 3.15,
                     3.23, 3.38, 3.46, 3.64, 3.73, 3.91, 4.10, 4.27)

# Documented acceptance window around a list entry, in percent.
WINDOW_LO, WINDOW_HI = -1.0, 2.5

# Circumferences outside this are refused outright; outside the inner band
# they are written but flagged. A 2 m to 2.5 m circumference covers anything
# an 8HP sits behind; 500 mm or 5 m is a typo, not a tyre.
SANE_MM = (1200.0, 3600.0)
TYPICAL_MM = (1700.0, 2600.0)

TIRE_RX = re.compile(r'^(\d{3})\s*/\s*(\d{2})\s*[RrZz]?\s*(\d{2}(?:\.\d)?)$')


# ------------------------------------------------------------------ wheel

def wheel_constant(xdf):
    """The Radumfang constant, found through the XDF by title."""
    hits = [c for c in xdf.constants
            if 'radumfang' in c.title.lower()
            or 'wheel circumference' in c.title.lower()]
    if len(hits) != 1:
        sys.exit(f'{len(hits)} constants in {xdf.path} look like the wheel '
                 'circumference (expected exactly one titled "Radumfang") - '
                 'is this the E70 XDF?')
    return hits[0]


def tire_size(spec):
    """'225/45R17' -> (width_mm, profile_pct, rim_inch)."""
    m = TIRE_RX.match(spec.strip())
    if not m:
        raise ValueError(f'cannot parse tyre size {spec!r} '
                         '(expected something like 225/45R17)')
    return float(m.group(1)), float(m.group(2)), float(m.group(3))


def tire_circumference(spec):
    """'225/45R17' -> dynamic rolling circumference in mm.

    pi * (rim_inch * 25.4 + 2 * width_mm * profile_pct / 100) * 0.97, the
    formula the XDF gives in the Radumfang description. The 0.97 is the
    dynamic factor: a loaded, rolling tyre travels slightly less per turn
    than its geometric circumference. The XDF's worked example, 225/45R17 =
    1933 mm, is what this returns.
    """
    width, profile, rim = tire_size(spec)
    return math.pi * (rim * 25.4 + 2 * width * profile / 100) * 0.97


def in_hole(addr, size=1):
    for lo, hi in HOLES:
        if addr < hi and lo < addr + size:
            return (lo, hi)
    return None


def read_circumference(buf, const):
    """-> (value_mm, note). note is None when the read looks trustworthy."""
    emb = const.embedded
    size = emb.elem_bits // 8
    raw = bytes(buf[emb.address:emb.address + size])
    value = decode_constant(buf, const)
    note = None
    if raw == b'\xff' * size:
        hole = in_hole(emb.address, size)
        note = ('reads all-0xFF' + (
            f' and sits in the uninitialised 0x{hole[0]:X}-0x{hole[1]:X} '
            'region of this image, so the value is UNVERIFIABLE here - it is '
            'not "no tyre programmed", it is "these bytes were never read '
            'back"' if hole else
            ' - that is the erased-flash pattern, not a circumference'))
    elif not SANE_MM[0] <= value <= SANE_MM[1]:
        note = (f'{value} mm is outside {SANE_MM[0]:.0f}-{SANE_MM[1]:.0f} mm, '
                'so either this is not the right calibration or the constant '
                'is not what the XDF thinks it is')
    return value, note


def write_circumference(buf, const, mm):
    """Write mm into the Radumfang constant. -> stored value."""
    if not SANE_MM[0] <= mm <= SANE_MM[1]:
        sys.exit(f'refusing to write {mm:.0f} mm: outside {SANE_MM[0]:.0f}-'
                 f'{SANE_MM[1]:.0f} mm. Check the tyre size or use --mm with '
                 'a rolling circumference, not a diameter.')
    return write_elem(buf, const.embedded.address, const.embedded, mm)


def rolling_diameter(mm):
    """The rolling diameter the formula implies for a circumference."""
    return mm / 0.97 / math.pi


# ----------------------------------------------------------- the ratio list

def find_ratio_list(buf, lo_x100=100, hi_x100=800, min_n=8, max_n=64,
                    min_distinct=10):
    """Find the TCU's fixed final-drive list in a calibration image.

    Searched for by structure, not at a remembered address: a u32 big-endian
    count N, then N u16 big-endian values in hundredths, ascending, all
    inside a plausible ratio range, with enough distinct entries that a run
    of counters or flags cannot match. Returns a list of
    (address_of_first_entry, count, values_as_ratios).
    """
    out = []
    for a in range(CAL_START, CAL_END - 8, 2):
        n = struct.unpack_from('>I', buf, a)[0]
        if not min_n <= n <= max_n or a + 4 + 2 * n > CAL_END:
            continue
        vals = struct.unpack_from('>%dH' % n, buf, a + 4)
        if not all(lo_x100 <= v <= hi_x100 for v in vals):
            continue
        if any(vals[i] > vals[i + 1] for i in range(n - 1)):
            continue
        if len(set(vals)) < min_distinct:
            continue
        out.append((a + 4, n, [v / 100.0 for v in vals]))
    return out


def distinct_ratios(values):
    """The list without the repeated padding slots, order kept."""
    seen, out = set(), []
    for v in values:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def describe_ratio_list(buf):
    """-> (ratios, lines, addr). Falls back to the documented list, loudly."""
    hits = find_ratio_list(buf)
    lines = []
    if not hits:
        lines.append('final-drive list: NOT FOUND in this image. No block in '
                     f'0x{CAL_START:X}-0x{CAL_END:X} has the shape of a '
                     'count-prefixed ascending ratio table, so the list below '
                     'is the one documented in the XDF, not one read back '
                     'from your bin - treat every snap decision as unchecked.')
        lines.append('  documented: '
                     + ' '.join(f'{r:.2f}' for r in DOCUMENTED_RATIOS))
        return list(DOCUMENTED_RATIOS), lines, None
    if len(hits) > 1:
        lines.append(f'{len(hits)} candidate ratio blocks found - using the '
                     'first; the others are listed below for inspection.')
    addr, n, values = hits[0]
    ratios = distinct_ratios(values)
    pad = len(values) - len(ratios)
    lines.append(f'final-drive list found at 0x{addr:X}: u32 count {n} at '
                 f'0x{addr - 4:X}, then {n} u16 big-endian hundredths'
                 + (f' ({len(ratios)} distinct, top entry repeated over the '
                    f'last {pad} slots)' if pad else ''))
    lines.append('  ' + ' '.join(f'{r:.2f}' for r in ratios))
    if tuple(ratios) == DOCUMENTED_RATIOS:
        lines.append('  matches the list the XDF documents, entry for entry')
    else:
        lines.append('  WARNING: differs from the list the XDF documents '
                     f'({" ".join(f"{r:.2f}" for r in DOCUMENTED_RATIOS)}) - '
                     'the image wins, but something is off')
    for a2, n2, v2 in hits[1:]:
        lines.append(f'  also at 0x{a2:X}: count {n2}, '
                     + ' '.join(f'{r:.2f}' for r in distinct_ratios(v2)))
    return ratios, lines, addr


def nearest_entry(ratio, ratios):
    """-> (entry, percent the ratio sits away from that entry)."""
    entry = min(ratios, key=lambda x: abs(x - ratio))
    return entry, (ratio - entry) / entry * 100


def diff_report(ratio, ratios, circ, learned=None):
    """-> (lines, suggested_circumference_or_None)."""
    entry, dev = nearest_entry(ratio, ratios)
    lines = [f'real final drive {ratio:.3f}: nearest list entry {entry:.2f}, '
             f'{dev:+.2f}% away']
    if WINDOW_LO <= dev <= WINDOW_HI:
        lines.append(f'  inside the documented {WINDOW_LO:+g}%/{WINDOW_HI:+g}% '
                     'acceptance window')
    else:
        lines.append(f'  OUTSIDE the documented {WINDOW_LO:+g}%/'
                     f'{WINDOW_HI:+g}% window: the TCU has no entry close '
                     'enough to your axle, so whatever it learns will be off '
                     'by this much and every shift point moves with it')
    if learned is None:
        return lines, None
    if abs(learned - ratio) / ratio <= 0.005:
        lines.append(f'learned {learned:.2f} already agrees with the real '
                     f'{ratio:.3f} (within 0.5%) - nothing to trim')
        return lines, None
    suggested = circ * ratio / learned
    lines.append(
        f'learned {learned:.2f} != real {ratio:.3f}: the TCU is reading the '
        f'axle {(learned - ratio) / ratio * 100:+.2f}% off, and the learned '
        'value tracks the programmed circumference directly, so scale it by '
        'the same factor')
    lines.append(f'  set circumference to {suggested:.0f} mm '
                 f'(= {circ:.0f} x {ratio:.3f}/{learned:.2f})')
    lines.append(f'  it should then learn {ratio:.3f} and snap to '
                 f'{entry:.2f} ({dev:+.2f}%)')
    lines.append('  after flashing: Tool32 steuern_lernfkt_ruecksetzen 0, '
                 'drive above ~24 km/h, then read status_lernfkt and repeat '
                 'this step if it is still off')
    return lines, suggested


# -------------------------------------------------------------------- CLI

def open_checked(path, any_calibration):
    """Load a bin and refuse unless it is the calibration this XDF describes."""
    buf = load_bin(path)
    ok, msg = check_calibration(buf, os.path.basename(path))
    if ok:
        print(msg)
    elif any_calibration:
        print('WARNING: ' + msg, file=sys.stderr)
        print('continuing anyway because --any-calibration was given',
              file=sys.stderr)
    else:
        sys.exit(msg + '\n\nRefusing to read or edit. Pass --any-calibration '
                 'only if you know why the identity differs.')
    return buf


def save(buf, args):
    with open(args.out, 'wb') as f:
        f.write(buf)
    print(f'\nwrote {args.out} (checksum NOT corrected - sign before flashing)')
    print(f'gate it: xdf_verify.py {args.xdf} {args.bin} {args.out}')


def cmd_wheel(args, xdf, buf):
    const = wheel_constant(xdf)
    emb = const.embedded
    old, note = read_circumference(buf, const)
    print(f'{const.title} @0x{emb.address:X} ({emb.type_name()}'
          f'{" big-endian" if not emb.little_endian else " little-endian"}): '
          f'{old} mm')
    if note:
        print(f'  NOTE: {note}')
    else:
        print(f'  implies a {rolling_diameter(old):.0f} mm rolling diameter')

    if args.tire:
        width, profile, rim = tire_size(args.tire)
        mm = tire_circumference(args.tire)
        source = (f'tyre {args.tire}: pi x ({rim:g} x 25.4 + 2 x {width:g} x '
                  f'{profile:g}/100) x 0.97')
    elif args.mm is not None:
        mm, source = float(args.mm), 'given directly'
    else:
        return                                   # read-only, nothing to write

    new = round(mm)
    print(f'\nwheel circumference: {old} -> {new} mm  ({source} = {mm:.1f} mm)')
    if not TYPICAL_MM[0] <= mm <= TYPICAL_MM[1]:
        print(f'  WARNING: {new} mm is outside the usual '
              f'{TYPICAL_MM[0]:.0f}-{TYPICAL_MM[1]:.0f} mm band - check the '
              'tyre size')
    if new == old:
        print('  (already programmed - nothing would change)')
    if args.preview:
        print('\npreview only, no file written')
        return
    out = bytearray(buf)
    write_circumference(out, const, mm)
    print('  relearn afterwards: Tool32 steuern_lernfkt_ruecksetzen 0, drive '
          'above ~24 km/h, then check status_lernfkt against your real axle')
    save(out, args)


def cmd_diff(args, xdf, buf):
    const = wheel_constant(xdf)
    circ, note = read_circumference(buf, const)
    print(f'programmed circumference: {circ} mm @0x{const.embedded.address:X}')
    if note:
        print(f'  NOTE: {note}')
    ratios, lines, addr = describe_ratio_list(buf)
    for line in lines:
        print(line)
    if args.ratio is None:
        if args.fix:
            sys.exit('--fix needs --ratio and --learned')
        return
    print()
    report, suggested = diff_report(args.ratio, ratios, circ, args.learned)
    for line in report:
        print(line)
    if not args.fix:
        return
    if suggested is None:
        sys.exit('\n--fix needs --learned with a value that disagrees with '
                 '--ratio; there is nothing to trim')
    if args.preview:
        print('\npreview only, no file written')
        return
    out = bytearray(buf)
    stored = write_circumference(out, const, suggested)
    print(f'\ncircumference {circ} -> {stored} mm')
    save(out, args)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__[__doc__.index('After flashing'):])
    sub = ap.add_subparsers(dest='cmd', required=True)

    def common(p):
        p.add_argument('bin', help='calibration read (the 2 MB image)')
        p.add_argument('-o', '--out', help='output bin (omit with --preview)')
        p.add_argument('--xdf', default=XDF_DEFAULT)
        p.add_argument('--preview', action='store_true',
                       help='report what would change without writing a bin')
        p.add_argument('--any-calibration', action='store_true',
                       help='run even if the image is a different calibration '
                            'from the one this XDF describes (the addresses '
                            'then mean something else - almost always wrong)')

    p = sub.add_parser('wheel', help='read or set the wheel circumference')
    common(p)
    p.add_argument('--tire', '--tyre', dest='tire',
                   help='tyre size, e.g. 245/40R18 (overrides --mm)')
    p.add_argument('--mm', type=float,
                   help='dynamic rolling circumference in mm, straight from '
                        "the tyre maker's Abrollumfang if you have it")

    p = sub.add_parser('diff', help='check a final drive against the TCU list')
    common(p)
    p.add_argument('--ratio', type=float,
                   help='the real final-drive ratio of the axle in the car')
    p.add_argument('--learned', type=float,
                   help='the ratio the TCU actually learned (Tool32 '
                        'status_lernfkt), if it disagrees with --ratio')
    p.add_argument('--fix', action='store_true',
                   help='write the trimmed circumference (needs --learned '
                        'and -o)')

    args = ap.parse_args()
    writes = (args.cmd == 'wheel' and (args.tire or args.mm is not None)) \
        or (args.cmd == 'diff' and args.fix)
    if writes and not args.preview and not args.out:
        ap.error('give -o OUT, or use --preview')
    if args.cmd == 'wheel' and args.tire and args.mm is not None:
        print('note: --tire given, ignoring --mm', file=sys.stderr)

    xdf = XDF(args.xdf)
    buf = open_checked(args.bin, args.any_calibration)
    (cmd_wheel if args.cmd == 'wheel' else cmd_diff)(args, xdf, buf)


if __name__ == '__main__':
    main()
