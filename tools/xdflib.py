#!/usr/bin/env python3
"""xdflib - a minimal, dependency-free TunerPro XDF parser and bin decoder.

Written for 8hpe_cali_v3.xdf (ZF 8HP E-series TCU calibration) but generic
enough for most TunerPro 1.70 XDFs. Values are decoded straight from a
calibration image (the 2 MB bin this XDF is addressed against).

Notes on this XDF specifically:
  * All addresses are file offsets into the 2 MB image (BASEOFFSET 0),
    which equal the flash addresses (calibration block 0x180200-0x1FFFFF).
  * Data is big-endian unless an element sets the LSB-first flag.
  * mmedtypeflags bits: 0x01 signed, 0x02 LSB-first, 0x04 column-major,
    0x10000 float (IEEE754, 32-bit).
  * Strided layouts: every strided element in this file is column-major with
    mmedmajorstridebits=0 and mmedminorstridebits>0. Empirically (verified
    against the shift-line slot layout documented in the XDF descriptions),
    the column pitch is:  (rowcount-1)*elementsizebits + minorstridebits.
    That convention is what decode() implements; a different XDF generator
    may mean something else by these fields.

Drive-mode groups: the char-to-drive-mode mapping (which shift characteristic
a program like Sport selects) lives in the program ROM, not the calibration,
so the user assigns it after logging. load_mode_groups/save_mode_groups keep
that assignment in e84_modes.json next to the XDF; chars_for_mode resolves a
mode name to a chars filter for shift-line edits.

Use /usr/bin/python3 on macOS if your Homebrew python's expat is broken.
"""

import json as _json
import os as _os
import re as _re
import struct

try:
    import xml.etree.ElementTree as ET
    ET.fromstring('<probe/>')          # Homebrew pythons may lack pyexpat
    _HAVE_ET = True
except ImportError:
    _HAVE_ET = False


class _MiniEl:
    """Tiny ElementTree-compatible element for the expat-free fallback."""
    __slots__ = ('tag', 'attrib', 'children', 'text')

    def __init__(self, tag, attrib):
        self.tag, self.attrib, self.children, self.text = tag, attrib, [], None

    def get(self, key, default=None):
        return self.attrib.get(key, default)

    def find(self, tag):
        for c in self.children:
            if c.tag == tag:
                return c
        return None

    def findall(self, tag):
        return [c for c in self.children if c.tag == tag]

    def findtext(self, tag, default=None):
        c = self.find(tag)
        return c.text if c is not None and c.text is not None else default


def _unescape(s):
    for ent, ch in (('&lt;', '<'), ('&gt;', '>'), ('&quot;', '"'),
                    ('&apos;', "'"), ('&amp;', '&')):
        s = s.replace(ent, ch)
    return s


_TOKEN = _re.compile(
    r'<!--.*?-->'                                   # comments
    r'|<\?[^>]*\?>'                                 # declarations
    r'|<([A-Za-z_][-\w.]*)((?:\s+[-\w.:]+="[^"]*")*)\s*(/?)>'  # open/empty
    r'|</([-\w.:]+)\s*>', _re.S)
_ATTR = _re.compile(r'([-\w.:]+)="([^"]*)"')


def _parse_no_expat(path):
    """Minimal non-validating XML parser (no pyexpat) sufficient for XDFs."""
    with open(path, newline='') as f:
        src = f.read()
    root = None
    stack = []
    pos = 0
    for m in _TOKEN.finditer(src):
        if stack and stack[-1].text is None:
            gap = src[pos:m.start()].strip()
            if gap:
                stack[-1].text = _unescape(gap)
        pos = m.end()
        if m.group(1):                               # open or self-closing
            el = _MiniEl(m.group(1), {k: _unescape(v) for k, v
                                      in _ATTR.findall(m.group(2) or '')})
            if stack:
                stack[-1].children.append(el)
            elif root is None:
                root = el
            if not m.group(3):                       # not self-closing
                stack.append(el)
        elif m.group(4):                             # close tag
            while stack and stack[-1].tag != m.group(4):
                stack.pop()                          # tolerate mismatches
            if stack:
                stack.pop()
    if root is None:
        raise ValueError(f'{path}: no XML root element found')
    return root

FLAG_SIGNED = 0x01
FLAG_LSBFIRST = 0x02
FLAG_COLMAJOR = 0x04
FLAG_FLOAT = 0x10000


def _int(s, default=0):
    if s is None:
        return default
    try:
        return int(str(s).strip(), 0)
    except ValueError:
        return default


class Embedded:
    """One EMBEDDEDDATA element: where and how raw values live in the bin."""

    def __init__(self, el):
        el = el if el is not None else ET.Element('EMBEDDEDDATA')
        self.flags = _int(el.get('mmedtypeflags'), 0)
        addr = el.get('mmedaddress')
        self.address = _int(addr) if addr else None
        self.elem_bits = _int(el.get('mmedelementsizebits'), 8)
        self.rowcount = _int(el.get('mmedrowcount'), 0)
        self.colcount = _int(el.get('mmedcolcount'), 0)
        self.major_stride = _int(el.get('mmedmajorstridebits'), 0)
        self.minor_stride = _int(el.get('mmedminorstridebits'), 0)

    @property
    def signed(self):
        return bool(self.flags & FLAG_SIGNED)

    @property
    def little_endian(self):
        return bool(self.flags & FLAG_LSBFIRST)

    @property
    def col_major(self):
        return bool(self.flags & FLAG_COLMAJOR)

    @property
    def is_float(self):
        return bool(self.flags & FLAG_FLOAT)

    def type_name(self):
        if self.is_float:
            return f'f{self.elem_bits}'
        return f'{"s" if self.signed else "u"}{self.elem_bits}'


class Axis:
    def __init__(self, el):
        self.id = el.get('id')
        self.embedded = Embedded(el.find('EMBEDDEDDATA'))
        self.count = _int(el.findtext('indexcount'), 0)
        self.units = (el.findtext('units') or '').strip() or None
        math = el.find('MATH')
        self.equation = math.get('equation') if math is not None else 'X'
        self.labels = [l.get('value') for l in el.findall('LABEL')] or None


class Item:
    """Common base for tables and constants."""

    kind = 'item'

    def __init__(self, el, categories):
        self.uid = el.get('uniqueid')
        self.title = (el.findtext('title') or '').strip()
        self.description = el.findtext('description') or ''
        self.categories = []
        for cm in el.findall('CATEGORYMEM'):
            idx = _int(cm.get('category')) - 1  # CATEGORYMEM is 1-based
            self.categories.append(categories.get(idx, f'?{idx}'))


class Table(Item):
    kind = 'table'

    def __init__(self, el, categories):
        super().__init__(el, categories)
        self.axes = {}
        for ax in el.findall('XDFAXIS'):
            self.axes[ax.get('id')] = Axis(ax)

    @property
    def z(self):
        return self.axes.get('z')

    def shape(self):
        """(rows, cols) of the z data."""
        z = self.z.embedded if self.z else Embedded(None)
        rows = z.rowcount or (self.axes.get('y').count if 'y' in self.axes else 1) or 1
        cols = z.colcount or (self.axes.get('x').count if 'x' in self.axes else 1) or 1
        return rows, cols


class Constant(Item):
    kind = 'constant'

    def __init__(self, el, categories):
        super().__init__(el, categories)
        self.embedded = Embedded(el.find('EMBEDDEDDATA'))
        self.units = (el.findtext('units') or '').strip() or None
        math = el.find('MATH')
        self.equation = math.get('equation') if math is not None else 'X'


class PatchEntry:
    def __init__(self, el):
        self.name = el.get('name')
        self.address = _int(el.get('address'))
        self.datasize = _int(el.get('datasize'))
        self.patchdata = bytes.fromhex(el.get('patchdata') or '')
        base = el.get('basedata')
        self.basedata = bytes.fromhex(base) if base else None


class Patch(Item):
    kind = 'patch'

    def __init__(self, el, categories):
        super().__init__(el, categories)
        self.entries = [PatchEntry(e) for e in el.findall('XDFPATCHENTRY')]


class XDF:
    def __init__(self, path):
        self.path = path
        if _HAVE_ET:
            root = ET.parse(path).getroot()
        else:                       # pyexpat broken (some Homebrew pythons)
            root = _parse_no_expat(path)
        hdr = root.find('XDFHEADER')
        self.title = hdr.findtext('deftitle')
        self.description = hdr.findtext('description')
        self.categories = {}
        for c in hdr.findall('CATEGORY'):
            self.categories[_int(c.get('index'))] = c.get('name')
        self.tables = [Table(t, self.categories) for t in root.findall('XDFTABLE')]
        self.constants = [Constant(c, self.categories) for c in root.findall('XDFCONSTANT')]
        self.patches = [Patch(p, self.categories) for p in root.findall('XDFPATCH')]

    @property
    def items(self):
        return self.tables + self.constants + self.patches

    def find(self, needle):
        """Items whose title or uid matches needle (case-insensitive substring)."""
        n = needle.lower()
        return [i for i in self.items
                if n in (i.title or '').lower() or n == (i.uid or '').lower()]

    def at_address(self, addr, slack=0):
        """Tables/constants whose data starts within [addr-slack, addr+slack]."""
        out = []
        for t in self.tables:
            z = t.z.embedded if t.z else None
            if z and z.address is not None and abs(z.address - addr) <= slack:
                out.append(t)
        for c in self.constants:
            if c.embedded.address is not None and abs(c.embedded.address - addr) <= slack:
                out.append(c)
        return out


# ---------------------------------------------------------------- decoding

def element_offset(emb, rows, cols, r, c):
    """Byte offset of element (r, c) in the bin, honouring this XDF's layout
    conventions (see module docstring)."""
    elem_bytes = emb.elem_bits // 8
    if emb.minor_stride and emb.col_major:
        col_pitch_bits = (rows - 1) * emb.elem_bits + emb.minor_stride
        if col_pitch_bits % 8:
            raise ValueError('column pitch is not byte-aligned')
        return emb.address + c * (col_pitch_bits // 8) + r * elem_bytes
    if emb.minor_stride or emb.major_stride:
        raise ValueError('unsupported stride layout '
                         f'(major={emb.major_stride}, minor={emb.minor_stride}, '
                         f'flags=0x{emb.flags:X})')
    if emb.col_major:
        return emb.address + (c * rows + r) * elem_bytes
    return emb.address + (r * cols + c) * elem_bytes


def value_range(emb):
    """(min, max) storable in one element."""
    if emb.is_float:
        return (-3.4e38, 3.4e38)
    bits = emb.elem_bits
    if emb.signed:
        return (-(1 << (bits - 1)), (1 << (bits - 1)) - 1)
    return (0, (1 << bits) - 1)


def write_elem(buf, byte_off, emb, value, clamp=True):
    """Encode one value into a bytearray at byte_off. Returns the stored value
    (after clamping/rounding for integer types)."""
    size = emb.elem_bits // 8
    bo = '<' if emb.little_endian else '>'
    if emb.is_float:
        fmt = {4: 'f', 8: 'd'}[size]
        stored = float(value)
    else:
        lo, hi = value_range(emb)
        stored = int(round(value))
        if clamp:
            stored = max(lo, min(hi, stored))
        elif not lo <= stored <= hi:
            raise ValueError(f'{value} out of range for {emb.type_name()}')
        fmt = {1: 'b' if emb.signed else 'B',
               2: 'h' if emb.signed else 'H',
               4: 'i' if emb.signed else 'I'}[size]
    struct.pack_into(bo + fmt, buf, byte_off, stored)
    return stored


def _read_elem(buf, byte_off, emb):
    size = emb.elem_bits // 8
    raw = buf[byte_off:byte_off + size]
    if len(raw) < size:
        raise IndexError(f'read past end of bin at 0x{byte_off:X}')
    bo = '<' if emb.little_endian else '>'
    if emb.is_float:
        fmt = {4: 'f', 8: 'd'}[size]
    else:
        fmt = {1: 'b' if emb.signed else 'B',
               2: 'h' if emb.signed else 'H',
               4: 'i' if emb.signed else 'I'}[size]
    return struct.unpack(bo + fmt, raw)[0]


def apply_equation(value, equation):
    """Evaluate a TunerPro MATH equation for one cell. Supports the usual
    arithmetic forms (X*0.1+5 etc.); this XDF uses plain 'X' throughout."""
    eq = (equation or 'X').strip()
    if eq.upper() == 'X':
        return value
    allowed = set('0123456789.+-*/()xX eE,')
    if not set(eq) <= allowed:
        raise ValueError(f'unsupported equation: {equation!r}')
    return eval(eq.replace('x', 'X').replace('X', repr(value)),
                {'__builtins__': {}}, {})


def decode_embedded(buf, emb, rows, cols, equation='X'):
    """Decode a rows x cols block as a list of rows (row = list of values)."""
    if emb.address is None:
        return None
    out = [[None] * cols for _ in range(rows)]
    for r in range(rows):
        for c in range(cols):
            off = element_offset(emb, rows, cols, r, c)
            out[r][c] = apply_equation(_read_elem(buf, off, emb), equation)
    return out


def decode_axis(buf, axis):
    """Decode a 1-D axis; returns labels if the axis has no stored data."""
    if axis is None:
        return None
    if axis.embedded.address is None:
        return axis.labels or list(range(1, (axis.count or 1) + 1))
    grid = decode_embedded(buf, axis.embedded, 1, axis.count or 1, axis.equation)
    return grid[0] if grid else None


def decode_table(buf, table):
    """Decode a full table -> dict with x, y, z (z = list of rows)."""
    rows, cols = table.shape()
    z = table.z
    return {
        'title': table.title,
        'rows': rows,
        'cols': cols,
        'type': z.embedded.type_name() if z else None,
        'x': decode_axis(buf, table.axes.get('x')),
        'y': decode_axis(buf, table.axes.get('y')),
        'z': decode_embedded(buf, z.embedded, rows, cols, z.equation) if z else None,
        'x_units': table.axes.get('x').units if 'x' in table.axes else None,
        'y_units': table.axes.get('y').units if 'y' in table.axes else None,
        'z_units': z.units if z else None,
    }


def decode_constant(buf, const):
    val = _read_elem(buf, const.embedded.address, const.embedded)
    return apply_equation(val, const.equation)


# ---------------------------------------------------------- drive-mode groups

MODES_FILENAME = 'e84_modes.json'
_CHAR_TITLE = _re.compile(r'<title>(?:Up|Down)shift char (\d+):')


def _modes_path(xdf_path):
    return _os.path.join(_os.path.dirname(_os.path.abspath(xdf_path)),
                         MODES_FILENAME)


def _all_chars(xdf_path):
    """Every shift-characteristic number named in the XDF (cheap text scan)."""
    with open(xdf_path, errors='replace') as f:
        return {int(m.group(1)) for m in _CHAR_TITLE.finditer(f.read())}


def load_mode_groups(xdf_path):
    """Robust wrapper: malformed e84_modes.json raises ValueError with guidance."""
    try:
        return _load_mode_groups_raw(xdf_path)
    except (TypeError, AttributeError, KeyError) as e:
        raise ValueError(
            'e84_modes.json is malformed (expected {"sport": [ints], "normal": [ints]}): %s' % e)


def _load_mode_groups_raw(xdf_path):
    """{'sport': set, 'normal': set} of characteristic numbers, read from
    e84_modes.json next to the XDF. Defaults when the file is missing:
    normal = all chars in the XDF, sport = empty (unassigned)."""
    path = _modes_path(xdf_path)
    if not _os.path.exists(path):
        return {'sport': set(), 'normal': _all_chars(xdf_path)}
    with open(path) as f:
        data = _json.load(f)
    sport = {int(c) for c in data.get('sport', [])}
    normal = {int(c) for c in data.get('normal', [])}
    return {'sport': sport, 'normal': normal or (_all_chars(xdf_path) - sport)}


def save_mode_groups(xdf_path, groups):
    """Write mode groups ({'sport': iterable, 'normal': iterable}) to
    e84_modes.json next to the XDF; returns the path written."""
    path = _modes_path(xdf_path)
    with open(path, 'w') as f:
        _json.dump({k: sorted(int(c) for c in v) for k, v in groups.items()},
                   f, indent=1)
        f.write('\n')
    return path


def chars_for_mode(xdf_path, mode):
    """Resolve a drive mode to a chars filter for shift-line edits:
    'all' (or None) -> None (no filter), 'normal'/'sport' -> the assigned set.
    Unassigned sport is a hard error, never a silent no-op: the mapping is not
    recoverable from a calibration-only read, so the user must assign it."""
    if mode in (None, 'all'):
        return None
    if mode not in ('normal', 'sport'):
        raise ValueError(f'unknown mode {mode!r}')
    chars = load_mode_groups(xdf_path)[mode]
    if mode == 'sport' and not chars:
        raise SystemExit(
            'sport characteristics are not assigned yet: a calibration-only '
            'read cannot recover which chars the Sport program selects. '
            'Identify them by logging, then assign them in the GUI Modes '
            f'panel or write {_modes_path(xdf_path)} like {{"sport": [8, 9]}}.')
    return chars


def load_bin(path, expect_size=None):
    with open(path, 'rb') as f:
        data = f.read()
    if expect_size and len(data) != expect_size:
        import sys
        print(f'warning: {path} is {len(data)} bytes, expected {expect_size} '
              '(this XDF is addressed against the full 2 MB image)',
              file=sys.stderr)
    return data
