# SPDX-License-Identifier: AGPL-3.0-only

"""Test PDFs are generated here with PyMuPDF (no samples/ and no personal data)."""

import os
from pathlib import Path

import pymupdf
import pytest

# PDFs that open fine but have a broken page tree (review I2): MuPDF raises later, while pages are read.
BROKEN_TREES = {
    "page-tree-cycle": (
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[2 0 R]/Count 1>>endobj\n"
        b"trailer<</Root 1 0 R>>\n%%EOF\n"
    ),
    "lying-count": (
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1000000>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]>>endobj\n"
        b"trailer<</Root 1 0 R>>\n%%EOF\n"
    ),
}
TR_TEXT = "Dilekçe: Işık, ğüşöç İĞÜŞÖÇ ı i ₺1.234,56 tutarında ödeme."
FONT_CANDIDATES = [
    os.environ.get("PDFB_TEST_FONT", ""),
    "/opt/pdfb-fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/local/share/pdfb-office/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
]


def _covers_tr_text(path: str) -> bool:
    # E.g. macOS Arial has no ₺: a missing glyph is silently dropped and tests fail in the wrong place.
    font = pymupdf.Font(fontfile=path)
    return all(font.has_glyph(ord(ch)) for ch in TR_TEXT + "İkinci sayfa: çğıöşü" if not ch.isspace())


@pytest.fixture(scope="session")
def tr_font() -> str:
    for candidate in FONT_CANDIDATES:
        if candidate and Path(candidate).is_file() and _covers_tr_text(candidate):
            return candidate
    if os.environ.get("PDFB_REQUIRE_FONT") == "1":
        pytest.fail("No font with Turkish glyphs found (the container must provide the dedicated font directory)")
    pytest.skip("No font with Turkish glyphs available")


def text_pdf(path: Path, font: str, pages: list[str]) -> Path:
    doc = pymupdf.open()
    for body in pages:
        page = doc.new_page(width=595, height=842)
        page.insert_font(fontname="tr", fontfile=font)
        if body:
            page.insert_textbox(pymupdf.Rect(56, 56, 539, 786), body, fontname="tr", fontsize=11)
    doc.save(path)
    doc.close()
    return path


def image_only_pdf(path: Path, pages: int) -> Path:
    """Imitates a scanned document: each page holds only a raster image, no text layer."""
    pix = pymupdf.Pixmap(pymupdf.csGRAY, pymupdf.IRect(0, 0, 200, 280), False)
    pix.set_rect(pix.irect, (235,))  # the colour is a sequence (gray: a single component)
    png = pix.tobytes("png")
    doc = pymupdf.open()
    for _ in range(pages):
        page = doc.new_page(width=595, height=842)
        page.insert_image(page.rect, stream=png)
    doc.save(path)
    doc.close()
    return path


@pytest.fixture
def make_text_pdf(tmp_path, tr_font):
    def make(pages: list[str], name: str = "input.pdf") -> Path:
        return text_pdf(tmp_path / name, tr_font, pages)

    return make


def encrypted_pdf(src: Path, out: Path, user_pw: str) -> Path:
    with pymupdf.open(src) as doc:
        doc.save(out, encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw=user_pw)
    return out


@pytest.fixture
def make_broken_tree(tmp_path):
    def make(name: str) -> Path:
        path = tmp_path / f"{name}.pdf"
        path.write_bytes(BROKEN_TREES[name])
        return path

    return make


@pytest.fixture
def make_image_pdf(tmp_path):
    def make(pages: int, name: str = "scan.pdf") -> Path:
        return image_only_pdf(tmp_path / name, pages)

    return make
