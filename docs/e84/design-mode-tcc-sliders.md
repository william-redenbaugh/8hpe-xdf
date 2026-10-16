# Design: drive-mode groups + TCC lockshift (E84 tools)

## Facts constraining the design (verified against 8hpe84_cali_v1.xdf and the E70 RE)
- Shift LINES are per-characteristic (21 chars on E84, memory-order numbering, drive-mode mapping
  unknown without the program ROM -> user assigns chars to modes after logging).
- Shift EXECUTION time tables are shared across drive programs (indexed by clutch K1/K2/K0 and
  torque, NOT by program; the per-shift-type tables that would differentiate did not survive the
  E84 port). Per-mode quickness is therefore NOT implementable honestly -> quickness stays global
  with an explanatory note.
- TCC close/open maps in the E84 XDF are global (not per-char): tcc_close_time_map @0x1a2314
  (z raw, MED), tcc_close_press_map @0x1a21f4 (MED), tcc_press_rate_drive_curve, tcc_ramp_curve,
  tcc_open_speed_slip_map/2, tcc_slip_target_curve/map. A lockup slider is global; say so in UI.

## 1. Mode groups config
- File `e84_modes.json` stored NEXT TO the loaded XDF (same dir), JSON:
  `{"sport": [8, 9], "normal": [0, 1, 2, ...]}` (characteristic numbers as ints).
- Loader in tools/xdflib.py: `load_mode_groups(xdf_path) -> {'sport': set, 'normal': set}`.
  Defaults when the file is missing: normal = all chars, sport = empty set.
  Saver: `save_mode_groups(xdf_path, groups)`.
- Resolution helper `chars_for_mode(xdf_path, mode)`: mode in {'all','normal','sport'};
  'all' -> None (no filter). 'sport' with empty set -> raise SystemExit with the message that
  sport chars must be assigned first (GUI Modes panel or editing e84_modes.json), because the
  char-to-drive-mode mapping is not recoverable from a calibration-only read.

## 2. CLI (tools/xdf_tune.py)
- Add `--mode {all,normal,sport}` (default all) to: shift-offset, redline-hold, sport-redline,
  early-upshift. It resolves to a chars set via chars_for_mode and INTERSECTS with --chars if both
  given. early-upshift currently takes no chars argument -> extend op_early_upshift(buf, xdf, rpm,
  chars=None) to pass chars into shift_curves (both up and down lookups).
- New subcommand `tcc-lockshift`:
  `xdf_tune.py tcc-lockshift BIN -o OUT --pct 20 [--firm-pct N]`
  - pct 0..40: scale `tcc_close_time_map` z DOWN by pct (faster lockup apply) and
    `tcc_press_rate_drive_curve` + `tcc_ramp_curve` z UP by pct (faster pressure ramp).
  - firm-pct (default pct/2): scale `tcc_close_press_map` z UP (firmer apply).
  - Find tables by exact title via a helper that warns-and-skips missing titles (keeps the op
    usable on the E70 XDF where names differ); print per-table cell counts. Scale raw z values
    multiplicatively, round, clamp to the element's unsigned/signed range, skip zeros.
  - Print a note: global maps (not per drive mode); mode-specific lockup lives in strategy
    tables that need a full flash read.
- Keep all existing commands working unchanged when --mode is omitted.

## 3. GUI (tools/xdf_gui.py)
- New "Modes" panel (either its own tab placed before Vehicle, or a compact frame at the top of
  the Shift speed tab — implementer's choice, keep it obvious): two multi-select listboxes or a
  single listbox with Sport/Normal toggle showing chars 00..NN (from the XDF pedal-axis items),
  Save button -> save_mode_groups. Show current assignment on load.
- Mode radio (All / Normal / Sport) added to: Shift speed tab slider, NA presets tab redline and
  early-upshift rows. The radio resolves to a chars filter exactly like the CLI. Quickness row
  gets NO radio but a one-line note: "applies to all drive modes - the 8HP uses shared
  execution-time tables (K1/K2 are clutches, not programs)".
- New "TCC lockup" tab: one slider 0..40 % ("lockup speed - scales converter close time down,
  close pressure and ramp rate up"), Preview and Apply buttons following the exact pattern of the
  NA presets tab (preview lists affected tables + cell counts via the same op function imported
  from xdf_tune; apply uses Workspace.set_cells so undo works). Label states the maps are global
  (all drive modes) and MED/LOW confidence from the RE.
- GUI should import and reuse op functions from xdf_tune (they already operate on (buf, xdf));
  where the GUI needs preview-only behaviour, compute with a copied bytearray.
- Keep `python3 -c "import xdf_gui"` working without a display (no Tk calls at import time).

## 4. Testing expectations (bin = ../WBAUU3C59AA541121_GKE233_8609556_0479U10K791Z_tune.bin)
- Every CLI command above runs against the E84 bin and reports non-zero changed cells
  (tcc-lockshift: expect changes in >= 3 tables).
- `--mode sport` without assignments exits with the explanatory error.
- After writing e84_modes.json with sport=[8,9], `sport-redline --mode sport` touches only
  chars 8/9 (verify via xdf_diff: only those char tables change).
- xdf_diff / xdf_show / xdf_export still work on outputs.
