#!/usr/bin/env python3
"""Tkinter GUI for editing a calibration image through the XDF.

Zero dependencies (stdlib only). Run with the system Python on macOS if
Homebrew's fails on XML:  /usr/bin/python3 tools/xdf_gui.py

  python3 xdf_gui.py [xdf_path] [bin_path]

Features:
  * Browse/search every table and constant defined in the XDF.
  * Grid editor for a single table (axes decoded live from the bin).
  * Bulk edit: select a *set* of related tables by search/category and apply
    one offset or percent scale to all of them at once, with a slider,
    a live preview, and optional sentinel skipping.
  * Shift speed preset: one slider that moves the shift lines of selected
    characteristics and gear pairs together (upshifts, optionally dragging
    the matching downshift lines along to preserve hysteresis). 8000-rpm
    "shift disabled" sentinels are never touched.
  * Drive modes: a Modes tab assigns shift characteristics to Normal/Sport
    (saved to e84_modes.json next to the XDF, shared with xdf_tune --mode);
    the shift-speed slider and the NA redline / early-upshift presets can
    then target one mode. Quickness stays global (shared execution tables).
  * TCC lockup preset: one slider scaling the converter close time down and
    the close pressure / ramp rate up for faster lockup (global maps).
  * Undo stack, change list vs. the loaded original, save-as (never in place).

Checksums are NOT corrected - run the saved bin through your checksum flow
(8HPe Quickflash corrects at flash time).
"""
import re
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import xdf_tune
from xdflib import (XDF, MODES_FILENAME, chars_for_mode, decode_axis,
                    decode_constant, decode_table, element_offset, load_bin,
                    load_mode_groups, save_mode_groups, write_elem)

SENTINEL_DEFAULT = 7900  # raw values >= this are treated as "disabled" markers
UP_CURVE = re.compile(r'^Upshift char (\d+): (\d)>(\d)$')
DN_CURVE = re.compile(r'^Downshift char (\d+): (\d)>(\d)$')
GEAR_PAIRS = ['1>2', '2>3', '3>4', '4>5', '5>6', '6>7', '7>8']


class Workspace:
    """The XDF + original and working bins + undo stack."""

    def __init__(self, xdf_path):
        self.xdf = XDF(xdf_path)
        self.orig = None
        self.work = None
        self.bin_path = None
        self.undo_stack = []  # (description, [(addr, old_bytes, new_bytes), ...])

    def load(self, bin_path):
        self.orig = bytes(load_bin(bin_path, expect_size=0x200000))
        self.work = bytearray(self.orig)
        self.bin_path = bin_path
        self.undo_stack.clear()

    # -- editing ----------------------------------------------------------
    def set_cells(self, description, writes):
        """writes = [(emb, rows, cols, r, c, value), ...]; one undo entry."""
        patch = []
        for emb, rows, cols, r, c, value in writes:
            off = element_offset(emb, rows, cols, r, c)
            size = emb.elem_bits // 8
            old = bytes(self.work[off:off + size])
            write_elem(self.work, off, emb, value)
            new = bytes(self.work[off:off + size])
            if old != new:
                patch.append((off, old, new))
        if patch:
            self.undo_stack.append((description, patch))
        return len(patch)

    def undo(self):
        if not self.undo_stack:
            return None
        description, patch = self.undo_stack.pop()
        for off, old, _new in patch:
            self.work[off:off + len(old)] = old
        return description

    def changed_items(self):
        """Tables/constants whose bytes differ from the original."""
        out = []
        seen_addr = set()
        for t in self.xdf.tables:
            emb = t.z.embedded if t.z else None
            if not emb or emb.address is None or emb.address in seen_addr:
                continue
            rows, cols = t.shape()
            try:
                n = sum(1 for r in range(rows) for c in range(cols)
                        if self._cell_differs(emb, rows, cols, r, c))
            except (ValueError, IndexError):
                continue
            if n:
                seen_addr.add(emb.address)
                out.append((t, n))
        for const in self.xdf.constants:
            emb = const.embedded
            if emb.address is None or emb.address in seen_addr:
                continue
            size = emb.elem_bits // 8
            if self.work[emb.address:emb.address + size] != \
                    self.orig[emb.address:emb.address + size]:
                seen_addr.add(emb.address)
                out.append((const, 1))
        return out

    def _cell_differs(self, emb, rows, cols, r, c):
        off = element_offset(emb, rows, cols, r, c)
        size = emb.elem_bits // 8
        return self.work[off:off + size] != self.orig[off:off + size]

    def revert_item(self, item):
        if item.kind == 'constant':
            emb, rows, cols = item.embedded, 1, 1
        else:
            emb = item.z.embedded
            rows, cols = item.shape()
        patch = []
        for r in range(rows):
            for c in range(cols):
                off = element_offset(emb, rows, cols, r, c)
                size = emb.elem_bits // 8
                old = bytes(self.work[off:off + size])
                new = self.orig[off:off + size]
                if old != new:
                    self.work[off:off + size] = new
                    patch.append((off, old, bytes(new)))
        if patch:
            self.undo_stack.append((f'revert {item.title}', patch))


# ------------------------------------------------------------------ presets
# Plain write-builders shared by the preset tabs: they read ws.work and
# return [(emb, rows, cols, r, c, value), ...] for Workspace.set_cells, so
# applies go through the undo stack and the same code runs headless (tests).
# Curve selection is xdf_tune's, so GUI edits land on exactly the cells the
# CLI would touch (dead 0-rpm slots and 8000 sentinels are never moved).

_MODE_CACHE = {}


def mode_chars(xdf_path, mode):
    """Resolve a drive-mode radio to a chars filter like the CLI --mode does:
    returns (chars_set_or_None, error). None = no filter ('all'). The
    unassigned-sport error is returned rather than raised so Tk callbacks can
    show it without killing the mainloop; results are cached on the modes
    file's mtime (the 'normal' default rescans the XDF, which is not free)."""
    if mode in (None, 'all'):
        return None, None
    mpath = os.path.join(os.path.dirname(os.path.abspath(xdf_path)),
                         MODES_FILENAME)
    try:
        key = (os.path.abspath(xdf_path), mode, os.path.getmtime(mpath))
    except OSError:
        key = (os.path.abspath(xdf_path), mode, None)
    if key not in _MODE_CACHE:
        try:
            _MODE_CACHE[key] = (chars_for_mode(xdf_path, mode), None)
        except SystemExit as e:
            _MODE_CACHE[key] = (None, str(e))
        except (OSError, ValueError) as e:
            _MODE_CACHE[key] = (None, f'cannot read mode groups: {e}')
    return _MODE_CACHE[key]


def xdf_shift_chars(xdf):
    """Sorted shift-characteristic numbers named by the XDF's shift lines."""
    chars = set()
    for t in xdf.tables:
        m = UP_CURVE.match(t.title) or DN_CURVE.match(t.title)
        if m:
            chars.add(int(m.group(1)))
    return sorted(chars)


def shift_offset_writes(ws, amount, pairs=None, chars=None, move_down=True):
    """Move the selected shift lines by `amount` output rpm; returns
    (writes, curve_count)."""
    kinds = ('up', 'down') if move_down else ('up',)
    curves = xdf_tune.shift_curves(ws.xdf, kinds, pairs, chars)
    writes = []
    for t, _k, _ch, _p in curves:
        rows, cols = t.shape()
        emb = t.z.embedded
        d = decode_table(ws.work, t)
        for r in range(rows):
            for c in range(cols):
                v = d['z'][r][c]
                if v <= 0 or v >= SENTINEL_DEFAULT:
                    continue
                writes.append((emb, rows, cols, r, c, max(0, v + amount)))
    return writes, len(curves)


def redline_hold_writes(ws, targets, chars=None):
    """Raise upshift lines to per-pair target output rpm (never lower them).
    targets = {'1>2': rpm, ...}; returns (writes, per-pair counts)."""
    writes, counts = [], {p: 0 for p in targets}
    for t, _k, _ch, pair in xdf_tune.shift_curves(ws.xdf, ('up',),
                                                  set(targets), chars):
        rows, cols = t.shape()
        emb = t.z.embedded
        d = decode_table(ws.work, t)
        tgt = targets[pair]
        for r in range(rows):
            for c in range(cols):
                v = d['z'][r][c]
                if v <= 0 or v >= SENTINEL_DEFAULT or tgt <= v:
                    continue
                writes.append((emb, rows, cols, r, c, tgt))
                counts[pair] += 1
    return writes, counts


def early_upshift_writes(ws, amount, chars=None):
    """Pedal-weighted early upshift (full at closed throttle, zero from 80%
    pedal), clamped >= matching downshift + 100. Returns (writes, clamped)."""
    down = {(ch, p): t for t, _k, ch, p
            in xdf_tune.shift_curves(ws.xdf, ('down',), chars=chars)}
    writes, clamped = [], 0
    for t, _k, ch, pair in xdf_tune.shift_curves(ws.xdf, ('up',), chars=chars):
        rows, cols = t.shape()
        emb = t.z.embedded
        d = decode_table(ws.work, t)
        pedal = d['x'] if d['x'] and isinstance(d['x'][0], (int, float)) else None
        dt = down.get((ch, pair))
        try:
            dvals = decode_table(ws.work, dt)['z'] if dt is not None else None
        except (ValueError, IndexError):
            dvals = None
        for r in range(rows):
            for c in range(cols):
                v = d['z'][r][c]
                if v <= 0 or v >= SENTINEL_DEFAULT:
                    continue
                p = pedal[c] if pedal and c < len(pedal) else 0
                weight = max(0.0, 1 - p / 800.0)
                if weight <= 0:
                    continue
                new = v - amount * weight
                if dvals is not None and r < len(dvals):
                    dv = dvals[r][c]
                    if 0 < dv < SENTINEL_DEFAULT and new < dv + 100:
                        new = dv + 100
                        clamped += 1
                new = max(0, round(new))
                if new != v:
                    writes.append((emb, rows, cols, r, c, new))
    return writes, clamped


def tcc_lockshift_writes(ws, pct):
    """Run xdf_tune.op_tcc_lockshift on a COPY of the working bin and turn
    the deltas into set_cells writes. Returns (writes, done) with done =
    [(title, pct, changed, cells), ...] straight from the op."""
    tmp = bytearray(ws.work)
    done = xdf_tune.op_tcc_lockshift(tmp, ws.xdf, pct)
    writes = []
    for title, _p, _n, _cells in done:
        t = next(t for t in ws.xdf.tables if t.title == title)
        rows, cols = t.shape()
        emb = t.z.embedded
        old = decode_table(ws.work, t)['z']
        new = decode_table(tmp, t)['z']
        for r in range(rows):
            for c in range(cols):
                if new[r][c] != old[r][c]:
                    writes.append((emb, rows, cols, r, c, new[r][c]))
    return writes, done


class App(tk.Tk):
    def __init__(self, xdf_path, bin_path=None):
        super().__init__()
        self.title('8HP XDF editor')
        self.geometry('1200x760')
        self.ws = Workspace(xdf_path)

        self._build_toolbar()
        body = ttk.Panedwindow(self, orient='horizontal')
        body.pack(fill='both', expand=True)
        self._build_browser(body)
        self._build_tabs(body)
        self._refresh_list()
        self._set_status(f'XDF loaded: {len(self.ws.xdf.items)} items. '
                         'Open a bin to start editing.')
        if bin_path:
            self._load_bin(bin_path)

    # -- chrome -----------------------------------------------------------
    def _build_toolbar(self):
        bar = ttk.Frame(self, padding=4)
        bar.pack(fill='x')
        ttk.Button(bar, text='Open XDF…', command=self._open_xdf).pack(side='left')
        ttk.Button(bar, text='Open bin…', command=self._open_bin).pack(side='left', padx=4)
        ttk.Button(bar, text='Save bin as…', command=self._save_bin).pack(side='left', padx=4)
        ttk.Button(bar, text='Undo', command=self._undo).pack(side='left')
        ttk.Button(bar, text='Sign bin', command=self._sign_bin).pack(side='left', padx=4)
        ttk.Button(bar, text='Flash…', command=self._flash_info).pack(side='left')
        self.status = ttk.Label(bar, text='', anchor='w')
        self.status.pack(side='left', fill='x', expand=True, padx=12)

    def _set_status(self, text):
        self.status.config(text=text)

    def _open_xdf(self):
        path = filedialog.askopenfilename(
            title='Open XDF definition',
            filetypes=[('XDF files', '*.xdf'), ('All files', '*')])
        if path:
            self._load_xdf(path)

    def _load_xdf(self, path):
        try:
            self.ws.xdf = XDF(path)
        except Exception as e:
            messagebox.showerror('XDF load failed', str(e))
            return
        cats = ['(all categories)'] + [self.ws.xdf.categories[k]
                                       for k in sorted(self.ws.xdf.categories)]
        self.cat_combo['values'] = cats
        self.cat_var.set('(all categories)')
        self.bulk_combo['values'] = ['(all)'] + cats[1:]
        self.bulk_cat.set('(all)')
        self.title(f'8HP XDF editor - {path.rsplit("/", 1)[-1]}')
        self._refresh_list()
        self._modes_refresh()
        self._set_status(f'XDF: {path} ({len(self.ws.xdf.items)} items). '
                         + (f'Editing {self.ws.bin_path}' if self.ws.work is not None
                            else 'Open a bin to start editing.'))

    def _open_bin(self):
        path = filedialog.askopenfilename(
            title='Open calibration image (full 2 MB read)',
            filetypes=[('Bin files', '*.bin'), ('All files', '*')])
        if path:
            self._load_bin(path)

    def _load_bin(self, path):
        try:
            self.ws.load(path)
        except OSError as e:
            messagebox.showerror('Open failed', str(e))
            return
        if len(self.ws.orig) != 0x200000:
            messagebox.showwarning(
                'Unexpected size',
                f'{path}\nis {len(self.ws.orig)} bytes - this XDF is addressed '
                'against the full 2 MB image. Addresses will not line up on a '
                'calibration-only read.')
        self._set_status(f'Editing {path}')
        self._show_selected()

    def _save_bin(self):
        if self.ws.work is None:
            messagebox.showinfo('No bin', 'Open a bin first.')
            return
        path = filedialog.asksaveasfilename(
            title='Save modified bin as', defaultextension='.bin',
            filetypes=[('Bin files', '*.bin')])
        if not path:
            return
        with open(path, 'wb') as f:
            f.write(self.ws.work)
        changed = len(self.ws.changed_items())
        messagebox.showinfo(
            'Saved', f'Saved to {path}\n{changed} item(s) differ from the '
            'original.\n\nChecksums are NOT corrected - run your checksum '
            'flow before flashing.')

    def _undo(self):
        desc = self.ws.undo()
        self._set_status(f'Undid: {desc}' if desc else 'Nothing to undo.')
        self._show_selected()
        self._refresh_changes()

    # -- browser ----------------------------------------------------------
    def _build_browser(self, parent):
        frame = ttk.Frame(parent, padding=4)
        parent.add(frame, weight=1)
        self.search_var = tk.StringVar()
        self.search_var.trace_add('write', lambda *a: self._refresh_list())
        ttk.Entry(frame, textvariable=self.search_var).pack(fill='x')
        cats = ['(all categories)'] + [self.ws.xdf.categories[k]
                                       for k in sorted(self.ws.xdf.categories)]
        self.cat_var = tk.StringVar(value=cats[0])
        self.cat_combo = ttk.Combobox(frame, textvariable=self.cat_var,
                                      values=cats, state='readonly')
        self.cat_combo.pack(fill='x', pady=2)
        self.cat_combo.bind('<<ComboboxSelected>>', lambda e: self._refresh_list())
        wrap = ttk.Frame(frame)
        wrap.pack(fill='both', expand=True)
        self.listbox = tk.Listbox(wrap, exportselection=False)
        sb = ttk.Scrollbar(wrap, command=self.listbox.yview)
        self.listbox.config(yscrollcommand=sb.set)
        self.listbox.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')
        self.listbox.bind('<<ListboxSelect>>', lambda e: self._show_selected())
        self.count_label = ttk.Label(frame, text='')
        self.count_label.pack(anchor='w')

    def _refresh_list(self):
        needle = self.search_var.get().lower()
        cat = self.cat_var.get()
        self.visible = []
        for i in self.ws.xdf.tables + self.ws.xdf.constants:
            if needle and needle not in i.title.lower():
                continue
            if cat != '(all categories)' and cat not in i.categories:
                continue
            self.visible.append(i)
        self.listbox.delete(0, 'end')
        for i in self.visible:
            self.listbox.insert('end', i.title)
        self.count_label.config(text=f'{len(self.visible)} items')

    # -- tabs -------------------------------------------------------------
    def _build_tabs(self, parent):
        self.tabs = ttk.Notebook(parent)
        parent.add(self.tabs, weight=3)
        self._build_table_tab()
        self._build_bulk_tab()
        self._build_shift_tab()
        self._build_na_tab()
        self._build_tcc_tab()
        self._build_modes_tab()
        self._build_vehicle_tab()
        self._build_changes_tab()
        self.tabs.bind('<<NotebookTabChanged>>', lambda e: (
            self._refresh_changes(), self._wheel_refresh()))

    # -- single table editor ----------------------------------------------
    def _build_table_tab(self):
        tab = ttk.Frame(self.tabs, padding=6)
        self.tabs.add(tab, text='Table')
        self.table_info = ttk.Label(tab, text='Select an item on the left.',
                                    wraplength=760, justify='left')
        self.table_info.pack(anchor='w')
        canvas = tk.Canvas(tab, highlightthickness=0)
        ysb = ttk.Scrollbar(tab, orient='vertical', command=canvas.yview)
        xsb = ttk.Scrollbar(tab, orient='horizontal', command=canvas.xview)
        canvas.configure(yscrollcommand=ysb.set, xscrollcommand=xsb.set)
        ysb.pack(side='right', fill='y')
        xsb.pack(side='bottom', fill='x')
        canvas.pack(fill='both', expand=True)
        self.grid_frame = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=self.grid_frame, anchor='nw')
        self.grid_frame.bind(
            '<Configure>',
            lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        btns = ttk.Frame(tab)
        btns.pack(fill='x', pady=4)
        ttk.Button(btns, text='Apply edits', command=self._apply_grid).pack(side='left')
        ttk.Button(btns, text='Reload', command=self._show_selected).pack(side='left', padx=4)

    def _selected_item(self):
        sel = self.listbox.curselection()
        return self.visible[sel[0]] if sel else None

    def _show_selected(self):
        for w in self.grid_frame.winfo_children():
            w.destroy()
        self.cell_vars = []
        item = self._selected_item()
        if item is None:
            return
        desc = (item.description or '').strip().split('\n')[0][:300]
        if self.ws.work is None:
            self.table_info.config(text=f'{item.title}\n{desc}\n(open a bin to edit)')
            return
        if item.kind == 'constant':
            val = decode_constant(self.ws.work, item)
            self.table_info.config(text=f'{item.title}\n{desc}')
            var = tk.StringVar(value=str(val))
            self.cell_vars = [(item, None, None, var)]
            ttk.Entry(self.grid_frame, textvariable=var, width=12).grid(row=0, column=0)
            return
        try:
            d = decode_table(self.ws.work, item)
        except (ValueError, IndexError) as e:
            self.table_info.config(text=f'{item.title}\ncannot decode: {e}')
            return
        if d['z'] is None:
            self.table_info.config(text=f'{item.title}\n(label-only item, no data)')
            return
        self.table_info.config(
            text=f'{item.title}   [{d["rows"]}x{d["cols"]} {d["type"]}]   '
                 f'x: {d["x_units"] or "-"} | y: {d["y_units"] or "-"} | '
                 f'z: {d["z_units"] or "-"}\n{desc}')
        x = d['x'] or ['']
        y = d['y'] or ['']
        for c, xv in enumerate(x[:d['cols']]):
            ttk.Label(self.grid_frame, text=str(xv), font=('', 10, 'bold')
                      ).grid(row=0, column=c + 1, padx=2)
        for r in range(d['rows']):
            yl = y[r] if r < len(y) else r
            ttk.Label(self.grid_frame, text=str(yl), font=('', 10, 'bold')
                      ).grid(row=r + 1, column=0, padx=2, sticky='e')
            for c in range(d['cols']):
                var = tk.StringVar(value=str(d['z'][r][c]))
                self.cell_vars.append((item, r, c, var))
                ttk.Entry(self.grid_frame, textvariable=var, width=8
                          ).grid(row=r + 1, column=c + 1, padx=1, pady=1)

    def _apply_grid(self):
        if self.ws.work is None or not self.cell_vars:
            return
        writes = []
        for item, r, c, var in self.cell_vars:
            try:
                value = float(var.get())
            except ValueError:
                messagebox.showerror('Bad value', f'Not a number: {var.get()!r}')
                return
            if item.kind == 'constant':
                writes.append((item.embedded, 1, 1, 0, 0, value))
            else:
                rows, cols = item.shape()
                writes.append((item.z.embedded, rows, cols, r, c, value))
        n = self.ws.set_cells(f'edit {self.cell_vars[0][0].title}', writes)
        self._set_status(f'{n} cell(s) changed.')
        self._show_selected()

    # -- bulk edit ---------------------------------------------------------
    def _build_bulk_tab(self):
        tab = ttk.Frame(self.tabs, padding=6)
        self.tabs.add(tab, text='Bulk edit')
        ttk.Label(tab, text='Apply one change to every table whose title matches '
                            'the filter (duplicated definitions of the same flash '
                            'bytes are applied once).', wraplength=760,
                  justify='left').pack(anchor='w')
        row = ttk.Frame(tab)
        row.pack(fill='x', pady=4)
        ttk.Label(row, text='Title filter (regex):').pack(side='left')
        self.bulk_pattern = tk.StringVar()
        self.bulk_pattern.trace_add('write', lambda *a: self._bulk_preview())
        ttk.Entry(row, textvariable=self.bulk_pattern, width=40).pack(side='left', padx=4)
        ttk.Label(row, text='Category:').pack(side='left')
        cats = ['(all)'] + [self.ws.xdf.categories[k] for k in sorted(self.ws.xdf.categories)]
        self.bulk_cat = tk.StringVar(value='(all)')
        self.bulk_combo = ttk.Combobox(row, textvariable=self.bulk_cat,
                                       values=cats, state='readonly', width=32)
        self.bulk_combo.pack(side='left')
        self.bulk_combo.bind('<<ComboboxSelected>>', lambda e: self._bulk_preview())

        row2 = ttk.Frame(tab)
        row2.pack(fill='x', pady=4)
        self.bulk_mode = tk.StringVar(value='offset')
        ttk.Radiobutton(row2, text='Offset (+/-)', variable=self.bulk_mode,
                        value='offset', command=self._bulk_preview).pack(side='left')
        ttk.Radiobutton(row2, text='Scale (%)', variable=self.bulk_mode,
                        value='scale', command=self._bulk_preview).pack(side='left', padx=6)
        self.bulk_amount = tk.DoubleVar(value=0)
        self.bulk_scale = ttk.Scale(row2, from_=-1500, to=1500,
                                    variable=self.bulk_amount,
                                    command=lambda v: self._bulk_preview())
        self.bulk_scale.pack(side='left', fill='x', expand=True, padx=8)
        self.bulk_amount_entry = ttk.Entry(row2, width=8)
        self.bulk_amount_entry.pack(side='left')
        self.bulk_amount_entry.insert(0, '0')
        self.bulk_amount_entry.bind('<Return>', self._bulk_amount_typed)

        row3 = ttk.Frame(tab)
        row3.pack(fill='x', pady=2)
        self.bulk_skip = tk.BooleanVar(value=True)
        ttk.Checkbutton(row3, text='Skip sentinel values >=', variable=self.bulk_skip,
                        command=self._bulk_preview).pack(side='left')
        self.bulk_sentinel = tk.StringVar(value=str(SENTINEL_DEFAULT))
        ttk.Entry(row3, textvariable=self.bulk_sentinel, width=8).pack(side='left')

        self.bulk_info = ttk.Label(tab, text='', wraplength=760, justify='left')
        self.bulk_info.pack(anchor='w', pady=4)
        wrap = ttk.Frame(tab)
        wrap.pack(fill='both', expand=True)
        self.bulk_list = tk.Listbox(wrap)
        sb = ttk.Scrollbar(wrap, command=self.bulk_list.yview)
        self.bulk_list.config(yscrollcommand=sb.set)
        self.bulk_list.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')
        ttk.Button(tab, text='Apply to all matched tables',
                   command=self._bulk_apply).pack(anchor='w', pady=4)

    def _bulk_amount_typed(self, _event):
        try:
            self.bulk_amount.set(float(self.bulk_amount_entry.get()))
        except ValueError:
            pass
        self._bulk_preview()

    def _bulk_matches(self):
        pat = self.bulk_pattern.get().strip()
        cat = self.bulk_cat.get()
        if not pat and cat == '(all)':
            return []
        try:
            rx = re.compile(pat, re.I) if pat else None
        except re.error:
            return []
        out, seen = [], set()
        for t in self.ws.xdf.tables:
            emb = t.z.embedded if t.z else None
            if not emb or emb.address is None or emb.address in seen:
                continue
            if rx and not rx.search(t.title):
                continue
            if cat != '(all)' and cat not in t.categories:
                continue
            seen.add(emb.address)
            out.append(t)
        return out

    def _bulk_op(self, value):
        amount = self.bulk_amount.get()
        if self.bulk_mode.get() == 'scale':
            return value * (1 + amount / 100.0)
        return value + amount

    def _bulk_preview(self):
        matches = self._bulk_matches()
        self.bulk_list.delete(0, 'end')
        for t in matches[:400]:
            self.bulk_list.insert('end', t.title)
        amount = self.bulk_amount.get()
        unit = '%' if self.bulk_mode.get() == 'scale' else ''
        sync = f'{amount:+.1f}{unit}'
        self.bulk_amount_entry.delete(0, 'end')
        self.bulk_amount_entry.insert(0, f'{amount:.1f}')
        if self.ws.work is None:
            self.bulk_info.config(text=f'{len(matches)} tables matched. '
                                       'Open a bin to preview values.')
            return
        example = ''
        if matches:
            try:
                d = decode_table(self.ws.work, matches[0])
                if d['z']:
                    v = d['z'][0][0]
                    example = (f'   example: {matches[0].title} [0,0] '
                               f'{v} -> {self._bulk_op(v):.0f}')
            except (ValueError, IndexError):
                pass
        self.bulk_info.config(text=f'{len(matches)} tables matched, change {sync}.{example}')

    def _bulk_apply(self):
        if self.ws.work is None:
            messagebox.showinfo('No bin', 'Open a bin first.')
            return
        matches = self._bulk_matches()
        if not matches:
            return
        try:
            sentinel = float(self.bulk_sentinel.get())
        except ValueError:
            sentinel = SENTINEL_DEFAULT
        writes = []
        for t in matches:
            rows, cols = t.shape()
            emb = t.z.embedded
            try:
                d = decode_table(self.ws.work, t)
            except (ValueError, IndexError):
                continue
            for r in range(rows):
                for c in range(cols):
                    v = d['z'][r][c]
                    if self.bulk_skip.get() and v >= sentinel:
                        continue
                    writes.append((emb, rows, cols, r, c, self._bulk_op(v)))
        n = self.ws.set_cells(
            f'bulk {self.bulk_mode.get()} {self.bulk_amount.get():+.1f} '
            f'on {len(matches)} tables', writes)
        self._set_status(f'Bulk edit: {n} cell(s) changed across '
                         f'{len(matches)} tables.')
        self._show_selected()

    # -- shift speed preset -------------------------------------------------
    def _mode_radio_row(self, parent, var, command=None):
        """All/Normal/Sport radio row; groups are assigned in the Modes tab."""
        row = ttk.Frame(parent)
        row.pack(fill='x', pady=2)
        ttk.Label(row, text='Drive mode:').pack(side='left')
        for text, val in (('All', 'all'), ('Normal', 'normal'),
                          ('Sport', 'sport')):
            ttk.Radiobutton(row, text=text, variable=var, value=val,
                            command=command).pack(side='left', padx=2)
        ttk.Label(row, text='(assign characteristics in the Modes tab)'
                  ).pack(side='left', padx=8)
        return row

    def _build_shift_tab(self):
        tab = ttk.Frame(self.tabs, padding=6)
        self.tabs.add(tab, text='Shift speed')
        ttk.Label(tab, text=(
            'Move the shift schedule as one unit: the slider adds output-shaft '
            'rpm to every selected upshift line across the selected '
            'characteristics. Positive = shifts happen later (higher rpm). '
            '8000-rpm "disabled" sentinels are never touched. Keep "move '
            'downshift lines too" on to preserve the up/down hysteresis.'),
            wraplength=760, justify='left').pack(anchor='w')

        row = ttk.Frame(tab)
        row.pack(fill='x', pady=8)
        ttk.Label(row, text='Shift point offset (rpm):').pack(side='left')
        self.shift_amount = tk.DoubleVar(value=0)
        ttk.Scale(row, from_=-1500, to=1500, variable=self.shift_amount,
                  command=lambda v: self._shift_preview()).pack(
            side='left', fill='x', expand=True, padx=8)
        self.shift_label = ttk.Label(row, text='+0 rpm', width=10)
        self.shift_label.pack(side='left')

        gp = ttk.LabelFrame(tab, text='Gear pairs', padding=4)
        gp.pack(fill='x', pady=4)
        self.pair_vars = {}
        for k, pair in enumerate(GEAR_PAIRS):
            var = tk.BooleanVar(value=True)
            self.pair_vars[pair] = var
            ttk.Checkbutton(gp, text=pair, variable=var,
                            command=self._shift_preview).grid(row=0, column=k, padx=4)

        ch = ttk.LabelFrame(tab, text='Characteristics (shift programs)', padding=4)
        ch.pack(fill='x', pady=4)
        self.char_vars = {}
        for n in range(23):
            var = tk.BooleanVar(value=True)
            self.char_vars[n] = var
            ttk.Checkbutton(ch, text=f'{n:02d}', variable=var,
                            command=self._shift_preview).grid(
                row=n // 12, column=n % 12, padx=2)

        self.shift_mode = tk.StringVar(value='all')
        self._mode_radio_row(tab, self.shift_mode, self._shift_preview)

        self.shift_down = tk.BooleanVar(value=True)
        ttk.Checkbutton(tab, text='Move matching downshift lines too '
                                  '(preserves hysteresis)',
                        variable=self.shift_down,
                        command=self._shift_preview).pack(anchor='w')
        self.shift_info = ttk.Label(tab, text='', wraplength=760, justify='left')
        self.shift_info.pack(anchor='w', pady=6)
        ttk.Button(tab, text='Apply shift offset',
                   command=self._shift_apply).pack(anchor='w')

    def _shift_chars(self):
        """Checked characteristics intersected with the drive-mode radio."""
        chars = {n for n, v in self.char_vars.items() if v.get()}
        mode_set, err = mode_chars(self.ws.xdf.path, self.shift_mode.get())
        if err:
            return None, err
        return chars if mode_set is None else chars & mode_set, None

    def _shift_preview(self):
        amount = self.shift_amount.get()
        self.shift_label.config(text=f'{amount:+.0f} rpm')
        chars, err = self._shift_chars()
        if err:
            self.shift_info.config(text=err)
            return
        pairs = {p for p, v in self.pair_vars.items() if v.get()}
        kinds = ('up', 'down') if self.shift_down.get() else ('up',)
        curves = xdf_tune.shift_curves(self.ws.xdf, kinds, pairs, chars)
        up = sum(1 for _t, k, _ch, _p in curves if k == 'up')
        down = len(curves) - up
        self.shift_info.config(
            text=f'{up} upshift lines'
                 + (f' + {down} downshift lines' if self.shift_down.get() else '')
                 + f' selected ({len(curves)} curves x 15 pedal points). '
                   f'Offset {amount:+.0f} rpm.')

    def _shift_apply(self):
        if self.ws.work is None:
            messagebox.showinfo('No bin', 'Open a bin first.')
            return
        amount = self.shift_amount.get()
        if not amount:
            return
        chars, err = self._shift_chars()
        if err:
            messagebox.showerror('Sport chars not assigned', err)
            return
        pairs = {p for p, v in self.pair_vars.items() if v.get()}
        writes, curves = shift_offset_writes(self.ws, amount, pairs, chars,
                                             self.shift_down.get())
        n = self.ws.set_cells(f'shift speed {amount:+.0f} rpm ({curves} lines, '
                              f'{self.shift_mode.get()} mode)', writes)
        self._set_status(f'Shift offset applied: {n} cell(s) across '
                         f'{curves} lines. Sentinels untouched.')
        self._show_selected()

    # -- NA presets ----------------------------------------------------------
    QUICK_RX = re.compile(
        r'(ph\d+_time|sync_time|phase.*time|_time_|rampout)', re.I)
    EXEC_CATS = ('Shift execution: upshift', 'Shift execution: downshift',
                 'Shift execution: timing control', 'Shift execution: other')

    def _build_na_tab(self):
        tab = ttk.Frame(self.tabs, padding=6)
        self.tabs.add(tab, text='NA presets')

        # --- shift quickness ------------------------------------------------
        q = ttk.LabelFrame(tab, text='Shift quickness', padding=6)
        q.pack(fill='x', pady=4)
        ttk.Label(q, text=(
            'Shortens the documented shift-execution phase/sync time tables '
            '(u8 control-cycle counts) by a percentage, so shifts complete '
            'faster. Firmer feel, more clutch heat per shift; change in small '
            'steps and let adaptation settle between changes.'),
            wraplength=740, justify='left').pack(anchor='w')
        ttk.Label(q, text=(
            'Applies to all drive modes - the 8HP uses shared execution-time '
            'tables (K1/K2 are clutches, not programs).'),
            wraplength=740, justify='left').pack(anchor='w')
        row = ttk.Frame(q)
        row.pack(fill='x', pady=2)
        ttk.Label(row, text='Faster by:').pack(side='left')
        self.quick_amount = tk.DoubleVar(value=0)
        ttk.Scale(row, from_=0, to=40, variable=self.quick_amount,
                  command=lambda v: self._quick_preview()).pack(
            side='left', fill='x', expand=True, padx=8)
        self.quick_label = ttk.Label(row, text='0 %', width=18)
        self.quick_label.pack(side='left')
        ttk.Button(q, text='Apply quickness',
                   command=self._quick_apply).pack(anchor='w', pady=2)

        # --- hold 1st-3rd to redline -----------------------------------------
        r = ttk.LabelFrame(tab, text='Hold 1st-3rd to redline', padding=6)
        r.pack(fill='x', pady=4)
        ttk.Label(r, text=(
            'Raises the 1>2, 2>3 and 3>4 upshift lines (characteristics per '
            'the drive-mode radio below) so those gears run to redline before '
            'upshifting. Shift lines are OUTPUT-shaft rpm, so the target per '
            'gear is redline / gear ratio (ratios editable below; defaults '
            'are 8HP45). Values only ever get raised (never lowered), 8000 '
            'sentinels stay, downshift lines are untouched. The TCU-side '
            'guard tests start at ~7100 rpm stock - keep redline below that '
            'or apply the True manual patch first.'),
            wraplength=740, justify='left').pack(anchor='w')
        row2 = ttk.Frame(r)
        row2.pack(fill='x', pady=2)
        self.redline_var = tk.StringVar(value='7000')
        self.margin_var = tk.StringVar(value='2')
        self.ratio_vars = {}
        ttk.Label(row2, text='Engine redline:').pack(side='left')
        ttk.Entry(row2, textvariable=self.redline_var, width=6).pack(side='left')
        ttk.Label(row2, text='rpm   margin:').pack(side='left')
        ttk.Entry(row2, textvariable=self.margin_var, width=4).pack(side='left')
        ttk.Label(row2, text='%   ratios:').pack(side='left')
        for gear, default in (('1st', '4.714'), ('2nd', '3.143'), ('3rd', '2.106')):
            ttk.Label(row2, text=f' {gear}').pack(side='left')
            var = tk.StringVar(value=default)
            self.ratio_vars[gear] = var
            ttk.Entry(row2, textvariable=var, width=6).pack(side='left')
        self.redline_mode = tk.StringVar(value='all')
        self._mode_radio_row(r, self.redline_mode)
        self.redline_info = ttk.Label(r, text='', wraplength=740, justify='left')
        self.redline_info.pack(anchor='w')
        ttk.Button(r, text='Apply redline hold',
                   command=self._redline_apply).pack(anchor='w', pady=2)

        # --- early upshift (NA) ----------------------------------------------
        e = ttk.LabelFrame(tab, text='Early upshift (NA)', padding=6)
        e.pack(fill='x', pady=4)
        ttk.Label(e, text=(
            'An NA engine has instant response, so part-throttle upshifts can '
            'come earlier: this lowers every upshift line (all gear pairs, '
            'characteristics per the drive-mode radio) by up to the slider '
            'amount, weighted by '
            'pedal - full effect at closed throttle, fading to zero at 80% '
            'pedal, kickdown untouched. Each point is clamped to stay at '
            'least 100 rpm above its matching downshift line so the box '
            'cannot hunt. 8000 sentinels stay.'),
            wraplength=740, justify='left').pack(anchor='w')
        row3 = ttk.Frame(e)
        row3.pack(fill='x', pady=2)
        ttk.Label(row3, text='Earlier by (at closed throttle):').pack(side='left')
        self.early_amount = tk.DoubleVar(value=0)
        ttk.Scale(row3, from_=0, to=800, variable=self.early_amount,
                  command=lambda v: self._early_preview()).pack(
            side='left', fill='x', expand=True, padx=8)
        self.early_label = ttk.Label(row3, text='0 rpm', width=18)
        self.early_label.pack(side='left')
        self.early_mode = tk.StringVar(value='all')
        self._mode_radio_row(e, self.early_mode)
        ttk.Button(e, text='Apply early upshift',
                   command=self._early_apply).pack(anchor='w', pady=2)

        self.na_info = ttk.Label(tab, text='', wraplength=740, justify='left')
        self.na_info.pack(anchor='w', pady=4)

    def _quick_targets(self):
        out, seen = [], set()
        for t in self.ws.xdf.tables:
            emb = t.z.embedded if t.z else None
            if not emb or emb.address is None or emb.address in seen:
                continue
            if emb.elem_bits != 8 or emb.is_float:
                continue
            if not any(c in self.EXEC_CATS for c in t.categories):
                continue
            if not self.QUICK_RX.search(t.title):
                continue
            seen.add(emb.address)
            out.append(t)
        return out

    def _quick_preview(self):
        n = len(self._quick_targets())
        self.quick_label.config(
            text=f'{self.quick_amount.get():.0f} % ({n} tables)')

    def _quick_apply(self):
        if self.ws.work is None:
            messagebox.showinfo('No bin', 'Open a bin first.')
            return
        pct = self.quick_amount.get()
        if not pct:
            return
        factor = 1 - pct / 100.0
        writes = []
        for t in self._quick_targets():
            rows, cols = t.shape()
            emb = t.z.embedded
            try:
                d = decode_table(self.ws.work, t)
            except (ValueError, IndexError):
                continue
            for r in range(rows):
                for c in range(cols):
                    v = d['z'][r][c]
                    if v <= 0 or v >= 250:          # zero/disabled or sentinel
                        continue
                    writes.append((emb, rows, cols, r, c, max(1, round(v * factor))))
        n = self.ws.set_cells(f'shift quickness -{pct:.0f}%', writes)
        self.na_info.config(text=f'Quickness: {n} time cells shortened by '
                                 f'{pct:.0f}% (floor 1 cycle).')
        self._show_selected()

    def _redline_apply(self):
        if self.ws.work is None:
            messagebox.showinfo('No bin', 'Open a bin first.')
            return
        try:
            redline = float(self.redline_var.get())
            margin = float(self.margin_var.get()) / 100.0
            ratios = {'1>2': float(self.ratio_vars['1st'].get()),
                      '2>3': float(self.ratio_vars['2nd'].get()),
                      '3>4': float(self.ratio_vars['3rd'].get())}
        except ValueError:
            messagebox.showerror('Bad value', 'Redline, margin and ratios must be numbers.')
            return
        chars, err = mode_chars(self.ws.xdf.path, self.redline_mode.get())
        if err:
            messagebox.showerror('Sport chars not assigned', err)
            return
        targets = {pair: round(redline * (1 - margin) / ratio)
                   for pair, ratio in ratios.items()}
        writes, counts = redline_hold_writes(self.ws, targets, chars)
        n = self.ws.set_cells(
            f'redline hold 1st-3rd @{redline:.0f}rpm '
            f'({self.redline_mode.get()} mode)', writes)
        self.redline_info.config(
            text='Targets (output rpm): '
                 + ', '.join(f'{p}: {v}' for p, v in targets.items())
                 + f' - raised {n} cells '
                 + str({p: c for p, c in counts.items()}))
        self._show_selected()

    def _early_preview(self):
        self.early_label.config(text=f'{self.early_amount.get():.0f} rpm')

    def _early_apply(self):
        if self.ws.work is None:
            messagebox.showinfo('No bin', 'Open a bin first.')
            return
        amount = self.early_amount.get()
        if not amount:
            return
        chars, err = mode_chars(self.ws.xdf.path, self.early_mode.get())
        if err:
            messagebox.showerror('Sport chars not assigned', err)
            return
        writes, clamped = early_upshift_writes(self.ws, amount, chars)
        n = self.ws.set_cells(f'early upshift -{amount:.0f}rpm (pedal-weighted, '
                              f'{self.early_mode.get()} mode)', writes)
        self.na_info.config(
            text=f'Early upshift: {n} cells lowered (pedal-weighted, '
                 f'{clamped} clamped to downshift line + 100 rpm).')
        self._show_selected()

    # -- TCC lockup ----------------------------------------------------------
    def _build_tcc_tab(self):
        tab = ttk.Frame(self.tabs, padding=6)
        self.tabs.add(tab, text='TCC lockup')
        ttk.Label(tab, text=(
            'Lockup speed: scales the converter close time DOWN and the '
            'close-pressure ramp rate UP by the slider amount, and the close '
            'pressure UP by half of it, so the lockup clutch applies faster '
            'around shifts. These maps are GLOBAL - they apply to all drive '
            'modes; mode-specific lockup lives in strategy tables that need '
            'a full flash read. Table identification is MED/LOW confidence '
            'from the decompile: change in small steps, reset TCC adaptation '
            'after flashing, and watch for low-rpm shudder.'),
            wraplength=760, justify='left').pack(anchor='w')
        row = ttk.Frame(tab)
        row.pack(fill='x', pady=8)
        ttk.Label(row, text='Lockup speed:').pack(side='left')
        self.tcc_amount = tk.DoubleVar(value=0)
        ttk.Scale(row, from_=0, to=40, variable=self.tcc_amount,
                  command=lambda v: self._tcc_slider()).pack(
            side='left', fill='x', expand=True, padx=8)
        self.tcc_label = ttk.Label(row, text='0 %', width=24)
        self.tcc_label.pack(side='left')
        btns = ttk.Frame(tab)
        btns.pack(fill='x', pady=2)
        ttk.Button(btns, text='Preview', command=self._tcc_preview).pack(side='left')
        ttk.Button(btns, text='Apply TCC lockup',
                   command=self._tcc_apply).pack(side='left', padx=4)
        self.tcc_info = ttk.Label(tab, text='', wraplength=760, justify='left')
        self.tcc_info.pack(anchor='w', pady=4)

    def _tcc_slider(self):
        pct = self.tcc_amount.get()
        self.tcc_label.config(text=f'{pct:.0f} % (pressure +{pct / 2:.0f} %)')

    def _tcc_preview(self):
        if self.ws.work is None:
            messagebox.showinfo('No bin', 'Open a bin first.')
            return
        writes, done = tcc_lockshift_writes(self.ws, self.tcc_amount.get())
        if not done:
            self.tcc_info.config(text='Nothing to change: slider at 0 %, or '
                                      'none of the TCC tables are in this XDF.')
            return
        self.tcc_info.config(
            text='Preview (nothing written):\n' + '\n'.join(
                f'  {title}: {p:+.1f}% on {n}/{cells} cells'
                for title, p, n, cells in done)
            + f'\n{len(done)} of 4 target tables in this XDF, '
              f'{len(writes)} cells would change.')

    def _tcc_apply(self):
        if self.ws.work is None:
            messagebox.showinfo('No bin', 'Open a bin first.')
            return
        pct = self.tcc_amount.get()
        if not pct:
            return
        writes, done = tcc_lockshift_writes(self.ws, pct)
        n = self.ws.set_cells(f'TCC lockup {pct:.0f}%', writes)
        self.tcc_info.config(
            text=f'Applied {pct:.0f}%: {n} cells changed ('
                 + ', '.join(f'{t} {p:+.1f}%' for t, p, _n, _c in done)
                 + '). Global - all drive modes. Reset TCC adaptation after '
                   'flashing.')
        self._show_selected()

    # -- drive-mode assignment -----------------------------------------------
    def _build_modes_tab(self):
        tab = ttk.Frame(self.tabs, padding=6)
        self.tabs.add(tab, text='Modes')
        ttk.Label(tab, text=(
            'Assign shift characteristics to drive modes. The char-to-mode '
            'mapping (which characteristic the Sport program selects) lives '
            'in the program ROM, not in this calibration read, so it cannot '
            'be recovered here: identify the Sport chars by logging while '
            'toggling modes, then select them below and toggle. Everything '
            'not Sport counts as Normal. Save writes e84_modes.json next to '
            'the XDF - the Normal/Sport radios on the other tabs and '
            'xdf_tune --mode read that file.'),
            wraplength=760, justify='left').pack(anchor='w')
        wrap = ttk.Frame(tab)
        wrap.pack(fill='both', expand=True, pady=4)
        self.modes_list = tk.Listbox(wrap, selectmode='extended',
                                     exportselection=False)
        sb = ttk.Scrollbar(wrap, command=self.modes_list.yview)
        self.modes_list.config(yscrollcommand=sb.set)
        self.modes_list.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')
        self.modes_list.bind('<Double-Button-1>', lambda e: self._modes_toggle())
        btns = ttk.Frame(tab)
        btns.pack(fill='x', pady=4)
        ttk.Button(btns, text='Toggle Sport/Normal',
                   command=self._modes_toggle).pack(side='left')
        ttk.Button(btns, text='Save assignment',
                   command=self._modes_save).pack(side='left', padx=4)
        self.modes_info = ttk.Label(tab, text='', wraplength=760, justify='left')
        self.modes_info.pack(anchor='w')
        self._modes_refresh()

    def _modes_refresh(self):
        """(Re)load the saved mode groups for the current XDF into the list."""
        if not hasattr(self, 'modes_list'):
            return
        self.modes_chars = xdf_shift_chars(self.ws.xdf)
        try:
            sport = load_mode_groups(self.ws.xdf.path)['sport']
        except (OSError, ValueError):
            sport = set()
        self.mode_sport = sport & set(self.modes_chars)
        self._modes_fill()

    def _modes_fill(self):
        sel = self.modes_list.curselection()
        self.modes_list.delete(0, 'end')
        for n in self.modes_chars:
            tag = 'SPORT' if n in self.mode_sport else 'normal'
            self.modes_list.insert('end', f'char {n:02d}   {tag}')
        for i in sel:
            self.modes_list.selection_set(i)
        try:
            saved = load_mode_groups(self.ws.xdf.path)['sport'] == self.mode_sport
        except (OSError, ValueError):
            saved = False
        self.modes_info.config(
            text=f'{len(self.modes_chars) - len(self.mode_sport)} normal / '
                 f'{len(self.mode_sport)} sport'
                 + ('.' if saved else '  -  UNSAVED, press Save to make the '
                                      'Normal/Sport filters see it.'))

    def _modes_toggle(self):
        for i in self.modes_list.curselection():
            self.mode_sport.symmetric_difference_update({self.modes_chars[i]})
        self._modes_fill()

    def _modes_save(self):
        path = save_mode_groups(
            self.ws.xdf.path,
            {'sport': self.mode_sport,
             'normal': set(self.modes_chars) - self.mode_sport})
        self._modes_fill()
        self._set_status(f'Mode groups saved to {path} '
                         f'({len(self.mode_sport)} sport chars).')

    # -- vehicle (wheel / diff / converter) -----------------------------------
    def _build_vehicle_tab(self):
        import xdf_tune
        self._tune = xdf_tune
        tab = ttk.Frame(self.tabs, padding=6)
        self.tabs.add(tab, text='Vehicle')

        w = ttk.LabelFrame(tab, text='Wheel circumference (Radumfang)', padding=6)
        w.pack(fill='x', pady=4)
        ttk.Label(w, text=(
            'The dynamic ROLLING circumference the TCU uses to learn the axle '
            'ratio. Enter mm directly, or a tire size to calculate it '
            '(pi x (rim x 25.4 + 2 x width x profile%) x 0.97).'),
            wraplength=740, justify='left').pack(anchor='w')
        row = ttk.Frame(w)
        row.pack(fill='x', pady=2)
        self.wheel_current = ttk.Label(row, text='current: (open a bin)')
        self.wheel_current.pack(side='left')
        ttk.Label(row, text='   tire:').pack(side='left')
        self.tire_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.tire_var, width=12).pack(side='left')
        ttk.Button(row, text='Calc', command=self._tire_calc).pack(side='left', padx=2)
        ttk.Label(row, text='mm:').pack(side='left')
        self.wheel_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.wheel_var, width=7).pack(side='left')
        ttk.Button(row, text='Set', command=self._wheel_set).pack(side='left', padx=4)

        d = ttk.LabelFrame(tab, text='Diff ratio (learned, not programmed)', padding=6)
        d.pack(fill='x', pady=4)
        ttk.Label(d, text=(
            'The TCU LEARNS the rear-axle ratio and snaps it to a fixed list - '
            'there is no stored diff-ratio byte to edit. Enter your real diff '
            'ratio (and, after driving, the learned value from Tool32 '
            'status_lernfkt): this checks the landing and can trim the '
            'circumference so learning comes out right.'),
            wraplength=740, justify='left').pack(anchor='w')
        row2 = ttk.Frame(d)
        row2.pack(fill='x', pady=2)
        ttk.Label(row2, text='real ratio:').pack(side='left')
        self.diff_var = tk.StringVar()
        ttk.Entry(row2, textvariable=self.diff_var, width=7).pack(side='left')
        ttk.Label(row2, text='learned (optional):').pack(side='left')
        self.learned_var = tk.StringVar()
        ttk.Entry(row2, textvariable=self.learned_var, width=7).pack(side='left')
        ttk.Button(row2, text='Check', command=self._diff_check).pack(side='left', padx=4)
        ttk.Button(row2, text='Apply suggested circumference',
                   command=self._diff_fix).pack(side='left')
        self.diff_info = ttk.Label(d, text='', wraplength=740, justify='left')
        self.diff_info.pack(anchor='w')

        c = ttk.LabelFrame(tab, text='Torque converter model (N20 / N55 donor)', padding=6)
        c.pack(fill='x', pady=4)
        ttk.Label(c, text=(
            'The converter-specific plant model is tcmodel_K_curve / '
            'tcmodel_mu_curve (HIGH confidence). This E70 calibration was '
            'matched to its original converter; an N20-spec converter is a '
            'higher-slip, lag-masking design, an N55 unit is tighter. Real '
            'K/mu values must come from a factory calibration for that '
            'converter: pick a donor read (+ the XDF that matches the donor '
            'if it is a different ZB) and import. After importing, reset TCC '
            'adaptation and re-log (see docs/analysis/n52k-tcc-optimization.md).'),
            wraplength=740, justify='left').pack(anchor='w')
        row3 = ttk.Frame(c)
        row3.pack(fill='x', pady=2)
        ttk.Button(row3, text='Pick donor bin…', command=self._pick_donor).pack(side='left')
        ttk.Button(row3, text='Donor XDF (optional)…',
                   command=self._pick_donor_xdf).pack(side='left', padx=4)
        ttk.Button(row3, text='Import K/mu from donor',
                   command=self._import_converter).pack(side='left')
        self.donor_info = ttk.Label(c, text='donor: (none)', wraplength=740,
                                    justify='left')
        self.donor_info.pack(anchor='w')
        self._donor_bin = self._donor_xdf = None

    def _wheel_refresh(self):
        if self.ws.work is None:
            return
        try:
            const = self._tune.find_constant(self.ws.xdf, 'Radumfang')
            val = decode_constant(self.ws.work, const)
            self.wheel_current.config(text=f'current: {val} mm')
        except SystemExit:
            self.wheel_current.config(text='current: (no Radumfang item in this XDF)')

    def _tire_calc(self):
        try:
            mm = self._tune.tire_circumference(self.tire_var.get())
        except ValueError as e:
            messagebox.showerror('Tire size', str(e))
            return
        self.wheel_var.set(str(round(mm)))

    def _wheel_set(self):
        if self.ws.work is None:
            messagebox.showinfo('No bin', 'Open a bin first.')
            return
        try:
            mm = float(self.wheel_var.get())
        except ValueError:
            messagebox.showerror('Bad value', 'Circumference must be a number (mm).')
            return
        const = self._tune.find_constant(self.ws.xdf, 'Radumfang')
        self.ws.set_cells(f'wheel circumference {mm:.0f} mm',
                          [(const.embedded, 1, 1, 0, 0, mm)])
        self._wheel_refresh()
        self._set_status(f'Wheel circumference set to {mm:.0f} mm. After '
                         'flashing: reset the learned axle value and re-learn.')

    def _diff_check(self):
        if self.ws.work is None:
            messagebox.showinfo('No bin', 'Open a bin first.')
            return
        try:
            ratio = float(self.diff_var.get())
            learned = float(self.learned_var.get()) if self.learned_var.get() else None
        except ValueError:
            messagebox.showerror('Bad value', 'Ratios must be numbers.')
            return
        const = self._tune.find_constant(self.ws.xdf, 'Radumfang')
        circ = decode_constant(self.ws.work, const)
        lines, suggestion = self._tune.diff_report(ratio, learned, circ)
        self._diff_suggestion = suggestion
        self.diff_info.config(text='\n'.join(lines))

    def _diff_fix(self):
        if getattr(self, '_diff_suggestion', None) is None:
            messagebox.showinfo('Nothing to apply',
                                'Run Check with both ratios first - a suggestion '
                                'only exists when learned differs from real.')
            return
        self.wheel_var.set(str(round(self._diff_suggestion)))
        self._wheel_set()

    def _pick_donor(self):
        path = filedialog.askopenfilename(title='Donor calibration read',
                                          filetypes=[('Bin files', '*.bin'),
                                                     ('All files', '*')])
        if path:
            self._donor_bin = path
            self.donor_info.config(text=f'donor: {path}'
                                   + (f' | XDF: {self._donor_xdf}'
                                      if self._donor_xdf else ' | XDF: same as target'))

    def _pick_donor_xdf(self):
        path = filedialog.askopenfilename(title='XDF matching the donor',
                                          filetypes=[('XDF files', '*.xdf'),
                                                     ('All files', '*')])
        if path:
            self._donor_xdf = path
            self._pick_donor_refresh()

    def _pick_donor_refresh(self):
        self.donor_info.config(text=f'donor: {self._donor_bin or "(none)"} | '
                               f'XDF: {self._donor_xdf or "same as target"}')

    def _import_converter(self):
        if self.ws.work is None or not self._donor_bin:
            messagebox.showinfo('Missing input', 'Open a bin and pick a donor first.')
            return
        try:
            donor_xdf = XDF(self._donor_xdf) if self._donor_xdf else self.ws.xdf
            donor = bytearray(open(self._donor_bin, 'rb').read())
            before = bytes(self.ws.work)
            copied = self._tune.op_copy_tables(
                self.ws.work, self.ws.xdf, donor, donor_xdf,
                ['tcmodel_K_curve', 'tcmodel_mu_curve'])
        except (OSError, ValueError) as e:
            messagebox.showerror('Import failed', str(e))
            return
        # fold the byte changes into the undo stack
        patch = [(i, before[i:i + 1], bytes(self.ws.work[i:i + 1]))
                 for i in range(len(before)) if before[i] != self.ws.work[i]]
        if patch:
            self.ws.undo_stack.append(('import converter K/mu from donor', patch))
        self._set_status('Imported ' + ', '.join(f'{t} ({n} cells)'
                                                 for t, n in copied)
                         + ' - reset TCC adaptation after flashing.')
        self._refresh_changes()

    # -- sign / flash --------------------------------------------------------
    def _sign_bin(self):
        """Recompute and store the calibration checksum using the profile
        produced by xdf_checksum.py search (clean-room; see tools/README)."""
        if self.ws.work is None:
            messagebox.showinfo('No bin', 'Open a bin first.')
            return
        try:
            import xdf_checksum
        except ImportError:
            messagebox.showerror('Missing', 'xdf_checksum.py not found next to the GUI.')
            return
        profile = xdf_checksum.load_profile()
        if profile is None:
            messagebox.showinfo(
                'No checksum profile yet',
                'The checksum algorithm must be confirmed once against YOUR '
                'stock read before signing can be trusted:\n\n'
                '  python3 xdf_checksum.py search your_stock_read.bin\n\n'
                'That finds the algorithm/region whose checksum matches the '
                'value already stored in a known-good bin and saves it to '
                'checksum_profile.json. After that, this button signs '
                'in one click.')
            return
        try:
            old, new = xdf_checksum.sign(self.ws.work, profile)
        except (ValueError, KeyError) as e:
            messagebox.showerror('Sign failed', str(e))
            return
        self._set_status(f'Signed: stored checksum 0x{old:08X} -> 0x{new:08X} '
                         f'({profile["algo"]} over 0x{profile["start"]:X}-'
                         f'0x{profile["end"]:X}).')
        self._refresh_changes()

    def _flash_info(self):
        messagebox.showinfo(
            'Flashing',
            'Flashing from this GUI is not enabled: the write path has not '
            'been validated on real hardware, and an unverified TCU flash '
            'can brick the transmission.\n\n'
            'Validated flow:\n'
            '  1. Edit here, Sign bin (or let your flash tool correct '
            'checksums), Save bin as…\n'
            '  2. Flash the saved 2 MB image with 8HPe Transmission '
            'Quickflash (FT232RL / K+DCAN cable) or your usual EGS flasher.\n'
            '  3. After a wheel-circumference or diff change: reset the '
            'learned axle ratio (Tool32 gsb233.prg, '
            'steuern_lernfkt_ruecksetzen 0) and re-learn by driving.\n\n'
            'See docs/analysis/quickflash-interop.md for the protocol notes.')

    # -- changes ------------------------------------------------------------
    def _build_changes_tab(self):
        tab = ttk.Frame(self.tabs, padding=6)
        self.tabs.add(tab, text='Changes')
        ttk.Label(tab, text='Items whose bytes differ from the loaded '
                            'original.').pack(anchor='w')
        wrap = ttk.Frame(tab)
        wrap.pack(fill='both', expand=True)
        self.changes_list = tk.Listbox(wrap)
        sb = ttk.Scrollbar(wrap, command=self.changes_list.yview)
        self.changes_list.config(yscrollcommand=sb.set)
        self.changes_list.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')
        btns = ttk.Frame(tab)
        btns.pack(fill='x', pady=4)
        ttk.Button(btns, text='Refresh', command=self._refresh_changes).pack(side='left')
        ttk.Button(btns, text='Revert selected',
                   command=self._revert_selected).pack(side='left', padx=4)

    def _refresh_changes(self):
        if not hasattr(self, 'changes_list') or self.ws.work is None:
            return
        self.changed = self.ws.changed_items()
        self.changes_list.delete(0, 'end')
        for item, n in self.changed:
            self.changes_list.insert('end', f'{item.title}  ({n} cells)')

    def _revert_selected(self):
        sel = self.changes_list.curselection()
        if not sel:
            return
        item, _n = self.changed[sel[0]]
        self.ws.revert_item(item)
        self._refresh_changes()
        self._show_selected()


def main():
    xdf_path = sys.argv[1] if len(sys.argv) > 1 else next(
        (c for c in ('../8hpe84_cali_v1.xdf', '../8hpe70_cali_v3.xdf',
                     '../8hpe_cali_v3.xdf') if os.path.exists(c)),
        '../8hpe84_cali_v1.xdf')
    bin_path = sys.argv[2] if len(sys.argv) > 2 else None
    App(xdf_path, bin_path).mainloop()


if __name__ == '__main__':
    main()
