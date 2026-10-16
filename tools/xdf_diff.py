#!/usr/bin/env python3
"""Diff two calibration images through the XDF: report which defined items
changed and (for tables/constants) the per-cell differences.

Examples:
  xdf_diff.py 8hpe84_cali_v1.xdf stock.bin tuned.bin
  xdf_diff.py 8hpe84_cali_v1.xdf stock.bin tuned.bin --cells
  xdf_diff.py 8hpe84_cali_v1.xdf stock.bin tuned.bin --raw   # also bytes not covered by any item
"""
import argparse
import sys

from xdflib import XDF, load_bin, decode_table, decode_constant


def table_span(t):
    """(start, end) byte range of a table's z data, best effort (contiguous
    assumption for span purposes; strided tables report their full pitch)."""
    emb = t.z.embedded if t.z else None
    if not emb or emb.address is None:
        return None
    rows, cols = t.shape()
    elem = emb.elem_bits // 8
    if emb.minor_stride and emb.col_major:
        pitch = ((rows - 1) * emb.elem_bits + emb.minor_stride) // 8
        return emb.address, emb.address + (cols - 1) * pitch + rows * elem
    return emb.address, emb.address + rows * cols * elem


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('xdf')
    ap.add_argument('bin_a')
    ap.add_argument('bin_b')
    ap.add_argument('--cells', action='store_true',
                    help='print per-cell value changes, not just item names')
    ap.add_argument('--raw', action='store_true',
                    help='also report changed byte ranges not covered by any item')
    args = ap.parse_args()

    xdf = XDF(args.xdf)
    a = load_bin(args.bin_a, expect_size=0x200000)
    b = load_bin(args.bin_b, expect_size=0x200000)
    if len(a) != len(b):
        sys.exit('images differ in size; diff needs equal-size reads')

    changed = []
    covered = []
    for t in xdf.tables:
        span = table_span(t)
        if not span:
            continue
        covered.append(span)
        if a[span[0]:span[1]] != b[span[0]:span[1]]:
            changed.append(t)
    for c in xdf.constants:
        if c.embedded.address is None:
            continue
        size = c.embedded.elem_bits // 8
        s, e = c.embedded.address, c.embedded.address + size
        covered.append((s, e))
        if a[s:e] != b[s:e]:
            changed.append(c)

    seen_spans = set()
    for i in changed:
        if i.kind == 'table':
            emb = i.z.embedded
            addr = emb.address
        else:
            addr = i.embedded.address
        print(f'0x{addr:X}  {i.kind:9}  {i.title}')
        if args.cells:
            try:
                if i.kind == 'constant':
                    print(f'    {decode_constant(a, i)} -> {decode_constant(b, i)}')
                else:
                    da, db = decode_table(a, i), decode_table(b, i)
                    x, y = da['x'] or [], da['y'] or []
                    for r, (ra, rb) in enumerate(zip(da['z'], db['z'])):
                        for cix, (va, vb) in enumerate(zip(ra, rb)):
                            if va != vb:
                                xl = x[cix] if cix < len(x) else cix
                                yl = y[r] if r < len(y) else r
                                print(f'    [y={yl}, x={xl}]  {va} -> {vb}')
            except (ValueError, IndexError) as e:
                print(f'    (cannot decode: {e})')

    print(f'-- {len(changed)} changed item(s)', file=sys.stderr)

    if args.raw:
        covered.sort()
        merged = []
        for s, e in covered:
            if merged and s <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], e))
            else:
                merged.append((s, e))

        def is_covered(off):
            import bisect
            k = bisect.bisect_right(merged, (off, len(a) + 1)) - 1
            return k >= 0 and merged[k][0] <= off < merged[k][1]

        start = None
        uncovered = 0
        for off in range(len(a)):
            differs = a[off] != b[off] and not is_covered(off)
            if differs and start is None:
                start = off
            elif not differs and start is not None:
                print(f'0x{start:X}-0x{off - 1:X}  raw ({off - start} B, '
                      'not covered by any XDF item)')
                uncovered += 1
                start = None
        if start is not None:
            print(f'0x{start:X}-0x{len(a) - 1:X}  raw (not covered by any XDF item)')
            uncovered += 1
        print(f'-- {uncovered} uncovered changed range(s)', file=sys.stderr)


if __name__ == '__main__':
    main()
