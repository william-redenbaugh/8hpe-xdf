#!/bin/sh
# tp-ui - drive the running TunerPro window and capture what it shows.
#
# TunerPro has no command line for exporting tables, and its UI layout is not
# something to guess at blind, so parity work is done by looking: send an
# action, take a screenshot, read it, decide the next action.
#
#   tp-ui shot [FILE]        screenshot the whole display (default /out/shot.png)
#   tp-ui key KEYS...        xdotool key (e.g. ctrl+o, Return, alt+f)
#   tp-ui type TEXT          type literal text into the focused control
#   tp-ui click X Y          move to X,Y and left-click
#   tp-ui dblclick X Y       move to X,Y and double-click
#   tp-ui windows            list visible windows with geometry
#   tp-ui focus NAME         raise/focus the first window matching NAME
#
# Every action takes a screenshot afterwards when OUT is set, so a sequence of
# calls leaves a visual trail: OUT=/out/step1.png tp-ui key ctrl+o
set -eu

: "${DISPLAY:=:99}"
: "${SETTLE:=1.5}"

snap() {
    [ -n "${OUT:-}" ] || return 0
    mkdir -p "$(dirname "$OUT")"
    sleep "$SETTLE"
    import -display "$DISPLAY" -window root "$OUT"
    echo "shot: $OUT"
}

cmd="${1:-shot}"
shift 2>/dev/null || true

case "$cmd" in
shot)
    OUT="${1:-/out/shot.png}"
    mkdir -p "$(dirname "$OUT")"
    sleep "$SETTLE"
    import -display "$DISPLAY" -window root "$OUT"
    echo "wrote $OUT"
    ;;
key)
    xdotool key --clearmodifiers "$@"
    snap
    ;;
type)
    xdotool type --clearmodifiers --delay 40 "$*"
    snap
    ;;
click)
    xdotool mousemove "$1" "$2" click 1
    snap
    ;;
dblclick)
    xdotool mousemove "$1" "$2" click --repeat 2 --delay 120 1
    snap
    ;;
windows)
    for id in $(xdotool search --onlyvisible --name '.' 2>/dev/null); do
        name=$(xdotool getwindowname "$id" 2>/dev/null || echo '?')
        geo=$(xdotool getwindowgeometry --shell "$id" 2>/dev/null \
              | tr '\n' ' ' | sed 's/WINDOW=[0-9]*//')
        printf '%s  %-45s %s\n' "$id" "$name" "$geo"
    done
    ;;
focus)
    id=$(xdotool search --onlyvisible --name "$1" | head -1)
    [ -n "$id" ] || { echo "no window matching '$1'" >&2; exit 1; }
    xdotool windowactivate --sync "$id" windowraise "$id"
    snap
    ;;
*)
    echo "unknown action: $cmd" >&2
    sed -n '3,18p' "$0" | sed 's/^# \{0,1\}//' >&2
    exit 2
    ;;
esac
