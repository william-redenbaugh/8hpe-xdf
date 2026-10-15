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

Use /usr/bin/python3 on macOS if your Homebrew python's expat is broken.
"""

import struct
import xml.etree.ElementTree as ET

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
        tree = ET.parse(path)
        root = tree.getroot()
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


def load_bin(path, expect_size=None):
    with open(path, 'rb') as f:
        data = f.read()
    if expect_size and len(data) != expect_size:
        import sys
        print(f'warning: {path} is {len(data)} bytes, expected {expect_size} '
              '(this XDF is addressed against the full 2 MB image)',
              file=sys.stderr)
    return data
