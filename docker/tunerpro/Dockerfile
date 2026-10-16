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
# TunerPro is a 32-bit Windows program, so this image is amd64. On Apple
# silicon it runs under emulation; enable Rosetta in Docker Desktop
# (Settings > General > "Use Rosetta for x86_64/amd64 emulation") for usable
# speed.
FROM --platform=linux/amd64 debian:bookworm-slim

# Free edition, current build as of 2026-10. Override to pin another build:
#   docker build --build-arg TUNERPRO_URL=.../SetupTunerProFree_v500_9209.exe
ARG TUNERPRO_URL=https://tunerpro.net/download/SetupTunerProFree_v500_10335.exe

ENV DEBIAN_FRONTEND=noninteractive \
    WINEPREFIX=/wine \
    WINEARCH=win32 \
    WINEDEBUG=-all \
    DISPLAY=:99 \
    SCREEN=1600x1000x24

RUN dpkg --add-architecture i386 \
 && apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates curl \
      wine wine32:i386 \
      xvfb x11vnc xdotool x11-utils imagemagick \
      procps psmisc \
 && rm -rf /var/lib/apt/lists/*

# Initialise the Wine prefix and install TunerPro silently (Inno Setup flags).
# Everything happens in one layer while a virtual display is up, because both
# wineboot and the installer want an X server.
RUN set -eux; \
    Xvfb :99 -screen 0 "$SCREEN" >/dev/null 2>&1 & \
    for i in $(seq 1 30); do xdpyinfo -display :99 >/dev/null 2>&1 && break; sleep 1; done; \
    wineboot --init; \
    for i in $(seq 1 60); do wineserver -w && break || sleep 1; done; \
    curl -fsSL -A "Mozilla/5.0" -o /tmp/tunerpro-setup.exe "$TUNERPRO_URL"; \
    wine /tmp/tunerpro-setup.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /NOICONS \
        /DIR='C:\TunerPro' || true; \
    wineserver -w; \
    rm -f /tmp/tunerpro-setup.exe; \
    test -f "$WINEPREFIX/drive_c/TunerPro/TunerPro.exe" \
      || (echo "TunerPro.exe not found after install:"; \
          find "$WINEPREFIX/drive_c" -iname 'TunerPro*.exe' -print; exit 1); \
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
