# SPDX-License-Identifier: AGPL-3.0-only

"""Opens a PDF safely. Encrypted, corrupt, empty and over-limit documents are rejected with the contract's errors."""

import pymupdf

from pdfb_convert.errors import ConvertError, EncryptedPdf, TooManyPages, Unreadable

# MuPDF errors: FileDataError/RuntimeError in the classic wrapper, subclasses of mupdf.FzErrorBase in the new bindings
# (e.g. FzErrorFormat). Both mean "the file could not be read".
MUPDF_ERRORS = (pymupdf.FileDataError, pymupdf.mupdf.FzErrorBase, RuntimeError, ValueError)


def open_pdf(path: str, max_pages: int) -> pymupdf.Document:
    try:
        doc = pymupdf.open(path, filetype="pdf")
    except MUPDF_ERRORS as exc:
        raise Unreadable() from exc
    ok = False
    try:
        # A PDF with only an owner password opens by itself with the empty password (needs_pass/is_encrypted become
        # False); the /Encrypt key in the trailer and the encryption entry in the metadata are still visible.
        encrypt_ref = doc.xref_get_key(-1, "Encrypt")[0] != "null" if doc.is_pdf else False
        if doc.needs_pass or doc.is_encrypted or encrypt_ref or (doc.metadata or {}).get("encryption"):
            raise EncryptedPdf()
        if not doc.is_pdf or doc.page_count == 0:
            raise Unreadable()
        if doc.page_count > max_pages:
            raise TooManyPages()
        ok = True
        return doc
    except (ConvertError, MemoryError):
        raise
    except Exception as exc:  # noqa: BLE001 - a MuPDF error raised after opening (e.g. a lying /Count) is unreadable
        raise Unreadable() from exc
    finally:
        if not ok:
            doc.close()
