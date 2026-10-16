# TunerPro parity harness.
#
# Runs the real TunerPro (free edition, Inno Setup installer from tunerpro.net)
# under Wine on a virtual X display, so an XDF can be read exactly the way
# TunerPro reads it. The point is to settle questions our own parser cannot
# answer on its own - above all how TunerPro resolves strided table addresses,
# which the XDF format does not document.
#
# The image contains no vendor firmware and no calibration data: mount those in.
#
# Apple silicon note. TunerPro is a 32-bit Windows program, and the obvious
# approach - Debian's wine + wine32:i386 - does NOT work here: both Rosetta and
# qemu-x86_64 refuse to execute 32-bit i386 *host* code, so Wine dies with
# "Unhandled illegal instruction" during wineboot. This image therefore installs
# WineHQ's 64-bit-only build and relies on Wine's new WoW64, which runs PE32
# programs entirely through x86_64 host code with no i386 Linux libraries at
# all. Enable Settings > General > "Use Rosetta for x86_64/amd64 emulation" in
# Docker Desktop or it will crawl.
FROM --platform=linux/amd64 debian:bookworm-slim

# Free edition, current build as of 2026-10. Override to pin another build:
#   docker build --build-arg TUNERPRO_URL=.../SetupTunerProFree_v500_9209.exe
ARG TUNERPRO_URL=https://tunerpro.net/download/SetupTunerProFree_v500_10335.exe

ENV DEBIAN_FRONTEND=noninteractive \
    WINEPREFIX=/wine \
    WINEARCH=win64 \
    WINEDEBUG=-all \
    DISPLAY=:99 \
    SCREEN=1600x1000x24 \
    PATH=/opt/wine-staging/bin:$PATH

# Deliberately no `dpkg --add-architecture i386`: keeping i386 out is what makes
# Wine select new WoW64 instead of the i386 path that cannot run here.
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        ca-certificates curl wget gnupg \
        xvfb x11vnc xdotool x11-utils imagemagick \
        procps psmisc coreutils; \
    mkdir -pm755 /etc/apt/keyrings; \
    wget -qO /etc/apt/keyrings/winehq-archive.key https://dl.winehq.org/wine-builds/winehq.key; \
    wget -qNP /etc/apt/sources.list.d/ \
        https://dl.winehq.org/wine-builds/debian/dists/bookworm/winehq-bookworm.sources; \
    apt-get update; \
    # NOT the winehq-staging metapackage: it hard-depends on wine-staging-i386,
    # which cannot be installed (and could not run) here. The amd64 package
    # alone ships the i386-windows PE modules that new WoW64 needs.
    apt-get install -y --no-install-recommends wine-staging-amd64; \
    rm -rf /var/lib/apt/lists/*

# Initialise the prefix and install TunerPro silently (Inno Setup flags).
# Both steps need an X server, hence Xvfb in the same layer. Every Wine call is
# wrapped in `timeout` so a hang fails the build instead of stalling forever.
RUN set -eux; \
    Xvfb :99 -screen 0 "$SCREEN" >/dev/null 2>&1 & \
    for i in $(seq 1 30); do xdpyinfo -display :99 >/dev/null 2>&1 && break; sleep 1; done; \
    wine --version; \
    timeout 600 wineboot --init || true; \
    timeout 120 wineserver -w || true; \
    curl -fsSL -A "Mozilla/5.0" -o /tmp/tunerpro-setup.exe "$TUNERPRO_URL"; \
    timeout 900 wine /tmp/tunerpro-setup.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /NOICONS \
        /DIR='C:\TunerPro' || true; \
    timeout 180 wineserver -w || true; \
    rm -f /tmp/tunerpro-setup.exe; \
    find "$WINEPREFIX/drive_c" -iname 'TunerPro*.exe' -print; \
    test -f "$WINEPREFIX/drive_c/TunerPro/TunerPro.exe"; \
    pkill Xvfb || true

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
COPY ui.sh /usr/local/bin/tp-ui
RUN chmod +x /usr/local/bin/entrypoint.sh /usr/local/bin/tp-ui

# /work is the repo (XDF + tools), /bin-in is where you mount calibration reads.
WORKDIR /work
VOLUME ["/work", "/bin-in", "/out"]

# 5900 = VNC, for driving TunerPro by hand when automation is not enough.
EXPOSE 5900

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["help"]
