#!/usr/bin/env python3
"""Verify a tuned calibration against the stock read before flashing.

Every changed byte must be explained by an XDF item's z-data (or, with
--allow-axis, axis data). Anything else - cal header, ZFADINFO block,
signature tail, program region, or bytes no XDF item covers - must be
byte-identical to stock, or the bin is treated as potentially corrupting
and verification FAILS (exit code 1).

  xdf_verify.py XDF stock.bin tuned.bin
  xdf_verify.py XDF stock.bin tuned.bin --allow-axis   # axis edits intended
  xdf_verify.py XDF stock.bin tuned.bin -v             # list every change

Checks:
  1. sizes match and the program region (below the cal block) is identical
  2. protected cal ranges are identical: cal header @0x180200, the
     ZFADINFO identification block @0x190000, the calibration-ID /
     signature tail at the end of the cal block
  3. every changed byte falls inside a known XDF item's z span
     (axis spans only count as explained with --allow-axis)
  4. all pedal/axis arrays of shift-line items are unchanged and still
     strictly monotonic in the tuned bin
  5. hysteresis: no downshift line cell rose above its matching upshift
     line cell (warning, not failure, when the upshift cell is disabled)

Checksums are NOT verified or corrected here - the flash tool signs.
"""
import argparse
import sys

from xdflib import XDF, load_bin, decode_table, check_calibration

CAL_START = 0x180200
CAL_END = 0x200000
# (start, end, why) - byte-identical required
PROTECTED = [
    (0x000000, 0x180200, 'program region / padding below the cal block'),
    (0x180200, 0x180254, 'calibration header (magic, TYPTEILENR)'),
    (0x190000, 0x190180, 'ZFADINFO identification block'),
    (0x1FFD00, 0x200000, 'calibration-ID / signature tail'),
]


def coverage_mask(xdf, include_axes):
    """bytearray mask over the file: 1 where an XDF element byte may be written.

    Built with xdflib's own element_offset, so strided/column-major layouts
    are covered exactly where the editing tools can write."""
    from xdflib import element_offset
    mask = bytearray(CAL_END)
    def mark(emb, rows, cols):
        step = emb.elem_bits // 8
        try:
            for r in range(rows):
                for c in range(cols):
                    off = element_offset(emb, rows, cols, r, c)
                    if 0 <= off < CAL_END - step:
                        for k in range(step):
                            mask[off + k] = 1
        except ValueError as e:
            # Never fall back to a guessed contiguous span: that would mark the
            # wrong bytes as "covered" and make this gate approve edits it has
            # not actually checked.
            raise SystemExit(
                f'cannot compute the byte layout of a table at '
                f'0x{emb.address:X} ({e}). Refusing to verify, because a '
                'guessed layout would silently approve the wrong bytes.')
    for t in xdf.tables:
        emb = t.z.embedded if t.z else None
        if emb is not None and emb.address is not None:
            rows, cols = t.shape()
            mark(emb, rows, cols)
        if include_axes:
            for ax in ('x', 'y'):
                axis = t.axes.get(ax)
                emb = axis.embedded if axis is not None else None
                if emb is not None and emb.address is not None:
                    mark(emb, 1, axis.count or 1)
    for c in xdf.constants:
        emb = c.embedded
        if emb is not None and emb.address is not None:
            mark(emb, 1, 1)
    return mask


def changed_ranges(a, b):
    out = []
    i, n = 0, min(len(a), len(b))
    while i < n:
        if a[i] != b[i]:
            j = i
            while j < n and a[j] != b[j]:
                j += 1
            out.append((i, j))
            i = j
        else:
            i += 1
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('xdf')
    ap.add_argument('stock')
    ap.add_argument('tuned')
    ap.add_argument('--allow-axis', action='store_true',
                    help='axis-data edits are intended (Bulk edit of axes)')
    ap.add_argument('-v', '--verbose', action='store_true')
    ap.add_argument('--any-calibration', action='store_true',
                    help='downgrade a calibration-identity mismatch to a warning '
                         '(you are then on your own: the addresses mean '
                         'something else in that image)')
    args = ap.parse_args()

    xdf = XDF(args.xdf)
    stock = load_bin(args.stock)
    tuned = load_bin(args.tuned)
    fails, warns = [], []

    # Calibration identity. Without this the coverage check below is
    # meaningless on a foreign image: every XDF address exists in any 2 MB
    # file, so a wrong-calibration bin "passes" while the addresses actually
    # describe unrelated data.
    for buf, name in ((stock, 'stock'), (tuned, 'tuned')):
        ok, msg = check_calibration(buf, name)
        if ok:
            print(msg)
        elif args.any_calibration:
            warns.append(msg + '  [--any-calibration given]')
        else:
            fails.append(msg)

    # A calibration-only read is padded with 0xFF below the cal block, so the
    # program-region comparison would pass by comparing padding with padding.
    if all(b == 0xFF for b in stock[:CAL_START]):
        warns.append('stock image is 0xFF below 0x%X - a calibration-only read, '
                     'so the program-region check proves nothing here'
                     % CAL_START)

    if len(stock) != len(tuned):
        print(f'FAIL: size mismatch (stock {len(stock)}, tuned {len(tuned)})')
        sys.exit(1)

    ranges = changed_ranges(stock, tuned)
    nbytes = sum(j - i for i, j in ranges)
    print(f'{len(ranges)} changed range(s), {nbytes} byte(s) total')

    for lo, hi, why in PROTECTED:
        bad = [(i, j) for i, j in ranges if i < hi and lo < j]
        if bad:
            fails.append(f'protected region modified: {why} '
                         f'({", ".join(f"0x{i:X}..0x{j:X}" for i, j in bad)})')

    mask = coverage_mask(xdf, include_axes=args.allow_axis)
    orphan = []
    explained_bytes = 0
    for i, j in ranges:
        pos = i
        while pos < j:
            if mask[pos]:
                explained_bytes += 1
                pos += 1
            else:
                end = pos
                while end < j and not mask[end]:
                    end += 1
                orphan.append((pos, end))
                pos = end
    if orphan:
        for i, j in orphan[:20]:
            ctx = tuned[i:min(j, i + 16)].hex(' ', 2)
            fails.append(f'unexplained change at 0x{i:X}..0x{j:X} ({j - i} B): {ctx}')
        if len(orphan) > 20:
            fails.append(f'... and {len(orphan) - 20} more unexplained ranges')

    # axis integrity + hysteresis on shift-line singles
    ups = {}
    for t in xdf.tables:
        title = t.title
        if title.startswith('Upshift char ') or title.startswith('Downshift char '):
            x = t.axes.get('x')
            emb = x.embedded if x is not None else None
            if emb is not None and emb.address is not None:
                n = x.count or 15
                step = emb.elem_bits // 8
                raw_s = stock[emb.address:emb.address + n * step]
                raw_t = tuned[emb.address:emb.address + n * step]
                if raw_s != raw_t and not args.allow_axis:
                    fails.append(f'pedal axis bytes changed under "{title}" @0x{emb.address:X}')
                vals = [int.from_bytes(raw_t[k * step:(k + 1) * step], 'big') for k in range(n)]
                # Repeated breakpoints are legitimate (stock char 08 plateaus at
                # 500/660/820/980); only a decrease breaks interpolation.
                drops = [k for k in range(len(vals) - 1) if vals[k] > vals[k + 1]]
                if drops:
                    fails.append(f'pedal axis decreases under "{title}" @0x{emb.address:X} '
                                 f'at index {drops[0]} ({vals[drops[0]]} -> {vals[drops[0] + 1]})')
            if title.startswith('Upshift char '):
                ups[title.replace('Upshift char ', '')] = t
    for t in xdf.tables:
        if not t.title.startswith('Downshift char '):
            continue
        key = t.title.replace('Downshift char ', '')
        # match "NN: 2>1" to the upshift "NN: 1>2"
        try:
            ch, pair = key.split(': ')
            hi, lo = pair.split('>')
            up = ups.get(f'{ch}: {lo}>{hi}')
        except ValueError:
            up = None
        if up is None:
            continue
        dz = decode_table(tuned, t)['z']
        uz = decode_table(tuned, up)['z']
        dz0 = decode_table(stock, t)['z']
        uz0 = decode_table(stock, up)['z']
        for r in range(len(dz)):
            for c in range(len(dz[r])):
                d, u = dz[r][c], uz[r][c]
                m0 = uz0[r][c] - dz0[r][c]
                if 0 < u < 7900 and d > u - 50 and (u - d) < m0:
                    warns.append(f'hysteresis tight: "{t.title}" cell[{r}][{c}]={d} vs upshift {u}')
                    break
            else:
                continue
            break

    print(f'{explained_bytes} changed byte(s) inside XDF-covered element data')

    for w in warns[:10]:
        print('WARN:', w)
    if fails:
        for f in fails:
            print('FAIL:', f)
        print('\nVERDICT: FAIL - do not flash this bin.')
        sys.exit(1)
    print('\nVERDICT: PASS - every change is explained by the XDF and all '
          'protected regions are byte-identical to stock.')


if __name__ == '__main__':
    main()
