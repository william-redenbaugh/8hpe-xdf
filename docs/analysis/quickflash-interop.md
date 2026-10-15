# 8HPe Transmission Quickflash — what it does, and our interop plan

A functional characterization of the commercial flashing tool this repo
recommends, and how this repo's own tools line up with each step. Everything
here comes from **public information** (the product page, the vendor's cable
notes, this repo's own usage experience) plus analysis of **our own
calibration data**. The product itself was not disassembled, decompiled, or
license-circumvented, and nothing here reproduces its code.

## What the vendor states (facts)

From the product page (v1.10, $49, SKU 8hpqf-1):

- Reads and flashes custom transmission tunes on 8HP/8HPe automatics in
  **E70 and E71**, **Rolls-Royce RR1**, and "some later E84, E89".
- **Reads and resets error codes.**
- **Automatic checksum correction.**
- Unlimited vehicle use; license activated online, tied to one PC
  (Windows 7+, internet required).
- Requires an **FT232RL(q)-chipset cable**; the vendor strongly recommends
  one running **ediabaslib firmware**.

From this repo's own use of it (README): it reads and writes **exactly the
2 MB image** these definitions are addressed against — calibration at
`0x180200`, program area reading back blank (`FF`) — and corrects checksums
at flash time.

## What that implies technically (inference, labelled as such)

- **Transport.** An FT232RL USB-serial cable is the classic BMW "K+DCAN"
  OBD cable. On E7x the EGS (transmission) module is reached over **D-CAN
  (500 kbit/s)** through the OBD port; ediabaslib's cable firmware gives
  reliable BMW-FAST framing over the FTDI chip. So the tool is almost
  certainly speaking BMW's standard diagnostic stack to the EGS — the same
  bus Tool32/EDIABAS uses with `gsb233.prg` — not some proprietary channel.
- **Reading.** The blank (`FF`) program area in reads suggests the tool
  uploads the **calibration region only** (memory-read/upload diagnostic
  services) and pads the rest to produce the uniform 2 MB file, rather than
  dumping the whole flash. That padding is why a calibration-only 512 KB
  file "does not line up" but the 2 MB image always does.
- **Writing.** BMW flash flows over UDS/BMW-FAST follow the standard shape:
  programming diagnostic session → **security access** (seed/key for the
  EGS) → erase of the calibration segment → `RequestDownload` /
  `TransferData` / `TransferExit` → a **checksum/verify routine** before
  reset. "Automatic checksum correction" means the tool fixes the
  calibration's declared checksum(s) in the image before transfer (and/or
  satisfies the controller's verify routine) so the TCU accepts the data.
- **DTC read/reset** is plain diagnostic services on the same session —
  the same jobs Tool32 exposes via `gsb233.prg`.
- **ZB gating.** Flashing is only safe within the matching ZB
  (program `7641033A` / data `A8646497` for ZB 8646496); whether the tool
  enforces this or trusts the user is unknown from public info.

Unknowns that only bench work can settle: the exact security-access
seed/key algorithm, whether one CRC32 or several segment checksums are
verified, the erase/write granularity, and any anti-rollback behaviour.

## The checksum, clean-room

The calibration itself declares a CRC32 at **0x180244** (`cal_declared_crc32`
in the XDF; known tunes rewrite all four bytes). The algorithm and covered
region are not published, so this repo ships
[`tools/xdf_checksum.py`](../../tools/xdf_checksum.py), which **confirms**
them against a known-good bin instead of guessing:

```sh
python3 tools/xdf_checksum.py search your_stock_read.bin   # finds algo+region
python3 tools/xdf_checksum.py verify my_tuned.bin          # recompute vs stored
python3 tools/xdf_checksum.py sign my_tuned.bin -o signed.bin
```

`search` sweeps the common CRC32 variants (standard, Castagnoli, JAMCRC,
MPEG-2, bzip2, POSIX, plus a 32-bit sum) from several plausible start
offsets, comparing the running value at **every byte position** against the
value stored in your stock read — a hit is an (algorithm, start, end) that
reproduces the factory value, and it is saved as `checksum_profile.json`.
The GUI's **Sign bin** button then re-signs edited bins in one click.
Verify any found profile against a **second** known-good bin before trusting
it; if no profile is found (non-contiguous segments, unusual polynomial),
keep flashing with a tool that corrects checksums itself — Quickflash does.

This was implemented from the calibration data alone; it does not reuse or
inspect any vendor code.

## The pipeline this repo supports today

| Step | Tool | Status |
|---|---|---|
| Open XDF + bin | GUI (`./run.sh`) / TunerPro | working |
| Edit tables, bulk sliders, presets | GUI | working |
| Sign (checksum-correct) | GUI **Sign bin** / `xdf_checksum.py` | working once `search` has confirmed the profile against your stock read |
| Flash | **8HPe Quickflash** (or Tool32-based flow) | external, recommended |
| Post-flash re-learn | Tool32 `gsb233.prg`, `steuern_lernfkt_ruecksetzen 0` | documented in README |

In-GUI flashing is deliberately **not enabled**. A D-CAN write path
(python-can / serial K+DCAN, UDS session + security access + download) is
implementable, but an unvalidated TCU flasher is a transmission-bricking
risk; it would need bench validation against a recoverable unit, plus the
security-access algorithm, before it belongs in anyone's workflow. Until
then: edit → sign → save here, flash with Quickflash.
