#!/bin/sh
# Launch the shift-pressure GUI with this repo's XDF loaded.
#
#   ./run.sh                 - start the GUI, then "Open bin..."
#
# Edits are made to the BINARY (your 2 MB calibration read) as described by
# the XDF - the XDF itself is never modified. Save writes a new .bin that
# TunerPro (or the flash tool) ingests like any other. Sign bin corrects the
# checksum once tools/xdf_checksum.py search has confirmed the algorithm
# against your stock read.

dir="$(cd "$(dirname "$0")" && pwd)"

# Pick a python whose Tk actually works on this macOS:
#  - Apple's /usr/bin/python3 ships Tk 8.5, which fails on macOS 26+ with
#    "macOS XX or later required"; Homebrew python needs `brew install
#    python-tk` to have tkinter at all. xdflib falls back to its own XML
#    parser where Homebrew python's pyexpat is broken, so either works.
PY=""
for cand in /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do
    [ -x "$cand" ] || continue
    if "$cand" -c 'import tkinter as t, sys; sys.exit(0 if t.TkVersion >= 8.6 else 1)' \
        2>/dev/null; then
        PY="$cand"
        break
    fi
done
if [ -z "$PY" ]; then
    if /usr/bin/python3 -c 'import tkinter' 2>/dev/null; then
        PY=/usr/bin/python3
        echo "warning: only Tk 8.5 found - on macOS 26+ the GUI may refuse to" >&2
        echo "start ('macOS XX or later required'). Fix: brew install python-tk" >&2
    else
        echo "No python with tkinter found. Fix: brew install python-tk" >&2
        exit 1
    fi
fi

cd "$dir/tools" && exec "$PY" xdf_gui.py "$dir/8hpe70_cali_v3.xdf" "$@"
