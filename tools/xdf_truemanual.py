#!/usr/bin/env python3
"""True manual: stop the TCU upshifting for you at redline in manual mode.

In M, the stock box still upshifts itself when the engine reaches its guard
speed. This toggle applies the XDF's own "[PATCH] True manual" - seven fixed
byte writes - so that guard never fires and the gear you selected is the gear
you keep. The DME rev limiter still protects the engine; nothing here touches
engine control.

The bytes are not invented by this tool. They are read out of the XDF at run
time (XDFPATCH "[PATCH] True manual"), so the patch, the tool and TunerPro
all write exactly the same thing, and --status reports what each entry
currently holds in your bin.

What the seven entries do, from the XDF's own description:

  overspeed_limit_1/_2   0x1CECA4/0x1CECA6 -> 0xFFFF (stock 7100/6825 rpm).
                         Kills guard test 1 in FUN_0012c9b8 - the forced
                         upshift itself.
  overspeed_margin_a/_b  0x1D3A80/0x1D3A81 -> 0xFF (stock 105). df32 seeds,
                         raising the test-2 margin.
  revmatch_latch_arm     0x1D28EC -> 0xFFFF (stock 6500 rpm).
  df31_gate_off          0x1D34B1 -> 0x00 (stock 0x02). The df31 gate in
                         FUN_0012c660. This one hinges on a runtime value
                         (def4) the static analysis could not pin down, and
                         the XDF marks it SUPERVISED TEST ONLY; the
                         deterministic fix is a program patch at
                         0x12CA44/56, outside the calibration area.
  strat_state_attr_3_01  0x1C927C, 100 bytes -> 0x01. The "K0 lever":
                         attr_3[100]=01 makes the test-2 threshold 2.55x, so
                         the ~7200 rpm forced upshift cannot fire.

Read this before flashing it:

  * Apply order is part of the patch's own documentation: load and apply any
    stage-3 map edits FIRST, then this as a pure overwrite, then recompute
    the checksum. 0x1CECA4 is also the stage-3 item
    escalation_test1_threshold, so a stage-3 edit applied afterwards would
    undo half of this.
  * The patch has no basedata, so there is nothing to restore from. --off
    puts your own stock bin's bytes back over the same seven spans, which is
    why it needs --stock.
  * The XDF description also records an R4 companion edit (the cap at
    0x1CC03C, 7200 -> 10000) that is NOT one of the seven entries. This tool
    writes only what the patch contains.
  * Three of the seven spans (0x1CECA6, 0x1D3A80/81, 0x1D28EC, 0x1D34B1) are
    not inside any XDF table or constant, so the default xdf_verify run will
    call them unexplained. Gate this with --allow-patch, which explains a
    changed byte only when it is inside an XDFPATCH entry AND the bytes
    written are byte-for-byte that entry's patch data.

Checksums are not corrected - sign before flashing:

    xdf_verify.py 8hpe70_cali_v3.xdf stock.bin out.bin --allow-patch

Examples:
    xdf_truemanual.py stock.bin --status
    xdf_truemanual.py stock.bin --preview
    xdf_truemanual.py stock.bin -o out.bin
    xdf_truemanual.py out.bin --off --stock stock.bin -o back.bin
"""
import argparse
import os
import sys

from xdflib import XDF, load_bin, check_calibration

XDF_DEFAULT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           '..', '8hpe70_cali_v3.xdf')

PATCH_TITLE = 'true manual'


def true_manual_patch(xdf):
    """The [PATCH] True manual object, found through the XDF by title."""
    hits = [p for p in xdf.patches if PATCH_TITLE in (p.title or '').lower()]
    if len(hits) != 1:
        sys.exit(f'{len(hits)} patches in {xdf.path} are titled like '
                 '"[PATCH] True manual" (expected exactly one) - is this the '
                 'E70 XDF?')
    patch = hits[0]
    for e in patch.entries:
        if e.datasize and e.datasize != len(e.patchdata):
            sys.exit(f'{e.name}: XDF declares {e.datasize} bytes but carries '
                     f'{len(e.patchdata)} - refusing to guess which is right')
    return patch


def entry_state(buf, entry):
    """'on', 'off' or 'part' for one patch entry in this image."""
    n = len(entry.patchdata)
    cur = bytes(buf[entry.address:entry.address + n])
    if cur == entry.patchdata:
        return 'on'
    same = sum(a == b for a, b in zip(cur, entry.patchdata))
    return 'part' if same else 'off'


def status(buf, patch):
    """-> (overall, rows). rows are (entry, state, current_bytes)."""
    rows = [(e, entry_state(buf, e),
             bytes(buf[e.address:e.address + len(e.patchdata)]))
            for e in patch.entries]
    states = {s for _e, s, _c in rows}
    overall = states.pop() if len(states) == 1 else 'part'
    return overall, rows


def apply_patch(buf, patch):
    """Write every entry's patch data. -> number of bytes actually changed."""
    changed = 0
    for e in patch.entries:
        n = len(e.patchdata)
        for k in range(n):
            if buf[e.address + k] != e.patchdata[k]:
                buf[e.address + k] = e.patchdata[k]
                changed += 1
    return changed


def revert_patch(buf, patch, stock):
    """Put the stock image's bytes back over every entry span."""
    changed = 0
    for e in patch.entries:
        n = len(e.patchdata)
        for k in range(n):
            if buf[e.address + k] != stock[e.address + k]:
                buf[e.address + k] = stock[e.address + k]
                changed += 1
    return changed


def print_status(rows, overall):
    print(f'[PATCH] True manual: {overall.upper()}'
          + ('  (some entries written, some not - this bin is in a state no '
             'clean apply produces)' if overall == 'part' else ''))
    for e, state, cur in rows:
        print(f'  {state:4s} {e.name:22s} @0x{e.address:X} '
              f'{len(e.patchdata):3d} B  now={cur[:8].hex()}'
              + ('...' if len(cur) > 8 else '')
              + f'  patch={e.patchdata[:8].hex()}'
              + ('...' if len(e.patchdata) > 8 else ''))


def open_checked(path, any_calibration):
    buf = load_bin(path)
    ok, msg = check_calibration(buf, os.path.basename(path))
    if ok:
        print(msg)
    elif any_calibration:
        print('WARNING: ' + msg, file=sys.stderr)
        print('continuing anyway because --any-calibration was given',
              file=sys.stderr)
    else:
        sys.exit(msg + '\n\nRefusing to edit. Pass --any-calibration only if '
                 'you know why the identity differs.')
    return buf


def main():
    ap = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__[__doc__.index('Read this before flashing it:'):])
    ap.add_argument('bin', help='calibration read (the 2 MB image)')
    ap.add_argument('-o', '--out', help='output bin (omit with --preview)')
    ap.add_argument('--xdf', default=XDF_DEFAULT)
    ap.add_argument('--status', action='store_true',
                    help='report the state of each entry and stop')
    ap.add_argument('--off', action='store_true',
                    help='put --stock\'s bytes back over the patch spans '
                         '(the XDF carries no basedata to restore from)')
    ap.add_argument('--stock', help='the stock read --off restores from')
    ap.add_argument('--preview', action='store_true',
                    help='report what would change without writing a bin')
    ap.add_argument('--any-calibration', action='store_true',
                    help='edit even if the image is a different calibration '
                         'from the one this XDF describes (the addresses then '
                         'mean something else - almost always wrong)')
    args = ap.parse_args()

    if args.off and not args.stock:
        ap.error('--off needs --stock STOCK.BIN to restore from')
    if not args.status and not args.preview and not args.out:
        ap.error('give -o OUT, or use --preview or --status')

    xdf = XDF(args.xdf)
    patch = true_manual_patch(xdf)
    buf = open_checked(args.bin, args.any_calibration)
    overall, rows = status(buf, patch)
    print_status(rows, overall)
    if args.status:
        return

    work = bytearray(buf)
    if args.off:
        stock = load_bin(args.stock)
        if len(stock) != len(buf):
            sys.exit(f'{args.stock} is {len(stock)} bytes, {args.bin} is '
                     f'{len(buf)} - these are not the same image')
        ok, msg = check_calibration(stock, os.path.basename(args.stock))
        if not ok and not args.any_calibration:
            sys.exit(msg + '\n\nRefusing to restore from it.')
        n = revert_patch(work, patch, stock)
        action = f'reverted to the bytes in {args.stock}'
    else:
        n = apply_patch(work, patch)
        action = 'applied'
    print(f'\n{action}: {n} byte(s) changed across {len(patch.entries)} entries')
    if n == 0:
        print('  (nothing to do - the bin already holds these bytes)')
    if not args.off:
        print('  reminder: apply stage-3 map edits BEFORE this patch, not '
              'after - 0x1CECA4 belongs to both')
        print('  reminder: df31_gate_off (0x1D34B1) is marked supervised test '
              'only in the XDF; try the patch on a lift or a closed road '
              'before trusting it on the move')

    if args.preview:
        print('\npreview only, no file written')
        return
    with open(args.out, 'wb') as f:
        f.write(work)
    print(f'\nwrote {args.out} (checksum NOT corrected - sign before flashing)')
    print(f'gate it: xdf_verify.py {args.xdf} {args.bin} {args.out} '
          '--allow-patch')


if __name__ == '__main__':
    main()
