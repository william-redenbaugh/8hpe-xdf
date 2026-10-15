#!/usr/bin/env python3
"""Clean-room checksum search / verify / sign for the 8HPe calibration image.

The calibration declares a CRC32 at 0x180244 (`cal_declared_crc32` in the
XDF; known tunes rewrite it). The exact algorithm and covered region are not
published anywhere, so this tool CONFIRMS them against a known-good bin
instead of guessing:

  search  - sweep common CRC32 variants and start offsets over YOUR stock
            read; for each byte position the running checksum is compared
            with the value stored in the bin. A hit = (algorithm, start, end)
            that reproduces the factory-stored value. Saved to
            checksum_profile.json next to this script.
  verify  - recompute with the saved profile and compare with the stored value.
  sign    - recompute and store it (writes a copy with -o, or in place with
            --in-place). The GUI's "Sign bin" button calls this.

This is an independent implementation built only from the calibration's own
data - no third-party flash tool was disassembled for it.

Usage:
  python3 xdf_checksum.py search stock_read.bin
  python3 xdf_checksum.py verify my_tuned.bin
  python3 xdf_checksum.py sign my_tuned.bin -o my_tuned_signed.bin
"""
import argparse
import json
import os
import struct
import sys
import zlib

LOC_DEFAULT = 0x180244
CAL_START = 0x180200
CAL_END = 0x200000
PROFILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'checksum_profile.json')


def _table(poly_reflected):
    tbl = []
    for i in range(256):
        c = i
        for _ in range(8):
            c = (c >> 1) ^ poly_reflected if c & 1 else c >> 1
        tbl.append(c)
    return tbl


def _table_msb(poly):
    tbl = []
    for i in range(256):
        c = i << 24
        for _ in range(8):
            c = ((c << 1) ^ poly if c & 0x80000000 else c << 1) & 0xFFFFFFFF
        tbl.append(c)
    return tbl


TBL_REFL = _table(0xEDB88320)   # standard CRC-32
TBL_C = _table(0x82F63B78)      # CRC-32C (Castagnoli)
TBL_MSB = _table_msb(0x04C11DB7)

# name -> (init, xorout, per-byte update using closure tables)
ALGOS = {
    'crc32':  ('refl', 0xFFFFFFFF, 0xFFFFFFFF),
    'crc32c': ('c',    0xFFFFFFFF, 0xFFFFFFFF),
    'crc32-mpeg2': ('msb', 0xFFFFFFFF, 0x0),
    'crc32-bzip2': ('msb', 0xFFFFFFFF, 0xFFFFFFFF),
    'crc32-posix': ('msb', 0x0, 0xFFFFFFFF),
    'crc32-jamcrc': ('refl', 0xFFFFFFFF, 0x0),
    'sum32': ('sum', 0x0, 0x0),
}


def _step(kind, crc, byte):
    if kind == 'refl':
        return (crc >> 8) ^ TBL_REFL[(crc ^ byte) & 0xFF]
    if kind == 'c':
        return (crc >> 8) ^ TBL_C[(crc ^ byte) & 0xFF]
    if kind == 'msb':
        return ((crc << 8) & 0xFFFFFFFF) ^ TBL_MSB[((crc >> 24) ^ byte) & 0xFF]
    return (crc + byte) & 0xFFFFFFFF   # sum32


def compute(buf, algo, start, end):
    kind, init, xorout = ALGOS[algo]
    if kind == 'refl' and (init, xorout) == (0xFFFFFFFF, 0xFFFFFFFF):
        return zlib.crc32(bytes(memoryview(buf)[start:end])) & 0xFFFFFFFF
    return _slow(buf, kind, init, xorout, start, end)


def _slow(buf, kind, init, xorout, start, end):
    crc = init
    step = _step
    for b in memoryview(buf)[start:end]:
        crc = step(kind, crc, b)
    return crc ^ xorout


def search(buf, loc, starts=None, quick=False):
    stored_be = struct.unpack_from('>I', buf, loc)[0]
    stored_le = struct.unpack_from('<I', buf, loc)[0]
    starts = starts or [CAL_START, loc + 4, 0x180250, 0x180300, 0x180400]
    hits = []
    algos = ['crc32', 'crc32c', 'crc32-jamcrc'] if quick else list(ALGOS)
    for algo in algos:
        kind, init, xorout = ALGOS[algo]
        for start in starts:
            crc = init
            mv = memoryview(buf)
            for pos in range(start, CAL_END):
                crc = _step(kind, crc, mv[pos])
                val = crc ^ xorout
                end = pos + 1
                if val == stored_be or val == stored_le:
                    endian = 'be' if val == stored_be else 'le'
                    print(f'HIT {algo} start=0x{start:X} end=0x{end:X} '
                          f'({endian}) value=0x{val:08X}', file=sys.stderr)
                    hits.append({'algo': algo, 'start': start, 'end': end,
                                 'loc': loc, 'endian': endian})
    return hits


def load_profile():
    try:
        with open(PROFILE_PATH) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def stored_value(buf, profile):
    fmt = '>I' if profile.get('endian', 'be') == 'be' else '<I'
    return struct.unpack_from(fmt, buf, profile['loc'])[0]


def sign(buf, profile):
    """Recompute and store into a bytearray. Returns (old, new)."""
    if not isinstance(buf, bytearray):
        raise ValueError('sign() needs a bytearray')
    old = stored_value(buf, profile)
    new = compute(buf, profile['algo'], profile['start'], profile['end'])
    fmt = '>I' if profile.get('endian', 'be') == 'be' else '<I'
    struct.pack_into(fmt, buf, profile['loc'], new)
    return old, new


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['search', 'verify', 'sign'])
    ap.add_argument('bin')
    ap.add_argument('-o', '--out')
    ap.add_argument('--in-place', action='store_true')
    ap.add_argument('--loc', type=lambda s: int(s, 0), default=LOC_DEFAULT)
    ap.add_argument('--quick', action='store_true',
                    help='search only the most common variants (faster)')
    args = ap.parse_args()

    buf = bytearray(open(args.bin, 'rb').read())
    if len(buf) < CAL_END:
        sys.exit(f'{args.bin} is {len(buf)} bytes; need the full 2 MB image')

    if args.cmd == 'search':
        hits = search(buf, args.loc, quick=args.quick)
        if not hits:
            sys.exit('no algorithm/region reproduced the stored value - the '
                     'checksum may cover non-contiguous segments or use a '
                     'different polynomial; flash with a tool that corrects '
                     'checksums itself (e.g. 8HPe Quickflash).')
        with open(PROFILE_PATH, 'w') as f:
            json.dump(hits[0], f, indent=1)
        print(f'profile saved to {PROFILE_PATH}: {hits[0]}')
        if len(hits) > 1:
            print(f'note: {len(hits)} candidate hits; verify against a SECOND '
                  'known-good bin before trusting (verify command).')
        return

    profile = load_profile()
    if profile is None:
        sys.exit(f'no profile at {PROFILE_PATH}; run search on a stock read first')

    if args.cmd == 'verify':
        want = compute(buf, profile['algo'], profile['start'], profile['end'])
        have = stored_value(buf, profile)
        print(f'computed 0x{want:08X}, stored 0x{have:08X} -> '
              + ('OK' if want == have else 'MISMATCH'))
        sys.exit(0 if want == have else 1)

    old, new = sign(buf, profile)
    out = args.bin if args.in_place else args.out
    if not out:
        sys.exit('sign needs -o OUT or --in-place')
    with open(out, 'wb') as f:
        f.write(buf)
    print(f'signed {out}: 0x{old:08X} -> 0x{new:08X} ({profile["algo"]} over '
          f'0x{profile["start"]:X}-0x{profile["end"]:X})')


if __name__ == '__main__':
    main()
