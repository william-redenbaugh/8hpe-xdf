# Design: kickdown toggle, blip slider, Windows compatibility

Applies AFTER the mode/TCC slider changes (xdflib mode groups, --mode plumbing, tcc-lockshift,
GUI Modes panel + TCC tab already exist). Follow existing code style; no new dependencies.

## 1. `kickdown` subcommand (tools/xdf_tune.py) — deeper downshifts at full pedal
User problem: at full pedal the box only downshifts to ~4500 rpm post-shift; wants one gear
deeper, landing up to ~5900 rpm, ONLY at kickdown, with a smooth ramp (no cliff).

`xdf_tune.py kickdown BIN -o OUT --max-rpm 5900 [--blend-from 700] [--mode M|--chars ...]`

Mechanism A (default, evidence HIGH — native E84 shift lines):
- For every DOWNSHIFT single curve (shift_curves kind 'down', pair X>Y with target gear Y),
  target line value T = max-rpm * 0.98 / ratio(Y) in output rpm. Ratios: 8HP45
  {1:4.714, 2:3.143, 3:2.106, 4:1.667, 5:1.285, 6:1.000, 7:0.839} (target gear = lower gear
  of the pair). Add --r1..--r7 overrides mirroring redline-hold's style (defaults above).
- Pedal blending (the "compensation"): for each cell with pedal p (from the decoded x axis):
  w = 0 for p <= blend-from; w = (p - blend-from)/(1100 - blend-from) clamped 0..1 otherwise.
  new = max(v, round(v + w * (T - v))) — only ever raises, full effect only at kickdown
  (p = 1100), smooth ramp above blend-from. Skip v<=0 and v>=SENTINEL (7900; E84 disabled
  sentinel is 8200).
- SAFETY CLAMP: never set a downshift cell above (matching upshift line cell - 150 rpm) when
  that upshift cell is active (0 < up < SENTINEL); hysteresis must survive. Look up the
  matching 'up' curve of the same char/pair like op_early_upshift does (it maps down from up;
  here map up from down).
- Respect --mode/--chars exactly like the other line ops.
- Print per-pair targets and changed-cell counts.

Mechanism B (opt-in ONLY, evidence LOW — candidate rpm-cap tables):
- `--cap-at 0x1A8B02 --cap-rpm 5900` additionally raises u16 values in a candidate
  post-downshift rpm-cap block. The three candidate blocks found by structure scan (NOT
  code-verified; the E84 read has no program ROM):
    0x1A8B02..0x1A8BA2: eight 7-value rows starting (5500, 4500, 4000, 4000, 4000, 4000, 4000)
    0x1A847C..0x1A850A: seven 6-value rows of (5000 x6)
    0x1A97FC..: rows of (5000, 4000 x5)
  Raise each u16 in the given block to max(value, cap-rpm) bounded to <= 6500. REFUSE to run
  without both flags; print a loud warning that these tables are unverified candidates and to
  test incrementally. Do NOT add a GUI control for mechanism B.
- Also ADD the three candidate blocks to 8hpe84_cali_v1.xdf as tables in a new category
  "E84 candidates: kickdown rpm caps" (u16 rows as above, MATH X, LOW confidence descriptions
  explaining the structure-scan evidence and the 4500 observation). Preserve CRLF (open the
  XDF with newline='') and validate with ElementTree after editing. Insert before </XDFFORMAT>,
  uniqueids 0x7F10+.

## 2. `blip` slider + subcommand — stronger downshift rev-match blip
`xdf_tune.py blip BIN -o OUT --pct 25 [--pairs 4to3,5to4] [--all-pairs]`
- Tables: every XDFTABLE whose title matches ^(auto_)?shiftexec_dn_blip_trq (29 in the E84
  XDF, 16 gear pairs, mostly HIGH confidence). --pairs filters by the NtoM token in the title;
  default --all-pairs.
- ENCODING (critical): z is u8 with 128 = zero torque request. Scale the EXCESS over 128:
  new = 128 + round((v - 128) * (1 + pct/100)), clamp 128..255 (never push below 128 for
  positive blips; cells already at 128 stay 128). pct range -50..+100.
- Optionally also scale the blip duration/output-gradient gates? NO — torque tables only;
  the scale tables (coolant/outgrad) are factors and stay stock.
- GUI: add a "Blip" row to the TCC lockup tab (or its own small tab if cleaner): slider
  -50..+100 % labeled "Downshift blip strength vs stock", pair entry defaulting to all,
  Preview/Apply via Workspace.set_cells (undo must work), reusing the xdf_tune op.

## 3. Windows compatibility (all tools/*.py + launcher)
- Replace the two non-ASCII characters in source: the ellipsis in xdf_gui.py and the em-dash
  in xdf_show.py with ASCII ('...' and '--'). Verify afterwards: no byte > 0x7F in any
  tools/*.py EXCEPT where a docstring genuinely needs it (then it must still be cp1252-safe
  when printed -> prefer ASCII everywhere).
- Add a safe-print guard once in xdflib.py (shared import):
    if sys.platform == 'win32':
        for s in (sys.stdout, sys.stderr):
            if s and hasattr(s, 'reconfigure'):
                s.reconfigure(errors='replace')
  (Python 3.7+; guards cp1252 redirects against any stray non-ASCII in XDF titles.)
- New run.bat at repo root mirroring run.sh: pick XDF (8hpe84_cali_v1.xdf if present else
  8hpe70_cali_v3.xdf), then `py -3 tools\xdf_gui.py <xdf> %*` falling back to
  `python tools\xdf_gui.py ...` if py.exe is absent. Plain cmd.exe syntax, CRLF line endings,
  @echo off.
- Check (and fix if needed): e84_modes.json path handling uses os.path.join/dirname (no
  hardcoded '/'), bins opened 'rb'/'wb', XDF opened with explicit encoding='utf-8' (Windows
  default cp1252 would break on any non-ASCII in the XDF), no os.exec*/fork/termios/fcntl.
- Keep /usr/bin/env python3 shebangs (harmless on Windows).

## 4. Tests (bin = WBAUU3C59AA541121_GKE233_8609556_0479U10K791Z_tune.bin at repo root)
- kickdown --max-rpm 5900: non-zero cells; verify via xdf_show that char 00 "Downshift char
  00: 2>1" kickdown column rose toward 5900*0.98/4.714 ~ 1226 output rpm but mid-pedal
  (<=700) cells unchanged; verify no down cell exceeds its up cell - 150 where up active.
- kickdown --cap-at without --cap-rpm (and vice versa) errors; with both: warns loudly and
  changes only the named block.
- blip --pct 25 --pairs 4to3: only the 4to3 blip tables change; a z=128 cell stays 128;
  a z=160 cell becomes 128 + 40 = 168.
- XDF still parses; xdf_ls shows the new candidate category with 3 tables.
- python3 -X utf8=0 -c "import xdf_gui, xdf_tune, xdflib" works; grep confirms no non-ASCII
  bytes remain in tools/*.py; run.bat exists with CRLF endings.
