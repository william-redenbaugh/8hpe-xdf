#!/usr/bin/env python3
"""Small GUI for the toggles: shift pressure, wheel, differential, true manual.

Open a calibration read and work on it in memory. Four panels:

  Shift pressure   the eight stage-3 shift_press_map_b* maps, raised together
  Wheel            the Radumfang dynamic rolling circumference, from a tyre
                   size or in millimetres
  Differential     your real final drive against the fixed list the TCU snaps
                   to, and the circumference trim that makes it learn the
                   right entry
  True manual      the XDF's own [PATCH] True manual, on or off

The bin in memory is only written when you choose Save As, Undo steps back
through every change, and Revert on the True manual panel puts the bytes from
the bin you opened back.

The first thing it does with a bin is check the calibration identity, because
every address in this XDF exists in any 2 MB image: pointed at the wrong
calibration the tool would show and edit perfectly plausible numbers that
actually mean something else. A mismatch is shown in red and editing is
blocked unless you deliberately override it.

Check bin applies the same gate as xdf_verify.py: every changed byte must sit
inside an XDF item, or inside an XDFPATCH entry written exactly as the XDF
declares it. Nothing here corrects a checksum.

Launch it with ../run.sh, which picks a Python whose Tk works.
"""
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import xdf_stage3
import xdf_truemanual
import xdf_vehicle
import xdf_verify
from xdflib import XDF, load_bin, decode_table, check_calibration

DEFAULT_XDF = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           '..', '8hpe70_cali_v3.xdf')

GREEN, RED, GREY = '#137333', '#b3261e', '#5f6368'


class App(tk.Tk):
    def __init__(self, xdf_path):
        super().__init__()
        self.title('ZF 8HP - E70 calibration toggles')
        self.geometry('980x760')
        self.xdf_path = xdf_path
        self.xdf = XDF(xdf_path)
        self.tables = xdf_stage3.pressure_tables(self.xdf)
        self.tcc_maps = xdf_stage3.tcc_tables(self.xdf)
        self.wheel_const = xdf_vehicle.wheel_constant(self.xdf)
        self.tm_patch = xdf_truemanual.true_manual_patch(self.xdf)
        self.ratios = None         # cached (ratios, lines, addr) per bin
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

        nb = ttk.Notebook(self)
        nb.pack(fill='both', expand=True, padx=10)
        self._build_pressure(nb)
        self._build_wheel(nb)
        self._build_diff(nb)
        self._build_truemanual(nb)

        self.out = tk.Text(self, height=11, wrap='word')
        self.out.pack(fill='both', expand=False, padx=10, pady=(8, 10))
        self._log(next(p for p in __doc__.split('\n\n')
                       if p.startswith('The first thing')))

    def _build_pressure(self, nb):
        tab = ttk.Frame(nb, padding=(0, 8))
        nb.add(tab, text='Shift pressure')
        ctl = ttk.LabelFrame(tab, text='Raise shift pressure', padding=(10, 8))
        ctl.pack(fill='x')
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
        self.tcc = tk.BooleanVar(value=True)
        ttk.Checkbutton(ctl, text='converter lockup', variable=self.tcc,
                        command=self._refresh).pack(side='left', padx=(0, 10))
        ttk.Button(ctl, text='Preview', command=self.preview).pack(side='left')
        ttk.Button(ctl, text='Apply', command=self.apply).pack(side='left', padx=(6, 0))

        cols = ('map', 'addr', 'shape', 'min', 'max', 'changed')
        self.tree = ttk.Treeview(tab, columns=cols, show='headings', height=10)
        for c, w in zip(cols, (210, 100, 80, 90, 90, 150)):
            self.tree.heading(c, text=c)
            self.tree.column(c, width=w, anchor='w')
        self.tree.pack(fill='both', expand=True, pady=(8, 0))

    def _build_wheel(self, nb):
        tab = ttk.Frame(nb, padding=(0, 8))
        nb.add(tab, text='Wheel circumference')
        emb = self.wheel_const.embedded
        box = ttk.LabelFrame(
            tab, text=f'{self.wheel_const.title}  @0x{emb.address:X} '
                      f'({emb.type_name()})', padding=(10, 8))
        box.pack(fill='x')

        self.wheel_now = ttk.Label(box, text='open a bin', font=('TkDefaultFont', 13))
        self.wheel_now.grid(row=0, column=0, columnspan=4, sticky='w', pady=(0, 8))

        ttk.Label(box, text='Tyre size:').grid(row=1, column=0, sticky='w')
        self.tire = tk.StringVar()
        ttk.Entry(box, textvariable=self.tire, width=14).grid(
            row=1, column=1, sticky='w', padx=(6, 6))
        self.tire.trace_add('write', lambda *_a: self._tire_changed())
        self.tire_lbl = ttk.Label(box, text='e.g. 245/40R18', foreground=GREY)
        self.tire_lbl.grid(row=1, column=2, sticky='w')
        ttk.Button(box, text='Apply tyre',
                   command=self._apply_tire).grid(row=1, column=3, padx=(10, 0))

        ttk.Label(box, text='Or exact mm:').grid(row=2, column=0, sticky='w', pady=(8, 0))
        self.wheel_mm = tk.StringVar()
        ttk.Entry(box, textvariable=self.wheel_mm, width=14).grid(
            row=2, column=1, sticky='w', padx=(6, 6), pady=(8, 0))
        ttk.Label(box, text="the tyre maker's Abrollumfang, if you have it",
                  foreground=GREY).grid(row=2, column=2, sticky='w', pady=(8, 0))
        ttk.Button(box, text='Apply mm',
                   command=self._apply_mm).grid(row=2, column=3, padx=(10, 0), pady=(8, 0))

        ttk.Label(tab, justify='left', foreground=GREY, text=(
            'Dynamic ROLLING circumference, not the geometric one:\n'
            '    pi x (rim_inch x 25.4 + 2 x width x profile/100) x 0.97\n'
            'This is the only axle input the TCU has - it derives the final\n'
            'drive from it. After flashing, reset the learned value (Tool32\n'
            'steuern_lernfkt_ruecksetzen 0) and drive above ~24 km/h.\n'
            'Do not use it to correct the speedometer; that is DSC coding.'
        )).pack(anchor='w', pady=(10, 0))

    def _build_diff(self, nb):
        tab = ttk.Frame(nb, padding=(0, 8))
        nb.add(tab, text='Differential')
        box = ttk.LabelFrame(tab, text='Final drive', padding=(10, 8))
        box.pack(fill='x')

        self.diff_list_lbl = ttk.Label(box, text='open a bin', justify='left')
        self.diff_list_lbl.grid(row=0, column=0, columnspan=5, sticky='w', pady=(0, 8))

        ttk.Label(box, text='Real axle ratio:').grid(row=1, column=0, sticky='w')
        self.diff_ratio = tk.StringVar()
        ttk.Entry(box, textvariable=self.diff_ratio, width=10).grid(
            row=1, column=1, sticky='w', padx=(6, 12))
        ttk.Label(box, text='Learned (status_lernfkt):').grid(row=1, column=2, sticky='w')
        self.diff_learned = tk.StringVar()
        ttk.Entry(box, textvariable=self.diff_learned, width=10).grid(
            row=1, column=3, sticky='w', padx=(6, 12))
        ttk.Button(box, text='Check', command=self._diff_check).grid(row=1, column=4)
        ttk.Button(box, text='Apply trim', command=self._diff_fix).grid(
            row=2, column=4, pady=(8, 0))

        ttk.Label(tab, justify='left', foreground=GREY, text=(
            'The TCU has no axle setting. It learns the final drive and snaps\n'
            'it to the nearest entry of a fixed internal list, so the job is\n'
            'to make it land on the right entry. Leave Learned empty to just\n'
            'check a ratio against the list; fill it in after a relearn drive\n'
            'to get the circumference trim that corrects it.\n'
            'The list is read out of your bin, not assumed - the address is\n'
            'shown above, and it differs between calibrations.'
        )).pack(anchor='w', pady=(10, 0))

    def _build_truemanual(self, nb):
        tab = ttk.Frame(nb, padding=(0, 8))
        nb.add(tab, text='True manual')
        box = ttk.LabelFrame(tab, text=self.tm_patch.title, padding=(10, 8))
        box.pack(fill='x')
        self.tm_lbl = tk.Label(box, text='open a bin', font=('TkDefaultFont', 13))
        self.tm_lbl.pack(anchor='w', pady=(0, 8))
        row = ttk.Frame(box)
        row.pack(anchor='w')
        ttk.Button(row, text='Turn ON', command=self._tm_on).pack(side='left')
        ttk.Button(row, text='Turn OFF (back to the opened bin)',
                   command=self._tm_off).pack(side='left', padx=(6, 0))
        ttk.Button(row, text='Entry status',
                   command=self._tm_status).pack(side='left', padx=(6, 0))

        ttk.Label(tab, justify='left', foreground=GREY, text=(
            'Removes the TCU-side forced upshift at redline in manual mode.\n'
            'The DME rev limiter still protects the engine; nothing here\n'
            'touches engine control. Seven writes, taken from the XDF patch\n'
            'itself, not from this tool.\n'
            '\n'
            'ORDER: raise shift pressure FIRST, then turn this on - 0x1CECA4\n'
            'belongs to both, and a stage-3 edit applied afterwards would\n'
            'undo half of it.\n'
            'The df31 gate byte (0x1D34B1) is marked SUPERVISED TEST ONLY in\n'
            'the XDF: its effect hinges on a runtime value static analysis\n'
            'could not pin down.\n'
            'Four of its spans are not inside any XDF table, so the command\n'
            'line gate needs --allow-patch; Check bin here already applies\n'
            'that rule, and only where the bytes match the patch exactly.'
        )).pack(anchor='w', pady=(10, 0))

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

    def _tire_changed(self):
        spec = self.tire.get().strip()
        if not spec:
            return self.tire_lbl.config(text='e.g. 245/40R18', foreground=GREY)
        try:
            mm = xdf_vehicle.tire_circumference(spec)
        except ValueError:
            return self.tire_lbl.config(text='unparsed', foreground=RED)
        self.tire_lbl.config(text=f'= {mm:.0f} mm', foreground=GREEN)

    def _refresh(self):
        self.pct_lbl.config(text=f'{self.pct.get():.0f}%')
        for row in self.tree.get_children():
            self.tree.delete(row)
        shown = self.tables + (self.tcc_maps if self.tcc.get() else [])
        for t in shown:
            emb = t.z.embedded
            if self.work is None:
                lo = hi = '-'
            else:
                vals = [v for r in decode_table(self.work, t)['z'] for v in r]
                lo, hi = min(vals), max(vals)
            rows, cols = t.shape()
            self.tree.insert('', 'end', values=(t.title, f'0x{emb.address:X}',
                                                f'{rows}x{cols}', lo, hi, ''))
        if self.work is None:
            return
        value, note = xdf_vehicle.read_circumference(self.work, self.wheel_const)
        self.wheel_now.config(
            text=f'{value} mm' + (f'   ({note})' if note else
                                  f'   ({xdf_vehicle.rolling_diameter(value):.0f} '
                                  'mm rolling diameter)'),
            foreground=RED if note else GREEN)
        overall, _rows = xdf_truemanual.status(self.work, self.tm_patch)
        self.tm_lbl.config(text={'on': 'ON', 'off': 'OFF',
                                 'part': 'PARTLY APPLIED - no clean apply '
                                         'produces this'}[overall],
                           fg={'on': GREEN, 'off': GREY, 'part': RED}[overall])

    def _ready(self, need_edit=True):
        """Guard every action: a bin is loaded, and editing is allowed."""
        if self.work is None:
            messagebox.showinfo('No bin', 'Open a calibration read first.')
            return False
        if need_edit and not self.cal_ok:
            messagebox.showerror(
                'Wrong calibration',
                'This image is a different calibration from the one the XDF '
                'describes. Editing is blocked: the addresses point at other '
                'data, so every value written would be wrong.')
            return False
        return True

    def _snapshot(self, label):
        self.undo_stack.append((label, bytes(self.work)))

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
                            fg=(GREEN if ok else RED))
        self._log(('' if ok else 'REFUSING TO EDIT - ') + msg)
        if not ok:
            if not messagebox.askyesno(
                    'Calibration mismatch',
                    msg + '\n\nLoad it read-only anyway? Editing stays blocked.'):
                return
        self.bin_path, self.stock = path, data
        self.work = bytearray(data)
        self.undo_stack.clear()
        self.ratios = None
        self._log(f'loaded {path}')
        self._refresh()
        self._diff_refresh()

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

    # ------------------------------------------------------- shift pressure
    def _apply_to(self, buf):
        pct = self.pct.get()
        report, total = [], 0
        for t in self.tables:
            n, cells, ceiling = xdf_stage3.raise_pressure(buf, t, pct)
            total += n
            report.append((t.title, n, cells, ceiling))
        # The converter clutch rides the same slider at half strength. These are
        # general lockup pressures, not a shift-only control.
        if self.tcc.get():
            tcc_pct = round(pct * xdf_stage3.TCC_FRACTION, 1)
            for t in self.tcc_maps:
                n, cells, ceiling = xdf_stage3.raise_pressure(buf, t, tcc_pct)
                total += n
                report.append((t.title, n, cells, ceiling))
        return report, total, pct

    def preview(self):
        if not self._ready(need_edit=False):
            return
        report, total, pct = self._apply_to(bytearray(self.work))   # throwaway copy
        self._log(f'--- preview +{pct:.0f}%: {total} cells across {len(report)} maps')
        for title, n, cells, ceiling in report:
            self._log(f'    {title:22s} {n:2d}/{cells:<2d} cells   cap {ceiling}')
        for row, (title, n, cells, _c) in zip(self.tree.get_children(), report):
            self.tree.set(row, 'changed', f'{n}/{cells} would change')

    def apply(self):
        if not self._ready():
            return
        self._snapshot(f'pressure +{self.pct.get():.0f}%')
        report, total, pct = self._apply_to(self.work)
        self._log(f'APPLIED +{pct:.0f}%: {total} cells across {len(report)} maps')
        self._refresh()
        for row, (title, n, cells, _c) in zip(self.tree.get_children(), report):
            self.tree.set(row, 'changed', f'{n}/{cells} changed')

    # ------------------------------------------------------------ the wheel
    def _set_circumference(self, mm, label):
        old, _note = xdf_vehicle.read_circumference(self.work, self.wheel_const)
        lo, hi = xdf_vehicle.SANE_MM
        if not lo <= mm <= hi:
            return messagebox.showerror(
                'Out of range',
                f'{mm:.0f} mm is outside {lo:.0f}-{hi:.0f} mm. That is a typo '
                'or a diameter, not a rolling circumference.')
        tlo, thi = xdf_vehicle.TYPICAL_MM
        if not tlo <= mm <= thi and not messagebox.askyesno(
                'Unusual value',
                f'{mm:.0f} mm is outside the usual {tlo:.0f}-{thi:.0f} mm '
                'band. Write it anyway?'):
            return
        self._snapshot(f'wheel {old} -> {round(mm)} mm')
        stored = xdf_vehicle.write_circumference(self.work, self.wheel_const, mm)
        self._log(f'APPLIED wheel circumference {old} -> {stored} mm ({label})')
        self._log('    relearn after flashing: Tool32 '
                  'steuern_lernfkt_ruecksetzen 0, drive above ~24 km/h, then '
                  'check status_lernfkt against your real axle')
        self._refresh()

    def _apply_tire(self):
        if not self._ready():
            return
        try:
            mm = xdf_vehicle.tire_circumference(self.tire.get())
        except ValueError as e:
            return messagebox.showerror('Tyre size', str(e))
        self._set_circumference(mm, f'tyre {self.tire.get().strip()}')

    def _apply_mm(self):
        if not self._ready():
            return
        try:
            mm = float(self.wheel_mm.get())
        except ValueError:
            return messagebox.showerror('Millimetres',
                                        f'{self.wheel_mm.get()!r} is not a number')
        self._set_circumference(mm, 'entered directly')

    # ----------------------------------------------------------- the differential
    def _diff_refresh(self):
        """Find the ratio list in the loaded bin (cached - it is a full scan)."""
        if self.work is None:
            return
        if self.ratios is None:
            self.diff_list_lbl.config(text='searching the image for the list...')
            self.update_idletasks()
            self.ratios = xdf_vehicle.describe_ratio_list(self.work)
        ratios, lines, addr = self.ratios
        head = (f'list at 0x{addr:X}' if addr is not None
                else 'LIST NOT FOUND IN THIS IMAGE - showing the documented one')
        self.diff_list_lbl.config(
            text=head + ':  ' + ' '.join(f'{r:.2f}' for r in ratios),
            foreground=GREY if addr is not None else RED)
        for line in lines:
            self._log(line)

    def _diff_inputs(self):
        try:
            ratio = float(self.diff_ratio.get())
        except ValueError:
            messagebox.showerror('Ratio', 'Enter the real axle ratio, e.g. 3.73')
            return None
        learned = None
        if self.diff_learned.get().strip():
            try:
                learned = float(self.diff_learned.get())
            except ValueError:
                messagebox.showerror('Learned', 'Not a number - leave it empty '
                                                'if you have not driven a relearn yet')
                return None
        return ratio, learned

    def _diff_report(self):
        got = self._diff_inputs()
        if got is None:
            return None
        self._diff_refresh()
        ratios = self.ratios[0]
        circ, _note = xdf_vehicle.read_circumference(self.work, self.wheel_const)
        lines, suggested = xdf_vehicle.diff_report(got[0], ratios, circ, got[1])
        self._log('--- differential')
        for line in lines:
            self._log('    ' + line)
        return suggested

    def _diff_check(self):
        if self._ready(need_edit=False):
            self._diff_report()

    def _diff_fix(self):
        if not self._ready():
            return
        suggested = self._diff_report()
        if suggested is None:
            return messagebox.showinfo(
                'Nothing to trim',
                'Apply trim needs a Learned value that disagrees with the '
                'real ratio. With both equal there is nothing to correct.')
        self._set_circumference(suggested, 'differential trim')

    # ------------------------------------------------------------ true manual
    def _tm_status(self):
        if not self._ready(need_edit=False):
            return
        overall, rows = xdf_truemanual.status(self.work, self.tm_patch)
        self._log(f'--- {self.tm_patch.title}: {overall.upper()}')
        for e, state, cur in rows:
            self._log(f'    {state:4s} {e.name:22s} @0x{e.address:X} '
                      f'{len(e.patchdata):3d} B  now={cur[:8].hex()}'
                      f'{"..." if len(cur) > 8 else ""}')

    def _tm_on(self):
        if not self._ready():
            return
        self._snapshot('true manual ON')
        n = xdf_truemanual.apply_patch(self.work, self.tm_patch)
        self._log(f'APPLIED true manual: {n} byte(s) over '
                  f'{len(self.tm_patch.entries)} entries'
                  + (' (already on, nothing changed)' if n == 0 else ''))
        self._log('    the DME rev limiter still protects the engine; the '
                  'df31 gate byte is supervised-test-only - see the panel')
        self._refresh()

    def _tm_off(self):
        if not self._ready():
            return
        self._snapshot('true manual OFF')
        n = xdf_truemanual.revert_patch(self.work, self.tm_patch, self.stock)
        self._log(f'REVERTED true manual: {n} byte(s) restored from '
                  f'{os.path.basename(self.bin_path)}'
                  + (' (already off, nothing changed)' if n == 0 else ''))
        self._refresh()

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
        pmask, _applied = xdf_verify.applied_patch_mask(self.xdf, self.work)
        ranges = xdf_verify.changed_ranges(self.stock, self.work)
        nbytes = sum(j - i for i, j in ranges)
        in_tables = in_patch = 0
        orphan = []
        for i, j in ranges:
            for pos in range(i, j):
                if mask[pos]:
                    in_tables += 1
                elif pmask[pos]:
                    in_patch += 1
                else:
                    orphan.append(pos)
        for lo, hi, why in xdf_verify.PROTECTED:
            if any(i < hi and lo < j for i, j in ranges):
                fails.append(f'protected region modified: {why}')
        if orphan:
            fails.append(f'{len(orphan)} changed byte(s) outside any XDF item '
                         f'or exactly-applied patch, first at 0x{orphan[0]:X}')
        self._log(f'--- check: {nbytes} byte(s) changed in {len(ranges)} range(s)')
        self._log(f'    {in_tables} inside XDF tables/constants, '
                  f'{in_patch} inside exactly-applied XDF patch entries')
        for f in fails:
            self._log('  FAIL: ' + f)
        self._log('  VERDICT: ' + ('FAIL - do not flash' if fails
                                   else 'PASS - every change is explained by '
                                        'the XDF'))


def main():
    xdf = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_XDF
    if not os.path.exists(xdf):
        sys.exit(f'XDF not found: {xdf}')
    App(xdf).mainloop()


if __name__ == '__main__':
    main()
