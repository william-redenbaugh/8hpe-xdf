# The XDF command-line tools, pinned to a known-good Python.
#
# Useful for running them identically on macOS, Linux and Windows (and in CI),
# and for sidestepping a broken system Python - notably Homebrew builds whose
# pyexpat cannot parse XML, which is why xdflib carries its own fallback parser.
#
# No firmware, calibration data or XDF ships in the image: mount the repo.
#
#   docker build -t 8hpe-tools docker/tools
#   docker run --rm -v "$PWD:/work" 8hpe-tools xdf_ls.py 8hpe70_cali_v3.xdf --categories
#   docker run --rm -v "$PWD:/work" -v /path/to/reads:/bin-in 8hpe-tools \
#       xdf_verify.py 8hpe70_cali_v3.xdf /bin-in/stock.bin /bin-in/tuned.bin
FROM python:3.12-slim-bookworm

# The GUI (xdf_gui.py) is deliberately not supported here - it needs Tk and a
# display; run it natively with ./run.sh instead.
COPY tools/ /opt/8hpe/tools/

RUN find /opt/8hpe/tools -name '*.py' -exec chmod +x {} + \
 && rm -rf /opt/8hpe/tools/__pycache__

ENV PYTHONPATH=/opt/8hpe/tools \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/opt/8hpe/tools:$PATH

WORKDIR /work
VOLUME ["/work", "/bin-in", "/out"]

# Run any tool by name: `xdf_show.py ...`, or drop to `python3`/`bash`.
ENTRYPOINT ["python3"]
CMD ["/opt/8hpe/tools/xdf_ls.py", "--help"]
