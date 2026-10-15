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
  * Undo stack, change list vs. the loaded original, save-as (never in place).

Checksums are NOT corrected - run the saved bin through your checksum flow
(8HPe Quickflash corrects at flash time).
"""
import re
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from xdflib import (XDF, decode_axis, decode_constant, decode_table,
                    element_offset, load_bin, write_elem)

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
        ttk.Button(bar, text='Open bin…', command=self._open_bin).pack(side='left')
        ttk.Button(bar, text='Save bin as…', command=self._save_bin).pack(side='left', padx=4)
        ttk.Button(bar, text='Undo', command=self._undo).pack(side='left')
        self.status = ttk.Label(bar, text='', anchor='w')
        self.status.pack(side='left', fill='x', expand=True, padx=12)

    def _set_status(self, text):
        self.status.config(text=text)

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
        cb = ttk.Combobox(frame, textvariable=self.cat_var, values=cats,
                          state='readonly')
        cb.pack(fill='x', pady=2)
        cb.bind('<<ComboboxSelected>>', lambda e: self._refresh_list())
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
        self._build_changes_tab()
        self.tabs.bind('<<NotebookTabChanged>>', lambda e: self._refresh_changes())

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
        cb = ttk.Combobox(row, textvariable=self.bulk_cat, values=cats,
                          state='readonly', width=32)
        cb.pack(side='left')
        cb.bind('<<ComboboxSelected>>', lambda e: self._bulk_preview())

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

        self.shift_down = tk.BooleanVar(value=True)
        ttk.Checkbutton(tab, text='Move matching downshift lines too '
                                  '(preserves hysteresis)',
                        variable=self.shift_down,
                        command=self._shift_preview).pack(anchor='w')
        self.shift_info = ttk.Label(tab, text='', wraplength=760, justify='left')
        self.shift_info.pack(anchor='w', pady=6)
        ttk.Button(tab, text='Apply shift offset',
                   command=self._shift_apply).pack(anchor='w')

    def _shift_curves(self):
        """Deduped per-gear-pair shift-line curves matching the selection."""
        chars = {n for n, v in self.char_vars.items() if v.get()}
        pairs = {p for p, v in self.pair_vars.items() if v.get()}
        up, down, seen = [], [], set()
        for t in self.ws.xdf.tables:
            emb = t.z.embedded if t.z else None
            if not emb or emb.address is None or emb.address in seen:
                continue
            m = UP_CURVE.match(t.title)
            kind = 'up'
            if not m:
                m = DN_CURVE.match(t.title)
                kind = 'down'
            if not m:
                continue
            char = int(m.group(1))
            lo, hi = sorted((m.group(2), m.group(3)))
            pair = f'{lo}>{hi}'
            if char not in chars or pair not in pairs:
                continue
            seen.add(emb.address)
            (up if kind == 'up' else down).append(t)
        return up, down

    def _shift_preview(self):
        amount = self.shift_amount.get()
        self.shift_label.config(text=f'{amount:+.0f} rpm')
        up, down = self._shift_curves()
        n = len(up) + (len(down) if self.shift_down.get() else 0)
        self.shift_info.config(
            text=f'{len(up)} upshift lines'
                 + (f' + {len(down)} downshift lines' if self.shift_down.get() else '')
                 + f' selected ({n} curves x 15 pedal points). '
                   f'Offset {amount:+.0f} rpm.')

    def _shift_apply(self):
        if self.ws.work is None:
            messagebox.showinfo('No bin', 'Open a bin first.')
            return
        amount = self.shift_amount.get()
        if not amount:
            return
        up, down = self._shift_curves()
        targets = up + (down if self.shift_down.get() else [])
        writes = []
        for t in targets:
            rows, cols = t.shape()
            emb = t.z.embedded
            d = decode_table(self.ws.work, t)
            for r in range(rows):
                for c in range(cols):
                    v = d['z'][r][c]
                    if v >= SENTINEL_DEFAULT:
                        continue
                    writes.append((emb, rows, cols, r, c, max(0, v + amount)))
        n = self.ws.set_cells(f'shift speed {amount:+.0f} rpm '
                              f'({len(targets)} lines)', writes)
        self._set_status(f'Shift offset applied: {n} cell(s) across '
                         f'{len(targets)} lines. Sentinels untouched.')
        self._show_selected()

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
    xdf_path = sys.argv[1] if len(sys.argv) > 1 else '../8hpe_cali_v3.xdf'
    bin_path = sys.argv[2] if len(sys.argv) > 2 else None
    App(xdf_path, bin_path).mainloop()


if __name__ == '__main__':
    main()
