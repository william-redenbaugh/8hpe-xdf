#!/usr/bin/env python3
"""Export the full XDF inventory to JSON or CSV (structure + metadata only;
pass a bin with --bin to also include decoded values for every item).

Examples:
  xdf_export.py 8hpe84_cali_v1.xdf -o inventory.json
  xdf_export.py 8hpe84_cali_v1.xdf -o inventory.csv --csv
  xdf_export.py 8hpe84_cali_v1.xdf --bin my_read.bin -o full_dump.json
"""
import argparse
import csv
import json
import sys

from xdflib import XDF, load_bin, decode_table, decode_constant


def item_record(i, buf=None):
    rec = {'uid': i.uid, 'kind': i.kind, 'title': i.title,
           'categories': i.categories, 'description': i.description}
    if i.kind == 'table':
        rows, cols = i.shape()
        emb = i.z.embedded if i.z else None
        rec.update(rows=rows, cols=cols,
                   address=f'0x{emb.address:X}' if emb and emb.address is not None else None,
                   type=emb.type_name() if emb else None,
                   x_units=i.axes.get('x').units if 'x' in i.axes else None,
                   y_units=i.axes.get('y').units if 'y' in i.axes else None,
                   z_units=i.z.units if i.z else None)
        if buf is not None:
            try:
                rec['values'] = decode_table(buf, i)['z']
            except (ValueError, IndexError) as e:
                rec['values_error'] = str(e)
    elif i.kind == 'constant':
        rec.update(address=(f'0x{i.embedded.address:X}'
                            if i.embedded.address is not None else None),
                   type=i.embedded.type_name(), units=i.units)
        if buf is not None:
            rec['value'] = decode_constant(buf, i)
    else:
        rec['entries'] = [{'name': e.name, 'address': f'0x{e.address:X}',
                           'size': e.datasize} for e in i.entries]
    return rec


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('xdf')
    ap.add_argument('-o', '--out', required=True)
    ap.add_argument('--csv', action='store_true', help='write CSV instead of JSON')
    ap.add_argument('--bin', help='calibration image: include decoded values (JSON only)')
    args = ap.parse_args()

    xdf = XDF(args.xdf)
    buf = load_bin(args.bin, expect_size=0x200000) if args.bin else None

    if args.csv:
        with open(args.out, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['uid', 'kind', 'address', 'type', 'rows', 'cols',
                        'categories', 'title'])
            for i in xdf.items:
                rec = item_record(i)
                w.writerow([rec['uid'], rec['kind'], rec.get('address', ''),
                            rec.get('type', ''), rec.get('rows', ''),
                            rec.get('cols', ''), '; '.join(rec['categories']),
                            rec['title']])
    else:
        data = {'title': xdf.title, 'description': xdf.description,
                'categories': [xdf.categories[k] for k in sorted(xdf.categories)],
                'items': [item_record(i, buf) for i in xdf.items]}
        with open(args.out, 'w') as f:
            json.dump(data, f, indent=1)
    print(f'wrote {args.out} ({len(xdf.items)} items)', file=sys.stderr)


if __name__ == '__main__':
    main()
