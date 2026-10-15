#!/usr/bin/env python3
"""Write the educated guesses for unlabelled items into the XDF itself, so
TunerPro (and this repo's GUI) shows them in each item's description.

Reads docs/data/unlabelled-guesses.csv (produced by the guessing pipeline,
see docs/parameters/12-unlabelled-guesses.md) and appends one clearly marked
sentence to the <description> of every unlabelled item, matched by data
address. Pure text edit: everything else in the file - attribute order,
CRLF line endings, formatting - is preserved. Idempotent: items already
carrying a 'SPECULATIVE GUESS' marker are skipped.

Usage:
  python3 annotate_xdf.py ../8hpe_cali_v3.xdf ../docs/data/unlabelled-guesses.csv

The file is modified IN PLACE (keep it under version control); pass
-o OUT.xdf to write a copy instead.
"""
import argparse
import csv
import re
import sys
from xml.sax.saxutils import escape

from xdflib import XDF

MARKER = 'SPECULATIVE GUESS'
OPEN_RX = re.compile(r'<(XDFTABLE|XDFCONSTANT) uniqueid="(0x[0-9A-Fa-f]+)"')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('xdf')
    ap.add_argument('csv')
    ap.add_argument('-o', '--out', help='write a copy instead of in place')
    args = ap.parse_args()

    # addr -> guess text, from the pipeline CSV
    guesses = {}
    with open(args.csv, newline='') as f:
        for row in csv.DictReader(f):
            bits = [row['guess']] if row['guess'] and row['guess'] != 'no signal' else []
            if row['cluster_interpretation']:
                bits.append(f"cluster: {row['cluster_interpretation']}")
            if bits:
                guesses[int(row['address'], 16)] = '; '.join(bits)

    # uid -> addr for every unlabelled item in the XDF
    xdf = XDF(args.xdf)
    targets = {}
    for i in xdf.tables + xdf.constants:
        if not any(c.startswith('Unlabelled:') for c in i.categories):
            continue
        if i.kind == 'table':
            emb = i.z.embedded if i.z else None
            addr = emb.address if emb else None
        else:
            addr = i.embedded.address
        if addr and addr in guesses:
            targets[i.uid.lower()] = guesses[addr]

    with open(args.xdf, newline='') as f:
        lines = f.readlines()

    current_uid = None
    in_desc = False
    annotated = skipped = 0
    for n, line in enumerate(lines):
        m = OPEN_RX.search(line)
        if m:
            current_uid = m.group(2).lower()
            in_desc = False
            continue
        if '</XDFTABLE>' in line or '</XDFCONSTANT>' in line:
            current_uid = None
            continue
        if current_uid not in targets:
            continue
        if '<description>' in line:
            in_desc = True
        if in_desc and '</description>' in line:
            in_desc = False
            note = escape(f' {MARKER} (auto-generated, weaker than LOW - '
                          f'do not tune from this): {targets[current_uid]}.')
            if MARKER in line:
                # replace the previous guess with the current one
                new_line = re.sub(f' {MARKER} \\(auto-generated[^<]*', note,
                                  line, count=1)
                if new_line == line:
                    skipped += 1
                else:
                    lines[n] = new_line
                    annotated += 1
            else:
                lines[n] = line.replace('</description>',
                                        note + '</description>', 1)
                annotated += 1
            del targets[current_uid]
            current_uid = None

    out = args.out or args.xdf
    with open(out, 'w', newline='') as f:
        f.writelines(lines)

    print(f'{annotated} descriptions annotated, {skipped} already annotated, '
          f'{len(targets)} targets not found -> {out}', file=sys.stderr)
    XDF(out)  # re-parse to prove the file is still valid XML
    print('re-parse OK', file=sys.stderr)


if __name__ == '__main__':
    main()
