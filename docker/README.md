# Containers

Two images. Neither contains firmware, calibration data or an XDF — mount those.

| Image | What it is for |
|---|---|
| `docker/tools` | The XDF command-line tools on a known-good Python, identically on macOS, Linux, Windows and CI. |
| `docker/tunerpro` | The real TunerPro running under Wine, to check that TunerPro and our tools read the same bytes. |

## Tools

```sh
docker build -t 8hpe-tools -f docker/tools/Dockerfile .

# list categories
docker run --rm -v "$PWD:/work" 8hpe-tools \
    /opt/8hpe/tools/xdf_ls.py 8hpe70_cali_v3.xdf --categories

# decode a table from a calibration read
docker run --rm -v "$PWD:/work" -v /path/to/reads:/bin-in:ro 8hpe-tools \
    /opt/8hpe/tools/xdf_show.py 8hpe70_cali_v3.xdf /bin-in/stock.bin "Upshift char 00: 1>2"

# the safety gate, before you flash anything
docker run --rm -v "$PWD:/work" -v /path/to/reads:/bin-in:ro 8hpe-tools \
    /opt/8hpe/tools/xdf_verify.py 8hpe70_cali_v3.xdf /bin-in/stock.bin /bin-in/tuned.bin
```

The repo mounts at `/work`, so XDF paths are relative to the repo root. Calibration reads go
somewhere else (`/bin-in`) on purpose: nothing writes into the repo by accident.

The GUI is not in this image — Tk and a display make it a poor fit for a container. Run it
natively with `./run.sh`.

## TunerPro

Why this exists: the XDF format is not publicly documented. For plain tables there is nothing to
disagree about, but the **strided block tables** depend on how a reader turns
`mmedminorstridebits` into a column pitch, and `xdflib`'s formula was derived by matching the
firmware rather than from a specification. If TunerPro resolves those addresses differently, the
same edit made in TunerPro and in our tools lands on **different bytes**. This image runs the real
thing so the question can be answered by observation.

```sh
docker build --platform linux/amd64 -t 8hpe-tunerpro docker/tunerpro
```

The build downloads the free edition from tunerpro.net (Inno Setup, installed silently). TunerPro
is a 32-bit Windows program, so the image is amd64; on Apple silicon enable **Settings → General →
Use Rosetta for x86_64/amd64 emulation** in Docker Desktop or it will crawl.

Drive it by hand over VNC — most reliable, and you can see what you are doing:

```sh
docker run --rm -it -p 5900:5900 \
    -v "$PWD:/work" -v /path/to/reads:/bin-in:ro -v "$PWD/out:/out" \
    8hpe-tunerpro run
# then connect a VNC client to localhost:5900 (no password)
```

On macOS, Finder → Go → Connect to Server → `vnc://localhost:5900` works without installing
anything.

Or capture what it shows, without a VNC client:

```sh
docker run --rm -v "$PWD:/work" -v "$PWD/out:/out" 8hpe-tunerpro shot /out/tunerpro.png
```

Inside the container, `tp-ui` sends input and captures the result, so a session can be driven step
by step:

```sh
tp-ui windows                 # what is on screen
tp-ui key ctrl+o              # File > Open
tp-ui type /work/8hpe70_cali_v3.xdf
tp-ui key Return
tp-ui shot /out/after-open.png
```

### The check that matters

Open `8hpe70_cali_v3.xdf` with a stock E70 read, open **`Upshift lines, char 00: 1>2..5>6`**, and
read the first column. It must be:

```
325 325 325 325 325 450 475 700 725 875 900 1100 1100 1100 1100
```

Those values are confirmed independently by the decompiled firmware readers and by the
per-gear-pair single-curve tables that alias the same flash bytes. If TunerPro shows them,
TunerPro and our tools agree and binaries from either are interchangeable. If it shows anything
else, do not edit the block tables in TunerPro — use the single curves, which carry no strides and
cannot be misread. The full protocol is in
[docs/e70/tunerpro-parity-check.md](../docs/e70/tunerpro-parity-check.md).
