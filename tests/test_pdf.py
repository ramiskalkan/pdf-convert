# SPDX-License-Identifier: AGPL-3.0-only

import pymupdf
import pytest

from conftest import encrypted_pdf
from pdfb_convert.errors import EncryptedPdf, TooManyPages, Unreadable
from pdfb_convert.pdf import open_pdf


def test_opens_valid_pdf(make_text_pdf):
    doc = open_pdf(str(make_text_pdf(["merhaba dünya"] * 2)), max_pages=100)
    try:
        assert doc.page_count == 2
    finally:
        doc.close()


def test_page_limit(make_text_pdf):
    path = make_text_pdf(["sayfa"] * 3)
    with pytest.raises(TooManyPages):
        open_pdf(str(path), max_pages=2)


def test_truncated_pdf_is_unreadable(tmp_path, make_text_pdf):
    good = make_text_pdf(["kesik belge"])
    cut = tmp_path / "truncated.pdf"
    cut.write_bytes(good.read_bytes()[:60])
    with pytest.raises(Unreadable):
        open_pdf(str(cut), max_pages=100)


def test_not_a_pdf_is_unreadable(tmp_path):
    junk = tmp_path / "x.pdf"
    junk.write_bytes(b"PK\x03\x04 this is not a pdf")
    with pytest.raises(Unreadable):
        open_pdf(str(junk), max_pages=100)


def test_zero_pages_is_unreadable(tmp_path):
    empty = tmp_path / "empty.pdf"
    empty.write_bytes(
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[]/Count 0>>endobj\n"
        b"trailer<</Root 1 0 R>>\n%%EOF\n"
    )
    with pytest.raises(Unreadable):
        open_pdf(str(empty), max_pages=100)


def _encrypted(tmp_path, make_text_pdf, user_pw: str):
    return encrypted_pdf(make_text_pdf(["şifreli"]), tmp_path / "encrypted.pdf", user_pw)


@pytest.mark.parametrize("user_pw", ["secret", ""])
def test_encrypted_pdf(tmp_path, make_text_pdf, user_pw):
    # User-password or owner-only encryption: the browser sends the body decrypted, so an encrypted one is
    # ENCRYPTED_PDF.
    with pytest.raises(EncryptedPdf):
        open_pdf(str(_encrypted(tmp_path, make_text_pdf, user_pw)), max_pages=100)


def test_owner_only_pdf_is_detected_from_trailer(tmp_path, make_text_pdf):
    # PyMuPDF opens an owner-only encrypted PDF on its own with an empty password: needs_pass is 0 and is_encrypted is
    # False. So encryption detection relies on the /Encrypt key in the trailer, not on those two flags.
    out = _encrypted(tmp_path, make_text_pdf, "")
    with pymupdf.open(out) as doc:
        assert not doc.needs_pass
        assert doc.xref_get_key(-1, "Encrypt")[0] != "null"
    with pytest.raises(EncryptedPdf):
        open_pdf(str(out), max_pages=100)


def test_lying_page_count_is_unreadable(make_broken_tree):
    # /Count 1000000 but a single page: MuPDF fails after opening (while reading the page count); must be 12, not 1.
    with pytest.raises(Unreadable):
        open_pdf(str(make_broken_tree("lying-count")), max_pages=100)
