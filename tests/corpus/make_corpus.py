# SPDX-License-Identifier: AGPL-3.0-only

"""Synthetic PDF corpus for the unit tests (spec §11.3): PDF → Word and (2c) PDF → Excel criteria. The benchmark PDFs
(bench-20p-tablo, tablo-100s) come from the shared generator in the pdfbirlestirme monorepo:
infra/office/corpus/make_corpus.py --pdfs.
Documents are drawn with PyMuPDF; there is no real personal data. Output: tests/corpus/out/ (not committed).

    python tests/corpus/make_corpus.py <output directory> <ttf>
"""

import sys
from pathlib import Path

import pymupdf

A4 = (595, 842)
HEAD = ["Sıra", "Ürün", "Miktar", "Birim Fiyat", "Tutar"]
ITEMS = ["Kâğıt", "Kalem", "Dosya", "Zımba", "Toner", "Klasör", "Şeffaf Poşet", "Mühür"]


def _page(doc: pymupdf.Document, font: str) -> pymupdf.Page:
    page = doc.new_page(width=A4[0], height=A4[1])
    page.insert_font(fontname="tr", fontfile=font)
    return page


def _text(page: pymupdf.Page, rect: tuple[float, float, float, float], body: str, size: float = 10) -> None:
    page.insert_textbox(pymupdf.Rect(*rect), body, fontname="tr", fontsize=size)


def _table(page: pymupdf.Page, top: float, rows: int, seed: int) -> None:
    widths = [40, 180, 70, 100, 100]
    x0, h = 56, 18
    for r in range(rows + 1):
        y = top + r * h
        x = x0
        for c, w in enumerate(widths):
            page.draw_rect(pymupdf.Rect(x, y, x + w, y + h), color=(0, 0, 0), width=0.6)
            if r == 0:
                cell = HEAD[c]
            else:
                qty = (seed + r) % 9 + 1
                price = 12.5 * ((seed + r * 7) % 40 + 1)
                cell = [str(r), ITEMS[(seed + r) % len(ITEMS)], str(qty), _tl(price), _tl(qty * price)][c]
            page.insert_text((x + 3, y + 13), cell, fontname="tr", fontsize=9)
            x += w


def _tl(v: float) -> str:
    whole, frac = f"{v:,.2f}".split(".")
    return whole.replace(",", ".") + "," + frac + " ₺"


def _save(doc: pymupdf.Document, path: Path) -> Path:
    doc.save(path, garbage=3, deflate=True)
    doc.close()
    return path


# PDF → Excel (2c): ruled tables; Turkish numbers, dates, currency and formula injection attempts.
EXCEL_INVOICE = [
    ["Kalem", "Miktar", "Birim Fiyat", "Tutar", "Tarih"],
    ["Danışmanlık hizmeti", "1.250", "₺1.234,56", "1.543.200,00 TL", "25.09.2026"],
    ["Yazılım lisansı", "3", "₺999,90", "2.999,70 TL", "01.10.2026"],
    ["İndirim", "1", "-₺150,00", "-150,00 TL", "01.10.2026"],
    ["KDV oranı", "", "%20", "", ""],
    ["=TOPLA(D2:D4)", "+90 212 555 00 00", "00123", "@komut", "31.02.2026"],
]


def _grid(page: pymupdf.Page, top: float, rows: list[list[str]], col_w: float = 105) -> None:
    h = 22
    for r, row in enumerate(rows):
        for c, text in enumerate(row):
            rect = pymupdf.Rect(40 + c * col_w, top + r * h, 40 + (c + 1) * col_w, top + (r + 1) * h)
            page.draw_rect(rect, color=(0, 0, 0), width=0.6)
            page.insert_textbox(rect + (3, 5, -3, -2), text, fontname="tr", fontsize=8)


def make_excel_invoice(path: Path, font: str) -> Path:
    doc = pymupdf.open()
    p1 = _page(doc, font)
    _text(p1, (40, 40, 555, 80), "Fatura dökümü — Çağ Ltd. Şti.", 12)
    _grid(p1, 90, EXCEL_INVOICE)
    _grid(p1, 300, [["Ay", "Gelir"], ["Ocak", "12.500,00"], ["Şubat", "1.234"]], col_w=120)
    p2 = doc.new_page(width=842, height=595)  # landscape page
    p2.insert_font(fontname="tr", fontfile=font)
    _text(p2, (40, 40, 800, 80), "Ek tablo: bordro özeti", 12)
    payroll = [["Personel", "Brüt", "Net"], ["Ayşe Yılmaz", "45.000,00", "33.975,00"]]
    _grid(p2, 90, [*payroll, ["İsmail Öztürk", "38.500,50", "29.120,25"]])
    doc.set_metadata({})
    return _save(doc, path)


def make_excel_no_tables(path: Path, font: str) -> Path:
    doc = pymupdf.open()
    for i in range(2):
        page = _page(doc, font)
        body = f"Dilekçe sayfa {i + 1}\nSayın Müdürlüğe,\nGereğinin yapılmasını arz ederim.\n"
        _text(page, (50, 50, 545, 800), body + '=HYPERLINK("http://örnek")\n1.234,56', 11)
    doc.set_metadata({})
    return _save(doc, path)


def build(out: Path, font: str) -> dict[str, Path]:
    out.mkdir(parents=True, exist_ok=True)
    files: dict[str, Path] = {}

    doc = pymupdf.open()
    page = _page(doc, font)
    _text(
        page,
        (56, 56, 539, 786),
        "T.C.\nİSTANBUL ANADOLU ... MAHKEMESİ'NE\n\nDAVACI: Ayşe Yılmaz\nKONU: Işıklı Sokak'taki taşınmazın "
        "kira bedelinin tespiti hakkında dilekçemdir.\n\nAçıklamalar: Öğrenci yurdu, çağrı, ığdır, şükür, İzmir, "
        "Ğ, Ü, Ş, Ö, Ç. Toplam ₺12.345,67.\n\nSaygılarımla.",
        11,
    )
    files["petition"] = _save(doc, out / "petition.pdf")

    doc = pymupdf.open()
    page = _page(doc, font)
    _text(page, (56, 40, 539, 90), "FATURA — Örnek Kırtasiye Ltd. Şti.", 13)
    _table(page, 100, 8, 1)
    files["invoice-table"] = _save(doc, out / "invoice-table.pdf")

    doc = pymupdf.open()
    page = _page(doc, font)
    col = "Bülten sütunu: Türkçe haber metni, şehir, çiçek, ağaç, ölçü. " * 12
    _text(page, (40, 56, 290, 786), col, 9)
    _text(page, (305, 56, 555, 786), col, 9)
    files["newsletter-columns"] = _save(doc, out / "newsletter-columns.pdf")

    for name, pages, text_every in (("scanned", 3, 0), ("mixed-scanned", 20, 10)):
        doc = pymupdf.open()
        pix = pymupdf.Pixmap(pymupdf.csGRAY, pymupdf.IRect(0, 0, 300, 420), False)
        pix.set_rect(pix.irect, (230,))  # the colour is a sequence (gray: a single component)
        png = pix.tobytes("png")
        for i in range(pages):
            page = _page(doc, font)
            page.insert_image(page.rect, stream=png)
            if text_every and i % text_every == 0:
                _text(page, (56, 56, 539, 200), "Bu sayfada gerçek metin katmanı var: ödeme, şirket, İstanbul.", 11)
        files[name] = _save(doc, out / f"{name}.pdf")

    for name, pages in (("table-100p", 100),):
        doc = pymupdf.open()
        for i in range(pages):
            page = _page(doc, font)
            _text(page, (56, 40, 539, 90), f"Hesap dökümü — sayfa {i + 1}", 12)
            _table(page, 100, 30, i)
        files[name] = _save(doc, out / f"{name}.pdf")
    files["excel-invoice"] = make_excel_invoice(out / "excel-invoice.pdf", font)
    files["excel-no-tables"] = make_excel_no_tables(out / "excel-no-tables.pdf", font)
    return files


if __name__ == "__main__":
    for key, path in build(Path(sys.argv[1]), sys.argv[2]).items():
        print(key, path)
