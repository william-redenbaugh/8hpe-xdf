#!/usr/bin/env python3
"""Decode and print one XDF item's values from a calibration image.

Examples:
  xdf_show.py 8hpe_cali_v3.xdf my_read.bin "Radumfang"
  xdf_show.py 8hpe_cali_v3.xdf my_read.bin "Upshift lines, char 00: 1>2..5>6"
  xdf_show.py 8hpe_cali_v3.xdf my_read.bin 0x616          # by uniqueid
  xdf_show.py 8hpe_cali_v3.xdf my_read.bin tcc_slip --all # every match
  xdf_show.py 8hpe_cali_v3.xdf my_read.bin tcc_slip_cond_map --csv
"""
import argparse
import sys

from xdflib import XDF, load_bin, decode_table, decode_constant


def fmt(v):
    if v is None:
        return '-'
    if isinstance(v, float):
        return f'{v:g}'
    return str(v)


def print_table(d, csv=False):
    sep = ',' if csv else '  '
    x = d['x'] or ['']
    y = d['y'] or ['']
    print(f'# {d["title"]}  ({d["rows"]}x{d["cols"]} {d["type"]})')
    units = [f'x: {d["x_units"]}' if d['x_units'] else None,
             f'y: {d["y_units"]}' if d['y_units'] else None,
             f'z: {d["z_units"]}' if d['z_units'] else None]
    units = [u for u in units if u]
    if units:
        print('# ' + ' | '.join(units))
    if d['z'] is None:
        print('# (no stored data: label/axis-only item)')
        return
    widths = None
    if not csv:
        cells = [[''] + [fmt(v) for v in x]]
        for r, row in enumerate(d['z']):
            cells.append([fmt(y[r] if r < len(y) else r)] + [fmt(v) for v in row])
        widths = [max(len(row[c]) for row in cells) for c in range(len(cells[0]))]
        for row in cells:
            print(sep.join(c.rjust(w) for c, w in zip(row, widths)))
    else:
        print(sep.join([''] + [fmt(v) for v in x]))
        for r, row in enumerate(d['z']):
            print(sep.join([fmt(y[r] if r < len(y) else r)] + [fmt(v) for v in row]))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('xdf')
    ap.add_argument('bin')
    ap.add_argument('item', help='title substring or uniqueid')
    ap.add_argument('--all', action='store_true',
                    help='print every match instead of requiring a unique one')
    ap.add_argument('--csv', action='store_true')
    ap.add_argument('--desc', action='store_true', help='also print the description')
    args = ap.parse_args()

    xdf = XDF(args.xdf)
    buf = load_bin(args.bin, expect_size=0x200000)

    matches = [i for i in xdf.find(args.item) if i.kind in ('table', 'constant')]
    if not matches:
        sys.exit(f'no table/constant matches {args.item!r}')
    exact = [i for i in matches if i.title.lower() == args.item.lower()
             or (i.uid or '').lower() == args.item.lower()]
    if exact:
        matches = exact
    if len(matches) > 1 and not args.all:
        print(f'{len(matches)} matches — pick one (or pass --all):', file=sys.stderr)
        for i in matches[:40]:
            print(f'  {i.uid:>8}  {i.title}', file=sys.stderr)
        sys.exit(2)

    for i in matches:
        if i.kind == 'constant':
            print(f'# {i.title}')
            print(decode_constant(buf, i))
        else:
            try:
                print_table(decode_table(buf, i), csv=args.csv)
            except (ValueError, IndexError) as e:
                print(f'# {i.title}: cannot decode ({e})', file=sys.stderr)
        if args.desc and i.description:
            for line in i.description.splitlines():
                print(f'# {line}')
        print()


if __name__ == '__main__':
    main()
