# pdf-convert

The PDF to Word and PDF to Excel converter that runs on [pdfbirlestirme.com](https://pdfbirlestirme.com), a free
online PDF toolkit.

This repository is the complete source code of the converter as it runs on the site. It is published under the GNU
Affero General Public License v3.0 (§13: users who interact with the program over a network can get its source).
It powers these tools:

- [PDF to Word](https://pdfbirlestirme.com/pdf-word-cevirme): editable DOCX (`word` mode)
- [PDF to Excel](https://pdfbirlestirme.com/pdf-excel-cevirme): XLSX with one worksheet per ruled table (`excel` mode)

The website and its API are separate, proprietary programs. They run this converter as a separate process from the
command line and exchange data with it only through files. The "Kaynak kodu" (source code) link on the tool pages,
on the result screen and on the site's [licenses page](https://pdfbirlestirme.com/lisanslar) points to the exact
commit of this repository that is running in production.

## License

Copyright (C) 2026 Motino, LLC

GNU Affero General Public License v3.0 only (`LICENSE`, the gnu.org text byte for byte; sha256
`0d96a4ff68ad6d4b6f1f30f713b18d5184912ba8dd389f86aa7710db079abcb0`). The licenses of the dependencies ship with
the packages pinned in `requirements.lock`: PyMuPDF/MuPDF are AGPL-3.0; pdf2docx, python-docx and openpyxl are MIT;
et-xmlfile is MIT and carries code taken from the Python standard library under PSF-2.0.

## Installation (Ubuntu 24.04, Python 3.12)

```bash
python3 -m venv venv
# 1) First the pip that performs the installation, from its hashed lock:
venv/bin/python -m pip install --require-hashes --no-deps --only-binary=:all: -r requirements-pip.lock
venv/bin/python -m pip --version | grep -q '^pip 26\.2\.1 ' || { echo "pip version does not match the lock" >&2; exit 1; }
# 2) Then the remaining packages, with the pinned pip:
venv/bin/python -m pip install --require-hashes --no-deps --only-binary=:all: -r requirements.lock
```

## Usage

```bash
PYTHONPATH=venv/lib/python3.12/site-packages:src python3 -m pdfb_convert word --in input.pdf --out output.docx --max-pages 100
PYTHONPATH=venv/lib/python3.12/site-packages:src python3 -m pdfb_convert excel --in input.pdf --out output.xlsx --max-pages 100
```

On success a single line of JSON is written to stdout: `{"pages":3,"tables":1}`.

In Excel output every ruled table is a separate worksheet named "Sayfa N - Tablo M" ("Page N - Table M"; the site
is in Turkish). The text of all pages, in page order, is on the last worksheet, "Metin" ("Text"). `tables` is 0 when
no table was found in the PDF. Turkish-formatted numbers, percentages, amounts in lira and dates (for example
`1.234,56`, `%12,5`, `₺99,90`, `25.09.2026`) become real numeric and date cells; no cell is ever a formula.

| Exit code | Meaning |
|---|---|
| 0 | Success |
| 10 | Scanned PDF (at least 80% of the pages have fewer than 20 characters of text) |
| 11 | Page limit exceeded |
| 12 | Unreadable file |
| 13 | Encrypted PDF |
| Other | Conversion failed |

## Development

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes --no-deps --only-binary=:all: -r requirements-pip.lock
.venv/bin/python -m pip --version | grep -q '^pip 26\.2\.1 '
.venv/bin/python -m pip install --require-hashes --no-deps --only-binary=:all: -r requirements.lock -r requirements-dev.lock
.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/pytest
.venv/bin/pip-audit --strict --disable-pip --no-deps -r requirements.lock -r requirements-dev.lock
```

The Turkish text tests need a font that covers every Turkish glyph (including ₺). Arial on macOS has no ₺, so these
tests are skipped there. Point `PDFB_TEST_FONT` at DejaVuSans.ttf, or run the tests in the container
(`scripts/test-in-container.sh`).

`scripts/test-in-container.sh` only works inside the main (pdfbirlestirme) monorepo: the test image is built by
`infra/office/test-image/run.sh` there, and that folder is not part of this mirror. In this repository, use the
commands above.

The lock files are generated with `scripts/lock.sh` (Docker, ubuntu:24.04).
