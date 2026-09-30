# SPDX-License-Identifier: AGPL-3.0-only

import pymupdf
import pytest

from pdfb_convert.scan import SCANNED_RULE, is_scanned, non_space_chars, page_char_counts


def test_rule_matches_contract():
    # Same as roadmap §C/§E and SCANNED_RULE in packages/engine/src/render/text-stats.ts (the engine test checks it
    # too).
    assert SCANNED_RULE == (20, 0.8)


@pytest.mark.parametrize(
    ("counts", "expected"),
    [
        ([], True),
        ([0], True),
        ([19], True),
        ([20], False),
        ([0, 0, 0, 0, 500], True),  # 4/5 = 80% low-text → scanned
        ([0, 0, 0, 500, 500], False),  # 3/5 = 60%
        ([0] * 79 + [100] * 21, False),  # 79%
        ([0] * 80 + [100] * 20, True),  # exactly the 80% boundary
    ],
)
def test_is_scanned_threshold(counts, expected):
    assert is_scanned(counts) is expected


def test_counts_ignore_whitespace(make_text_pdf):
    path = make_text_pdf(["a b\tc\nd " + " " * 50, ""])
    with pymupdf.open(path) as doc:
        assert page_char_counts(doc) == [4, 0]


def test_whitespace_class_is_explicit_not_isspace():
    # str.isspace() and JS /\s/u are different sets; neither is used (Global Constraints "Whitespace set").
    assert non_space_chars("\u00a0\u2009\u202f\u3000\u200b\ufeff\u0085\t\n\x0b\f\r ") == 0
    assert non_space_chars("\x1c\x1d\x1e\x1f") == 4  # isspace() says True; not whitespace in our set
    assert non_space_chars("ğüşöçİı₺") == 8


def test_image_only_pdf_is_scanned(make_image_pdf):
    with pymupdf.open(make_image_pdf(3)) as doc:
        assert is_scanned(page_char_counts(doc))
