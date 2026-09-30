# SPDX-License-Identifier: AGPL-3.0-only

"""Generates the shared scanned-PDF fixture set: one PDF for each row in tests/fixtures/scan/cases.json.

    python scripts/make_scan_fixtures.py <ttf> [file.pdf …]

If file names are given, only those are generated; the bytes of the other committed PDFs do not change.

The outputs are committed; the pdf.js (packages/engine) and pdftotext (apps/api) tests in the pdfbirlestirme monorepo
read the same bytes.
"""

import json
import sys
from pathlib import Path

import pymupdf

HERE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "scan"
LONG = "Bu sayfada gerçek metin katmanı var: ödeme, şirket, İstanbul, çağrı, ığdır."
N20 = "ğüşöç\u00a0İıĞÜŞ\u2009ÖÇabc\u202fdefgh"  # 20 non-whitespace characters
N19 = N20[:-1]


def _image() -> bytes:
    pix = pymupdf.Pixmap(pymupdf.csGRAY, pymupdf.IRect(0, 0, 200, 280), False)
    pix.set_rect(pix.irect, (235,))  # the colour is a sequence (grey: a single component)
    return pix.tobytes("png")


def build(font: str, only: list[str] | None = None) -> list[Path]:
    cases = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
    png = _image()
    written = []
    for case in cases["pdfs"]:
        if only and case["file"] not in only:
            continue
        doc = pymupdf.open()
        for kind in case["pages"]:
            page = doc.new_page(width=595, height=842)
            if kind == "I":
                page.insert_image(page.rect, stream=png)
                continue
            page.insert_font(fontname="tr", fontfile=font)
            body = {"T": LONG, "N19": N19, "N20": N20}[kind]
            page.insert_text((56, 90), body, fontname="tr", fontsize=12)
        doc.subset_fonts()  # embedding full DejaVu makes each file ~400 KB; subsetting does not change text extraction
        doc.set_metadata({})
        path = HERE / case["file"]
        doc.save(path, garbage=4, deflate=True, no_new_id=True)
        doc.close()
        written.append(path)
    return written


if __name__ == "__main__":
    for p in build(sys.argv[1], sys.argv[2:] or None):
        print(p.name)
