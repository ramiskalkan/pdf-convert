#!/usr/bin/env bash
# Python gates (spec §4.12): ruff, pytest (including slow tests), pip-audit. Runs in the same image as the server; if
# there is no image, the release script does not continue.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
# Single image (U19): the tag comes from run.sh, which builds the image if missing. Without Docker run.sh exits with 3
# and the release stops.
IMAGE="$("$ROOT/infra/office/test-image/run.sh" tag)"
# The Python license texts on /lisanslar are extracted again from the wheels and compared byte for byte with the
# site's copy. Without that folder (a standalone clone of the AGPL mirror) the comparison is skipped.
LICDIR="$ROOT/apps/pdfbirlestirme/src/data/licenses-pypi"
LICMOUNT=(); [ -d "$LICDIR" ] && LICMOUNT=(-v "$LICDIR":/site-licenses:ro)
docker run --rm --platform linux/amd64 --network=bridge -v "$ROOT/services/pdf-convert":/src:ro ${LICMOUNT[@]+"${LICMOUNT[@]}"} -w /tmp "$IMAGE" bash -euc '
  # Local development leftovers (.venv, caches) are not copied.
  mkdir /tmp/pc && tar -C /src --exclude=./.venv --exclude=__pycache__ --exclude=.pytest_cache --exclude=.ruff_cache \
    --exclude=./tests/corpus/out -cf - . | tar -C /tmp/pc -xf - && cd /tmp/pc
  V=/opt/pdfb-office/venv/bin
  # Separate lines: with set -e, a failing "a" in "a && b" does not stop the script (a lint error would be swallowed).
  $V/ruff check .
  $V/ruff format --check .
  PDFB_TEST_FONT=$(find /opt/pdfb-fonts /usr/local/share/pdfb-office/fonts -name DejaVuSans.ttf 2>/dev/null | head -1) \
    $V/pytest -m "slow or not slow"
  # --disable-pip --no-deps: pip-audit does not create a temporary venv to install packages; the locks are complete
  # and hashed.
  $V/pip-audit --strict --disable-pip --no-deps -r requirements.lock -r requirements-dev.lock
  if [ -d /site-licenses ]; then
    # _upstream/: the tagged upstream copy of a license whose full text is not in the wheel (sha256 is checked by a
    # site test, licenses-python.test.ts).
    $V/python scripts/extract_licenses.py /opt/pdfb-office/venv/lib/python3.12/site-packages requirements.lock /tmp/lic >/dev/null
    diff -r -x _upstream /tmp/lic /site-licenses
    echo "license texts: identical to the wheels"
  fi
'
