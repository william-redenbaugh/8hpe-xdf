#!/usr/bin/env python3
"""True manual: remove the TCU-side forced upshift at redline, from the XDF's own patch.

The XDF carries a TunerPro patch called "[PATCH] True manual" - 7 entries, 109
bytes. This tool reads that patch out of 8hpe70_cali_v3.xdf (title, addresses,
sizes and patch bytes all come from the XDF, nothing is hardcoded here) and
applies it to a calibration read, so the XDF stays the single source of truth.

What it is supposed to do: in manual mode the TCU, not just the DME, forces an
upshift as the engine approaches redline. The patch pushes the thresholds that
trigger that out of reach, so the gear is held and the DME rev limiter is what
protects the engine. The patch does NOT raise the DME limiter, does NOT change
the shift schedule, and does NOT touch the program region, so the deterministic
code fix the XDF mentions (0x12CA44/56, outside the calibration) is not part of
it. Nor does it include the "R4" cap edit at 0x1CC03C that the patch
description talks about - there is no patch entry for that address.

Read this before trusting it. Of the 7 entries only two write bytes that any
XDF item describes (escalation_test1_threshold and the table
strat_state_attr_3); the other five write at raw addresses nothing in the XDF
defines. That is normal for a TunerPro patch - a patch is a byte overwrite, not
a map edit - but it means:

  * xdf_verify.py will FAIL a bin with this patch applied, on exactly those
    bytes ("unexplained change"). That is the gate doing its job, not a false
    alarm, and you have to decide those 7 bytes are intended. The tool prints
    which ones and reconciles them for you.
  * their meaning rests on the reverse-engineering notes quoted in the XDF
    description, not on anything this tool can re-prove. What it CAN check, and
    does, is that each address lands inside the calibration block and that the
    stock bytes there are the values the description says they should be; every
    entry is reported with that result and its confidence.

The weakest entry is df31_gate_off (0x1D34B1): the XDF itself calls it
"supervised test only". The strongest is strat_state_attr_3_01, which fills a
table the XDF rates HIGH confidence.

TunerPro patches are pure overwrites with no base-data, so there is no undo
stored anywhere. --revert therefore needs your stock read and restores the
patched ranges from it; keep that file.

Checksums are NOT corrected - sign before flashing, and gate the result:

    xdf_verify.py 8hpe70_cali_v3.xdf stock.bin out.bin

Examples:
    xdf_truemanual.py stock.bin --preview            # what would change
    xdf_truemanual.py stock.bin --apply -o tm.bin    # write it
    xdf_truemanual.py tm.bin --status                # is it applied?
    xdf_truemanual.py tm.bin --revert --stock stock.bin -o back.bin
"""
import argparse
import os
import sys

from xdflib import XDF, load_bin, check_calibration

XDF_DEFAULT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           '..', '8hpe70_cali_v3.xdf')
DEFAULT_PATCH = 'True manual'
CAL_START, CAL_END = 0x180200, 0x200000

# Per-entry commentary, keyed by the entry name in the XDF (not by address, so
# the XDF stays authoritative for where the bytes go). 'expect' is the stock
# value the XDF description and docs/e70/parameters/10-patches-stage3.md claim
# is there; it is checked against the image and reported either way. An entry
# with no notes here is still applied - it is reported as undocumented.
NOTES = {
    'overspeed_limit_1': dict(
        expect=('u16', 7100),
        does='Guard test 1 in FUN_0012c9b8 - the forced-upshift / escalation '
             'rpm threshold. 0xFFFF puts it out of reach.',
        conf='Highest of the seven. This is the only entry an XDF item names '
             '(constant escalation_test1_threshold), and the stock word is '
             'exactly the 7100 the description claims. The XDF rates that '
             'constant itself LOW ("structure not proven"); its role in guard '
             'test 1 comes from the RE notes and is not re-proven here.'),
    'overspeed_limit_2': dict(
        expect=('u16', 6825),
        does='Second threshold of the same guard test, the u16 immediately '
             'after overspeed_limit_1. 0xFFFF puts it out of reach.',
        conf='MED. Stock reads the documented 6825 and it sits in the same '
             'little record as the word above (.. 0000 1BBC 1AA9 01E0 0064 ..), '
             'which is consistent with a threshold pair, but no XDF item '
             'defines it and no reader was re-checked here.'),
    'overspeed_margin_a': dict(
        expect=('u8', 105),
        does='df32 seed byte - the margin the test-2 threshold is scaled by. '
             '0xFF (255) makes that scaling 2.55x.',
        conf='MED. Stock reads the documented 105, and the two seeds sit as a '
             'pair (6969) in a field of 00/01 flags, which fits "two seeds". '
             'Meaning is from the RE notes only.'),
    'overspeed_margin_b': dict(
        expect=('u8', 105),
        does='The second df32 seed byte, same purpose as overspeed_margin_a.',
        conf='MED, same evidence as overspeed_margin_a.'),
    'revmatch_latch_arm': dict(
        expect=('u16', 6500),
        does='Rev-match latch arm point. 0xFFFF stops the latch arming.',
        conf='MED. Stock reads the documented 6500 and the neighbourhood '
             '(300, 2000, 100, 6400, 6500, 30, 30, 180) looks like an rpm '
             'parameter block, but no XDF item covers it and the name is from '
             'the RE notes.'),
    'df31_gate_off': dict(
        expect=('u8', 2),
        does='df31 gate threshold in FUN_0012c660, zeroed so the gate is open.',
        conf='LOWEST of the seven, and the XDF says so itself: "hinges on '
             'runtime def4 - supervised test only". Stock does read the '
             'documented 02, in a field of 01/02 bytes, but the deterministic '
             'fix is the program patch at 0x12CA44/56, which is outside the '
             'calibration and is not applied by this tool.'),
    'strat_state_attr_3_01': dict(
        expect=None,          # the docs state the write (fill 01), not a stock value
        does='The "K0 lever": fills strat_state_attr_3[100] with 01 so dd39 != 0 '
             'in every strategy state -> df31 = 1 -> the test-2 threshold '
             'becomes (da9c*df32)/100 = 2.55x with df32 = 255, so the ~7200 rpm '
             'forced upshift cannot fire.',
        conf='HIGH for the target, MED for the effect. These 100 bytes are the '
             'XDF table strat_state_attr_3, which the XDF rates HIGH '
             '(blind-verified u8[100] -> RAM fff8dd39). Stock being all 00 is '
             'the premise the chain above needs, and this address is in '
             'initialised data, so all-00 here is real. The chain itself is '
             'from the RE notes.'),
}


def select_patch(xdf, needle):
    """The one patch whose title contains needle (case-insensitive)."""
    hits = [p for p in xdf.patches if needle.lower() in (p.title or '').lower()]
    if not hits:
        have = ', '.join(repr(p.title) for p in xdf.patches) or 'none'
        sys.exit(f'no patch matching {needle!r} in this XDF (it has: {have})')
    if len(hits) > 1:
        sys.exit(f'{len(hits)} patches match {needle!r}: '
                 + ', '.join(repr(p.title) for p in hits))
    return hits[0]


def covered_by(xdf):
    """(mask, labels): which bytes xdf_verify will accept, and what covers them.

    Built with xdf_verify's own coverage_mask so this tool's prediction and the
    gate's verdict cannot drift apart.
    """
    try:
        from xdf_verify import coverage_mask
    except ImportError:
        return None, {}
    mask = coverage_mask(xdf, include_axes=False)
    labels = {}
    for t in xdf.tables:
        emb = t.z.embedded if t.z else None
        if emb is not None and emb.address is not None:
            labels.setdefault(emb.address, f'table {t.title}')
    for c in xdf.constants:
        if c.embedded.address is not None:
            labels.setdefault(c.embedded.address, f'constant {c.title}')
    return mask, labels


def uncovered_bytes(mask, addr, size):
    """How many of these bytes no XDF item describes (None if unknown)."""
    if mask is None:
        return None
    return sum(1 for k in range(addr, addr + size)
               if k >= len(mask) or not mask[k])


def orphan_ranges(mask, patch):
    """The ranges xdf_verify will call unexplained, merged the way it merges
    them, so its output can be compared line by line with this prediction."""
    if mask is None:
        return None
    owner = {}
    for e in patch.entries:
        for k in range(e.address, e.address + e.datasize):
            if k >= len(mask) or not mask[k]:
                owner[k] = e.name
    out = []
    for addr in sorted(owner):
        if out and addr == out[-1][1]:
            out[-1][1] = addr + 1
            if owner[addr] not in out[-1][2]:
                out[-1][2].append(owner[addr])
        else:
            out.append([addr, addr + 1, [owner[addr]]])
    return out


def as_number(raw, kind):
    if kind == 'u16' and len(raw) == 2:
        return int.from_bytes(raw, 'big')
    if kind == 'u8' and len(raw) == 1:
        return raw[0]
    return None


def describe_bytes(raw):
    """Short, honest rendering of a byte run."""
    if len(raw) <= 8:
        return raw.hex()
    if len(set(raw)) == 1:
        return f'{len(raw)} B, all 0x{raw[0]:02X}'
    return raw[:8].hex() + f'... ({len(raw)} B)'


def stock_verdict(entry, cur):
    """Does what is in the image match what the patch's documentation expects?"""
    note = NOTES.get(entry.name)
    if set(cur) == {0xFF} and cur != entry.patchdata[:entry.datasize]:
        return ('UNVERIFIABLE', 'all 0xFF - uninitialised in this image, so '
                                'nothing can be concluded about this address')
    if note is None or note.get('expect') is None:
        return ('UNDOCUMENTED', f'no documented stock value; image has '
                                f'{describe_bytes(cur)}')
    kind, want = note['expect']
    got = as_number(cur, kind)
    if got is None:
        return ('UNVERIFIABLE', f'cannot read as {kind}: {describe_bytes(cur)}')
    if got == want:
        return ('OK', f'stock {kind} {got} is the documented value')
    return ('MISMATCH', f'stock {kind} is {got}, documented stock is {want} - '
                        'this entry is NOT verified against this image')


def entry_state(buf, entry):
    """'applied', 'other', plus the current bytes."""
    cur = bytes(buf[entry.address:entry.address + entry.datasize])
    new = entry.patchdata[:entry.datasize]
    return ('applied' if cur == new else 'other'), cur, new


def check_entries_fit(patch, buf, name):
    for e in patch.entries:
        if e.address + e.datasize > len(buf):
            sys.exit(f'{e.name}: 0x{e.address:X}+0x{e.datasize:X} is past the '
                     f'end of {name} ({len(buf)} bytes)')
        if not (CAL_START <= e.address and
                e.address + e.datasize <= CAL_END):
            sys.exit(f'{e.name}: 0x{e.address:X}..0x{e.address + e.datasize:X} '
                     f'is outside the calibration block '
                     f'0x{CAL_START:X}..0x{CAL_END:X}. Refusing: this patch is '
                     'meant to write calibration data only.')


def identity_gate(buf, path, any_calibration):
    ok, msg = check_calibration(buf, os.path.basename(path))
    if ok:
        print(msg)
    elif any_calibration:
        print('WARNING: ' + msg, file=sys.stderr)
        print('continuing anyway because --any-calibration was given',
              file=sys.stderr)
    else:
        sys.exit(msg + '\n\nRefusing to touch it. Pass --any-calibration only '
                 'if you know why the identity differs.')


def preview(patch, buf, mask, labels):
    """Full report; returns the number of entries already applied."""
    total = sum(e.datasize for e in patch.entries)
    print(f'{patch.title}  ({len(patch.entries)} entries, {total} bytes)')
    applied = 0
    for e in patch.entries:
        state, cur, new = entry_state(buf, e)
        applied += state == 'applied'
        verdict, why = stock_verdict(e, cur)
        orphan = uncovered_bytes(mask, e.address, e.datasize)
        tag = 'ALREADY APPLIED' if state == 'applied' else 'will change'
        print(f'\n  {e.name:22s} @0x{e.address:X}  {e.datasize:3d} B  {tag}')
        print(f'      now:   {describe_bytes(cur)}')
        print(f'      write: {describe_bytes(new)}')
        note = NOTES.get(e.name)
        if note:
            print(f'      does:  {note["does"]}')
        else:
            print('      does:  not documented in this tool - applied as the '
                  'XDF specifies it, meaning unknown')
        print(f'      stock: {verdict} - {why}')
        if orphan is None:
            print('      cover: unknown (xdf_verify not importable)')
        elif orphan == 0:
            print(f'      cover: inside {labels.get(e.address, "an XDF item")} '
                  '- xdf_verify explains these bytes')
        else:
            print(f'      cover: {orphan} of {e.datasize} byte(s) are not '
                  'inside any XDF item - xdf_verify will flag them')
        if note:
            print(f'      conf:  {note["conf"]}')
    print(f'\n{applied}/{len(patch.entries)} entries already applied')
    return applied


def gate_note(ranges, xdf_path, src, out):
    if ranges:
        nbytes = sum(hi - lo for lo, hi, _ in ranges)
        print(f'\nxdf_verify will FAIL this bin with {nbytes} unexplained '
              f'byte(s) in {len(ranges)} range(s), and these exactly:')
        for lo, hi, names in ranges:
            print(f'  0x{lo:X}..0x{hi:X} ({hi - lo} B)  {", ".join(names)}')
        print('A TunerPro patch overwrites raw addresses and the XDF defines an '
              'item at only some of them, so a FAIL on exactly these ranges - '
              'and nothing else - is the expected result, not a sign the bin is '
              'broken. Compare the gate\'s list with this one: if they match, '
              'the only unexplained bytes are the patch\'s own. Any other FAIL '
              'is a real problem.')
    print(f'\ngate it: xdf_verify.py {xdf_path} {src} {out}')


def main():
    ap = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='Exit codes for --status: 0 fully applied, 1 not applied, '
               '3 partially applied.')
    ap.add_argument('bin', help='the calibration read to inspect or edit')
    ap.add_argument('-o', '--out', help='output bin for --apply / --revert')
    ap.add_argument('--xdf', default=XDF_DEFAULT)
    ap.add_argument('--patch', default=DEFAULT_PATCH,
                    help=f'patch title to match (default: {DEFAULT_PATCH!r})')
    ap.add_argument('--preview', action='store_true',
                    help='report every entry and what it would change; no write')
    ap.add_argument('--status', action='store_true',
                    help='report whether BIN already has the patch applied')
    ap.add_argument('--apply', action='store_true', help='write the patched bin')
    ap.add_argument('--revert', action='store_true',
                    help='restore the patched ranges from --stock (a TunerPro '
                         'patch stores no base data, so the stock read is the '
                         'only possible undo)')
    ap.add_argument('--stock', help='your stock read, required by --revert')
    ap.add_argument('--force', action='store_true',
                    help='--revert: restore even where BIN holds neither the '
                         'patch bytes nor the stock bytes (this overwrites '
                         'whatever else put them there)')
    ap.add_argument('--any-calibration', action='store_true',
                    help='proceed even if the image is a different calibration '
                         'from the one this XDF describes (the addresses then '
                         'mean something else - almost always wrong)')
    args = ap.parse_args()

    modes = sum(bool(m) for m in (args.preview, args.status, args.apply,
                                  args.revert))
    if modes != 1:
        ap.error('give exactly one of --preview, --status, --apply, --revert')
    if (args.apply or args.revert) and not args.out:
        ap.error('--apply and --revert need -o OUT (the input is never '
                 'overwritten)')
    if args.revert and not args.stock:
        ap.error('--revert needs --stock STOCK.bin: TunerPro patches carry no '
                 'base data, so there is no undo without your stock read')

    xdf = XDF(args.xdf)
    patch = select_patch(xdf, args.patch)
    buf_in = load_bin(args.bin, expect_size=0x200000)
    identity_gate(buf_in, args.bin, args.any_calibration)
    check_entries_fit(patch, buf_in, args.bin)

    if args.status:
        states = [entry_state(buf_in, e)[0] for e in patch.entries]
        n = states.count('applied')
        for e, s in zip(patch.entries, states):
            cur = bytes(buf_in[e.address:e.address + e.datasize])
            print(f'  {e.name:22s} @0x{e.address:X}  '
                  f'{"APPLIED" if s == "applied" else "not applied"}  '
                  f'({describe_bytes(cur)})')
        if n == len(patch.entries):
            print(f'\n"{patch.title}" IS applied to {args.bin} '
                  f'({n}/{n} entries)')
            return 0
        if n == 0:
            print(f'\n"{patch.title}" is NOT applied to {args.bin}')
            return 1
        print(f'\n"{patch.title}" is PARTIALLY applied to {args.bin} '
              f'({n}/{len(patch.entries)} entries). Either something else wrote '
              'these addresses or an apply was interrupted - do not flash this '
              'without working out which.')
        return 3

    mask, labels = covered_by(xdf)
    ranges = orphan_ranges(mask, patch)

    if args.preview:
        preview(patch, buf_in, mask, labels)
        gate_note(ranges, args.xdf, args.bin, '<out.bin>')
        print('\npreview only, no file written')
        return 0

    if args.apply:
        preview(patch, buf_in, mask, labels)
        buf = bytearray(buf_in)
        written = 0
        for e in patch.entries:
            new = e.patchdata[:e.datasize]
            if bytes(buf[e.address:e.address + e.datasize]) != new:
                buf[e.address:e.address + e.datasize] = new
                written += e.datasize
        with open(args.out, 'wb') as f:
            f.write(buf)
        print(f'\napplied "{patch.title}" -> {args.out} ({written} byte(s) '
              'changed; checksum NOT corrected - sign before flashing)')
        gate_note(ranges, args.xdf, args.bin, args.out)
        return 0

    # --revert
    stock = load_bin(args.stock, expect_size=0x200000)
    identity_gate(stock, args.stock, args.any_calibration)
    if len(stock) != len(buf_in):
        sys.exit(f'size mismatch: {args.bin} is {len(buf_in)} bytes, '
                 f'{args.stock} is {len(stock)}')
    check_entries_fit(patch, stock, args.stock)

    buf = bytearray(buf_in)
    conflicts, restored, noop = [], 0, 0
    for e in patch.entries:
        new = e.patchdata[:e.datasize]
        cur = bytes(buf[e.address:e.address + e.datasize])
        old = bytes(stock[e.address:e.address + e.datasize])
        if old == new:
            print(f'  {e.name:22s} @0x{e.address:X}  the stock image already '
                  'holds the patch bytes here - nothing to restore, and your '
                  '"stock" read may itself be patched')
            noop += 1
            continue
        if cur != new and cur != old:
            conflicts.append(f'{e.name} @0x{e.address:X}: {args.bin} has '
                             f'{describe_bytes(cur)}, which is neither the '
                             f'patch ({describe_bytes(new)}) nor your stock '
                             f'({describe_bytes(old)})')
        if cur != old:
            buf[e.address:e.address + e.datasize] = old
            restored += e.datasize
    if conflicts and not args.force:
        for c in conflicts:
            print('CONFLICT:', c, file=sys.stderr)
        sys.exit(f'\nRefusing to revert: {len(conflicts)} entry/entries hold '
                 'something else - another tune or patch probably wrote them, '
                 'and restoring stock there would silently undo that too. '
                 'Pass --force if that is what you want.')
    for c in conflicts:
        print('FORCED over a conflict:', c, file=sys.stderr)
    with open(args.out, 'wb') as f:
        f.write(buf)
    print(f'\nreverted "{patch.title}" from {args.bin} -> {args.out} using the '
          f'stock bytes in {args.stock} ({restored} byte(s) restored'
          + (f', {noop} entry/entries skipped' if noop else '') + ')')
    print('Only the patch ranges were touched; any other edit in the input is '
          'still there. Checksum NOT corrected.')
    print(f'\ncompare: cmp {args.stock} {args.out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
