#!/bin/sh
# Launch the XDF bin editor GUI with this repo's XDF loaded.
#
#   ./run.sh                 - start the GUI, then File > Open bin
#   ./run.sh my_read.bin     - start with your calibration read loaded
#
# Edits are made to the BINARY (your 2 MB calibration read) as described by
# the XDF - the XDF itself is never modified. Save writes a new .bin that
# TunerPro (or the flash tool) ingests like any other; checksums are NOT
# corrected here, so run your checksum flow before flashing.

dir="$(cd "$(dirname "$0")" && pwd)"

# Homebrew python's XML parser is broken on some Macs; prefer the system one.
if [ -x /usr/bin/python3 ]; then
    PY=/usr/bin/python3
else
    PY=python3
fi

cd "$dir/tools" && exec "$PY" xdf_gui.py "$dir/8hpe_cali_v3.xdf" "$@"
