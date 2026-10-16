#!/bin/sh
# Entrypoint for the TunerPro parity harness.
#
#   run        start TunerPro on a virtual display with VNC on :5900
#   shot FILE  start TunerPro, wait for its window, save a PNG screenshot
#   shell      a shell inside the container (Wine prefix already set up)
#   help       this text
#
# Mount the repo at /work, calibration reads at /bin-in, outputs at /out.
set -eu

TP="$WINEPREFIX/drive_c/TunerPro/TunerPro.exe"

start_x() {
    if ! xdpyinfo -display "$DISPLAY" >/dev/null 2>&1; then
        Xvfb "$DISPLAY" -screen 0 "$SCREEN" >/dev/null 2>&1 &
        i=0
        while ! xdpyinfo -display "$DISPLAY" >/dev/null 2>&1; do
            i=$((i + 1))
            [ "$i" -gt 30 ] && { echo "Xvfb failed to start" >&2; exit 1; }
            sleep 1
        done
    fi
}

start_vnc() {
    pgrep x11vnc >/dev/null 2>&1 && return 0
    x11vnc -display "$DISPLAY" -forever -shared -nopw -quiet -bg >/dev/null 2>&1 || true
    echo "VNC listening on :5900 (no password) - connect with any VNC client."
}

# Wait for a TunerPro top-level window to exist, then give it a moment to paint.
wait_window() {
    i=0
    while [ "$i" -lt "${TP_WINDOW_TIMEOUT:-120}" ]; do
        if xdotool search --name 'TunerPro' >/dev/null 2>&1; then
            sleep "${TP_SETTLE:-6}"
            return 0
        fi
        i=$((i + 1))
        sleep 1
    done
    echo "TunerPro window did not appear within ${TP_WINDOW_TIMEOUT:-120}s" >&2
    return 1
}

cmd="${1:-help}"
shift 2>/dev/null || true

case "$cmd" in
help)
    sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'
    echo
    echo "TunerPro: $TP"
    ls -l "$TP" 2>/dev/null || echo "  (not installed!)"
    ;;

run)
    start_x
    start_vnc
    echo "Launching TunerPro${*:+ with: $*}"
    exec wine "$TP" "$@"
    ;;

shot)
    out="${1:-/out/tunerpro.png}"
    shift 2>/dev/null || true
    start_x
    start_vnc
    wine "$TP" "$@" >/tmp/wine.log 2>&1 &
    wait_window
    mkdir -p "$(dirname "$out")"
    import -display "$DISPLAY" -window root "$out"
    echo "wrote $out"
    ;;

shell)
    start_x
    exec /bin/bash
    ;;

*)
    exec "$cmd" "$@"
    ;;
esac
