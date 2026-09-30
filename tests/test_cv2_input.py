# SPDX-License-Identifier: AGPL-3.0-only

"""The only input OpenCV receives is PNG produced by MuPDF.

In the site repository: docs/02-kararlar.md, "Accepted risk: OpenSSL 1.1.1k inside opencv".

The opencv-python-headless wheel bundles FFmpeg (libavformat) and the OpenSSL 1.1.1k it links against. Accepting that
risk rests on one assumption: pdf2docx never hands cv2 a file, a stream or the user's embedded image bytes; it only
passes the PNG encoding of a Pixmap that PyMuPDF rendered from the page (Pixmap.tobytes() defaults to "png") to
cv2.imdecode. The test wraps cv2's decode/read entry points during a real conversion: every buffer passed to imdecode
starts with the PNG signature, and no entry point that opens a file or video is ever called. If a pdf2docx update
changes this path, the test fails and the risk record is reassessed.
"""

import inspect

import cv2
import pymupdf
from pdf2docx.common import algorithm
from pdf2docx.image import ImagesExtractor as images_extractor

from pdfb_convert.word import convert_word

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
# Entry points that read from a file/stream or run FFmpeg: none of them may be called.
FORBIDDEN = [
    "imread",
    "imreadmulti",
    "imreadanimation",
    "imdecodemulti",
    "imdecodeanimation",
    "VideoCapture",
    "haveImageReader",
]


def _mixed_pdf(path, font: str):
    """Text, vector drawings (pdf2docx's detect_svg_contours path) and a rotated image embedded as JPEG."""
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 120, 80), False)
    pix.set_rect(pix.irect, (200, 30, 30))
    pix.set_rect(pymupdf.IRect(10, 10, 60, 40), (20, 20, 220))
    jpeg = pix.tobytes("jpeg")
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_font(fontname="tr", fontfile=font)
    body = "Rapor: çizim ve görsel içeren sayfa."
    page.insert_textbox(pymupdf.Rect(56, 56, 539, 140), body, fontname="tr", fontsize=11)
    # Vector graphics that are not a table: curves, circles and diagonal lines.
    shape = page.new_shape()
    for i in range(6):
        shape.draw_bezier((80 + 40 * i, 400), (100 + 40 * i, 300), (120 + 40 * i, 500), (140 + 40 * i, 400))
        shape.draw_circle((100 + 60 * i, 600), 18)
        shape.draw_line((70 + 50 * i, 700), (110 + 50 * i, 760))
    shape.finish(color=(0, 0, 0), fill=(0.2, 0.6, 0.3), width=1.5)
    shape.commit()
    page.insert_image(pymupdf.Rect(300, 150, 420, 270), stream=jpeg, rotate=90)
    page.insert_image(pymupdf.Rect(80, 150, 200, 230), stream=jpeg)
    doc.save(path)
    doc.close()
    return path


def test_cv2_receives_only_mupdf_png(monkeypatch, tmp_path, tr_font):
    buffers: list[bytes] = []
    forbidden_calls: list[str] = []
    real_imdecode = cv2.imdecode

    def spy_imdecode(buf, flags, *args, **kwargs):
        buffers.append(bytes(memoryview(buf)[:8]))
        return real_imdecode(buf, flags, *args, **kwargs)

    monkeypatch.setattr(cv2, "imdecode", spy_imdecode)
    for name in FORBIDDEN:
        if hasattr(cv2, name):

            def forbid(*_a, _name=name, **_k):
                forbidden_calls.append(_name)
                raise AssertionError(f"cv2.{_name} was called")

            monkeypatch.setattr(cv2, name, forbid)

    src = _mixed_pdf(tmp_path / "mixed.pdf", tr_font)
    result = convert_word(str(src), str(tmp_path / "out.docx"), 100)

    assert result["pages"] == 1
    assert forbidden_calls == []
    # Make sure the test is not vacuous: the conversion passed at least one image to cv2.
    assert buffers, "pdf2docx never called cv2.imdecode; the fixture does not trigger the svg/rotation path"
    assert all(b == PNG_SIGNATURE for b in buffers), buffers


def test_pdf2docx_calls_cv2_by_attribute():
    # The wrapping works because pdf2docx calls cv2 through the module (cv.imdecode); a directly imported name
    # (from cv2 import imdecode) would bypass it. The buffer passed to imdecode is the output of Pixmap.tobytes()
    # (default "png").
    for module in (images_extractor, algorithm):
        source = inspect.getsource(module)
        assert "from cv2 import" not in source, module.__name__
    source = inspect.getsource(images_extractor)
    assert "cv.imdecode(np.frombuffer(img_byte, np.uint8)" in source
    assert "img_byte = pixmap.tobytes()" in source
