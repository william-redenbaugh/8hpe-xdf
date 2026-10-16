#!/usr/bin/env python3
"""Small GUI for the shift-pressure toggle.

Open a calibration read, see the eight stage-3 shift_press_map_b* maps, raise
them, and check the result before saving. The bin in memory is only written
when you choose Save As, and Undo steps back through every change.

The first thing it does with a bin is check the calibration identity, because
every address in this XDF exists in any 2 MB image: pointed at the wrong
calibration the tool would show and edit perfectly plausible numbers that
actually mean something else. A mismatch is shown in red and editing is
blocked unless you deliberately override it.

Launch it with ../run.sh, which picks a Python whose Tk works.
"""
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import xdf_stage3
import xdf_verify
from xdflib import XDF, load_bin, decode_table, check_calibration

DEFAULT_XDF = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           '..', '8hpe70_cali_v3.xdf')


class App(tk.Tk):
    def __init__(self, xdf_path):
        super().__init__()
        self.title('ZF 8HP - shift pressure')
        self.geometry('940x620')
        self.xdf_path = xdf_path
        self.xdf = XDF(xdf_path)
        self.tables = xdf_stage3.pressure_tables(self.xdf)
        self.stock = None          # pristine bytes as loaded
        self.work = None           # bytearray being edited
        self.undo_stack = []
        self.bin_path = None
        self.cal_ok = False
        self._build()
        self._refresh()

    # ---------------------------------------------------------------- layout
    def _build(self):
        bar = ttk.Frame(self, padding=(10, 8))
        bar.pack(fill='x')
        ttk.Button(bar, text='Open bin...', command=self.open_bin).pack(side='left')
        ttk.Button(bar, text='Save As...', command=self.save_bin).pack(side='left', padx=(6, 0))
        ttk.Button(bar, text='Undo', command=self.undo).pack(side='left', padx=(6, 0))
        ttk.Button(bar, text='Check bin', command=self.verify).pack(side='left', padx=(6, 0))
        self.cal_lbl = tk.Label(bar, text='no bin loaded', anchor='e')
        self.cal_lbl.pack(side='right')

        ctl = ttk.LabelFrame(self, text='Raise shift pressure', padding=(10, 8))
        ctl.pack(fill='x', padx=10)
        self.level = tk.StringVar(value='sport')
        for name in ('mild', 'sport', 'max', 'firm', 'hard'):
            ttk.Radiobutton(ctl, text=f'{name}  (+{xdf_stage3.LEVELS[name]}%)',
                            variable=self.level, value=name,
                            command=self._level_changed).pack(side='left', padx=(0, 12))
        ttk.Label(ctl, text='or exact %:').pack(side='left', padx=(12, 4))
        self.pct = tk.DoubleVar(value=float(xdf_stage3.LEVELS['sport']))
        self.scale = ttk.Scale(ctl, from_=0, to=100, variable=self.pct,
                               command=lambda _e: self._pct_changed(), length=220)
        self.scale.pack(side='left')
        self.pct_lbl = ttk.Label(ctl, width=6)
        self.pct_lbl.pack(side='left', padx=(6, 12))
        ttk.Button(ctl, text='Preview', command=self.preview).pack(side='left')
        ttk.Button(ctl, text='Apply', command=self.apply).pack(side='left', padx=(6, 0))

        cols = ('map', 'addr', 'shape', 'min', 'max', 'changed')
        self.tree = ttk.Treeview(self, columns=cols, show='headings', height=11)
        for c, w in zip(cols, (210, 100, 80, 90, 90, 150)):
            self.tree.heading(c, text=c)
            self.tree.column(c, width=w, anchor='w')
        self.tree.pack(fill='both', expand=True, padx=10, pady=(8, 0))

        self.out = tk.Text(self, height=9, wrap='word')
        self.out.pack(fill='both', expand=False, padx=10, pady=(8, 10))
        self._log(__doc__.strip().split('\n\n')[1])

    def _log(self, msg):
        self.out.insert('end', msg.rstrip() + '\n')
        self.out.see('end')

    # ----------------------------------------------------------------- state
    def _level_changed(self):
        self.pct.set(float(xdf_stage3.LEVELS[self.level.get()]))
        self._refresh()

    def _pct_changed(self):
        self.level.set('')
        self._refresh()

    def _refresh(self):
        self.pct_lbl.config(text=f'{self.pct.get():.0f}%')
        for row in self.tree.get_children():
            self.tree.delete(row)
        for t in self.tables:
            emb = t.z.embedded
            if self.work is None:
                lo = hi = '-'
            else:
                vals = [v for r in decode_table(self.work, t)['z'] for v in r]
                lo, hi = min(vals), max(vals)
            rows, cols = t.shape()
            self.tree.insert('', 'end', values=(t.title, f'0x{emb.address:X}',
                                                f'{rows}x{cols}', lo, hi, ''))

    # ------------------------------------------------------------- bin files
    def open_bin(self):
        path = filedialog.askopenfilename(title='Open calibration read',
                                          filetypes=[('bin', '*.bin'), ('all', '*')])
        if not path:
            return
        data = load_bin(path)
        ok, msg = check_calibration(data, os.path.basename(path))
        self.cal_ok = ok
        self.cal_lbl.config(text=('calibration OK' if ok else 'WRONG CALIBRATION'),
                            fg=('#137333' if ok else '#b3261e'))
        self._log(('' if ok else 'REFUSING TO EDIT - ') + msg)
        if not ok:
            if not messagebox.askyesno(
                    'Calibration mismatch',
                    msg + '\n\nLoad it read-only anyway? Editing stays blocked.'):
                return
        self.bin_path, self.stock = path, data
        self.work = bytearray(data)
        self.undo_stack.clear()
        self._log(f'loaded {path}')
        self._refresh()

    def save_bin(self):
        if self.work is None:
            return messagebox.showinfo('No bin', 'Open a calibration read first.')
        path = filedialog.asksaveasfilename(defaultextension='.bin',
                                            filetypes=[('bin', '*.bin')])
        if not path:
            return
        with open(path, 'wb') as f:
            f.write(self.work)
        self._log(f'wrote {path} - checksum NOT corrected, sign before flashing')

    def undo(self):
        if not self.undo_stack:
            return self._log('nothing to undo')
        label, snapshot = self.undo_stack.pop()
        self.work = bytearray(snapshot)
        self._log(f'undid: {label}')
        self._refresh()

    # -------------------------------------------------------------- the edit
    def _apply_to(self, buf):
        pct = self.pct.get()
        report, total = [], 0
        for t in self.tables:
            n, cells, ceiling = xdf_stage3.raise_pressure(buf, t, pct)
            total += n
            report.append((t.title, n, cells, ceiling))
        return report, total, pct

    def preview(self):
        if self.work is None:
            return messagebox.showinfo('No bin', 'Open a calibration read first.')
        report, total, pct = self._apply_to(bytearray(self.work))   # throwaway copy
        self._log(f'--- preview +{pct:.0f}%: {total} cells across {len(report)} maps')
        for title, n, cells, ceiling in report:
            self._log(f'    {title:22s} {n:2d}/{cells:<2d} cells   cap {ceiling}')
        for row, (title, n, cells, _c) in zip(self.tree.get_children(), report):
            self.tree.set(row, 'changed', f'{n}/{cells} would change')

    def apply(self):
        if self.work is None:
            return messagebox.showinfo('No bin', 'Open a calibration read first.')
        if not self.cal_ok:
            return messagebox.showerror(
                'Wrong calibration',
                'This image is a different calibration from the one the XDF '
                'describes. Editing is blocked: the addresses point at other '
                'data, so every value written would be wrong.')
        self.undo_stack.append((f'pressure +{self.pct.get():.0f}%', bytes(self.work)))
        report, total, pct = self._apply_to(self.work)
        self._log(f'APPLIED +{pct:.0f}%: {total} cells across {len(report)} maps')
        self._refresh()
        for row, (title, n, cells, _c) in zip(self.tree.get_children(), report):
            self.tree.set(row, 'changed', f'{n}/{cells} changed')

    # --------------------------------------------------------------- the gate
    def verify(self):
        if self.work is None:
            return messagebox.showinfo('No bin', 'Open a calibration read first.')
        fails = []
        for buf, name in ((self.stock, 'stock'), (self.work, 'edited')):
            ok, msg = check_calibration(buf, name)
            if not ok:
                fails.append(msg)
        mask = xdf_verify.coverage_mask(self.xdf, include_axes=False)
        ranges = xdf_verify.changed_ranges(self.stock, self.work)
        nbytes = sum(j - i for i, j in ranges)
        orphan = [(i, j) for i, j in ranges
                  for pos in range(i, j) if not mask[pos]]
        for lo, hi, why in xdf_verify.PROTECTED:
            if any(i < hi and lo < j for i, j in ranges):
                fails.append(f'protected region modified: {why}')
        if orphan:
            fails.append(f'{len(orphan)} changed byte(s) outside any XDF table, '
                         f'first at 0x{orphan[0][0]:X}')
        self._log(f'--- check: {nbytes} byte(s) changed in {len(ranges)} range(s)')
        for f in fails:
            self._log('  FAIL: ' + f)
        self._log('  VERDICT: ' + ('FAIL - do not flash' if fails
                                   else 'PASS - every change is inside an XDF table'))


def main():
    xdf = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_XDF
    if not os.path.exists(xdf):
        sys.exit(f'XDF not found: {xdf}')
    App(xdf).mainloop()


if __name__ == '__main__':
    main()
