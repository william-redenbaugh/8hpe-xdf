#!/usr/bin/env python3
"""List and search items defined in a TunerPro XDF.

Examples:
  xdf_ls.py 8hpe84_cali_v1.xdf --categories
  xdf_ls.py 8hpe84_cali_v1.xdf -c "Torque converter: slip"
  xdf_ls.py 8hpe84_cali_v1.xdf -s tcc_slip
  xdf_ls.py 8hpe84_cali_v1.xdf --addr 0x1D0AB6 --slack 64
  xdf_ls.py 8hpe84_cali_v1.xdf -s radumfang --long
"""
import argparse
import sys

from xdflib import XDF


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('xdf')
    ap.add_argument('-s', '--search', help='substring match on title/uid')
    ap.add_argument('-c', '--category', help='substring match on category name')
    ap.add_argument('-k', '--kind', choices=['table', 'constant', 'patch'])
    ap.add_argument('--addr', help='find items whose data starts at this address (hex ok)')
    ap.add_argument('--slack', type=lambda s: int(s, 0), default=0,
                    help='address tolerance in bytes for --addr')
    ap.add_argument('--categories', action='store_true', help='list categories and exit')
    ap.add_argument('--long', action='store_true', help='print full descriptions')
    args = ap.parse_args()

    xdf = XDF(args.xdf)

    if args.categories:
        counts = {}
        for i in xdf.items:
            for c in i.categories:
                counts[c] = counts.get(c, 0) + 1
        for idx in sorted(xdf.categories):
            name = xdf.categories[idx]
            print(f'{counts.get(name, 0):5d}  {name}')
        return

    items = xdf.items
    if args.addr:
        items = xdf.at_address(int(args.addr, 0), args.slack)
    if args.kind:
        items = [i for i in items if i.kind == args.kind]
    if args.category:
        cl = args.category.lower()
        items = [i for i in items if any(cl in c.lower() for c in i.categories)]
    if args.search:
        sl = args.search.lower()
        items = [i for i in items
                 if sl in (i.title or '').lower() or sl == (i.uid or '').lower()]

    for i in items:
        if i.kind == 'table':
            rows, cols = i.shape()
            emb = i.z.embedded if i.z else None
            addr = f'0x{emb.address:X}' if emb and emb.address is not None else '-'
            print(f'{i.uid:>8}  table     {addr:>10}  {rows}x{cols} '
                  f'{emb.type_name() if emb else "?":>4}  {i.title}')
        elif i.kind == 'constant':
            addr = (f'0x{i.embedded.address:X}'
                    if i.embedded.address is not None else '-')
            print(f'{i.uid:>8}  constant  {addr:>10}  1x1 '
                  f'{i.embedded.type_name():>4}  {i.title}')
        else:
            print(f'{i.uid:>8}  patch     {"-":>10}  {len(i.entries)} entries  {i.title}')
        if args.long and i.description:
            for line in i.description.splitlines():
                print(f'           | {line}')
            print()
    print(f'-- {len(items)} item(s)', file=sys.stderr)


if __name__ == '__main__':
    main()
