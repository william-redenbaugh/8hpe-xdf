#!/usr/bin/env python3
"""List or apply the XDF's [PATCH] entries to a calibration image.

IMPORTANT (this XDF): apply the Stage 3 maps first, then the patches, in the
order the XDF lists them; the patches are pure overwrites. Checksums are NOT
corrected by this tool or the XDF - recompute the segment CRC before flashing
(8HPe Quickflash does it automatically).

Examples:
  xdf_patch.py 8hpe84_cali_v1.xdf --list
  xdf_patch.py 8hpe84_cali_v1.xdf my.bin --show "Start in 2nd"
  xdf_patch.py 8hpe84_cali_v1.xdf my.bin --apply "True manual" -o my_tm.bin
"""
import argparse
import sys

from xdflib import XDF, load_bin


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('xdf')
    ap.add_argument('bin', nargs='?')
    ap.add_argument('--list', action='store_true', help='list patches and exit')
    ap.add_argument('--show', metavar='PATCH',
                    help='show what a patch would change in BIN (no write)')
    ap.add_argument('--apply', metavar='PATCH', help='apply a patch')
    ap.add_argument('-o', '--out', help='output file for --apply')
    args = ap.parse_args()

    xdf = XDF(args.xdf)

    if args.list or not (args.show or args.apply):
        for p in xdf.patches:
            total = sum(e.datasize for e in p.entries)
            print(f'{p.uid:>8}  {len(p.entries):3d} entries  {total:5d} B  {p.title}')
            first = p.description.splitlines()[0] if p.description else ''
            print(f'           {first}')
        return

    name = args.show or args.apply
    matches = [p for p in xdf.patches if name.lower() in p.title.lower()]
    if len(matches) != 1:
        sys.exit(f'{len(matches)} patches match {name!r} - be more specific')
    patch = matches[0]

    if not args.bin:
        sys.exit('a bin is required for --show/--apply')
    buf = bytearray(load_bin(args.bin, expect_size=0x200000))

    already = 0
    for e in patch.entries:
        cur = bytes(buf[e.address:e.address + e.datasize])
        if len(cur) < e.datasize:
            sys.exit(f'{e.name}: 0x{e.address:X}+0x{e.datasize:X} is past end of bin')
        new = e.patchdata[:e.datasize]
        state = 'ALREADY APPLIED' if cur == new else 'will change'
        if cur == new:
            already += 1
        if args.show:
            print(f'{e.name:32} @0x{e.address:X} ({e.datasize} B)  {state}')
            if cur != new:
                print(f'    {cur.hex()} -> {new.hex()}')
        else:
            buf[e.address:e.address + e.datasize] = new

    if args.show:
        print(f'-- {already}/{len(patch.entries)} entries already applied',
              file=sys.stderr)
        return

    out = args.out
    if not out:
        sys.exit('--apply needs -o OUTPUT (refusing to overwrite the input)')
    with open(out, 'wb') as f:
        f.write(buf)
    print(f'applied "{patch.title}" ({len(patch.entries)} entries) -> {out}')
    print('REMINDER: recompute the segment CRC before flashing; this tool '
          'does not correct checksums.', file=sys.stderr)


if __name__ == '__main__':
    main()
