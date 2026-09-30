#!/usr/bin/env bash
# Generates the lock files in the same environment as the server (ubuntu:24.04, Python 3.12, x86_64). The hashes cover
# all distributions on PyPI; installation accepts wheels only (--only-binary=:all:).
set -euo pipefail
cd "$(dirname "$0")/.."
# pip-compile itself is installed from the hashed lock too (pip first, then requirements-dev.lock; wheels only).
# Chicken and egg: requirements-dev.lock also contains the pip-tools that generates it. If there is no lock yet (first
# setup), pip-tools is installed once with a version pin but without hashes. When upgrading pip-tools, run the script
# twice: the first run generates the new lock with the old pip-tools, the second verifies it with the new pip-tools.
docker run --rm --platform linux/amd64 -v "$PWD":/src -w /src ubuntu:24.04 bash -euc '
  apt-get update -qq && apt-get install -y -qq python3-venv >/dev/null
  python3 -m venv /tmp/v
  if [ -f requirements-dev.lock ]; then
    /tmp/v/bin/python -m pip install -q --require-hashes --no-deps --only-binary=:all: -r requirements-pip.lock
    /tmp/v/bin/python -m pip install -q --require-hashes --no-deps --only-binary=:all: -r requirements-dev.lock
  else
    /tmp/v/bin/pip install -q pip-tools==7.6.1
  fi
  /tmp/v/bin/pip-compile -q --generate-hashes --allow-unsafe --strip-extras --no-emit-index-url -o requirements.lock requirements.in
  /tmp/v/bin/pip-compile -q --generate-hashes --allow-unsafe --strip-extras --no-emit-index-url -o requirements-dev.lock requirements-dev.in
'
grep -q '^pip==26.2.1' requirements.lock
grep -c -- '--hash=sha256:' requirements.lock >/dev/null
# The pip block alone, for the first installation stage (including the hash lines continued with a trailing "\").
awk '/^pip==/{p=1} p{print; if ($0 !~ /\\$/) exit}' requirements.lock > requirements-pip.lock
grep -q '^pip==26.2.1' requirements-pip.lock && grep -q -- '--hash=sha256:' requirements-pip.lock
echo "lock files are up to date"
