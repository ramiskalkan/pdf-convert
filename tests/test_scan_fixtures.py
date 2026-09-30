# SPDX-License-Identifier: AGPL-3.0-only

"""Shared fixture set: the PyMuPDF decision.

In the pdfbirlestirme monorepo, pdf.js (packages/engine/test/render/text-stats-fixtures.test.ts) and pdftotext
(2c: apps/api/test/integration/pdf-text-stats-fixtures.int.test.ts) read the same files and check the same decision.
"""

import json
import math
from pathlib import Path

import pymupdf
import pytest

from pdfb_convert.scan import SCANNED_RULE, is_scanned, non_space_chars, page_char_counts

HERE = Path(__file__).parent / "fixtures" / "scan"
CASES = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES["pdfs"], ids=lambda c: c["file"])
def test_pymupdf_server_decision(case):
    with pymupdf.open(HERE / case["file"]) as doc:
        counts = page_char_counts(doc)
    assert len(counts) == len(case["pages"])
    for kind, count in zip(case["pages"], counts, strict=True):
        if kind == "T":
            assert count >= 20
        else:
            assert count == CASES["pageChars"][kind], (case["file"], kind)
    assert is_scanned(counts) is case["server"]


@pytest.mark.parametrize("case", CASES["pdfs"], ids=lambda c: c["file"])
def test_browser_never_stricter_than_server(case):
    # Whatever the browser rejects, the server rejects too (spec §5.2: the server has the final say).
    assert not (case["browser"] and not case["server"])


def sample_indices(page_count: int, maximum: int) -> list[int]:
    """Exact copy of sampleIndices in packages/engine/src/render/text-stats.ts (evenly spaced, first and last kept)."""
    if page_count <= 0 or maximum <= 0:
        return []
    if page_count <= maximum:
        return list(range(page_count))
    if maximum == 1:
        return [0]
    out: list[int] = []
    for k in range(maximum):
        i = (k * (page_count - 1)) // (maximum - 1)
        if not out or out[-1] != i:
            out.append(i)
    return out


SCAN_SAMPLE_LIMIT = 50


def scanned_need(page_count: int) -> int:
    """Exact copy of text-stats.ts scannedNeed: the minimum number of low-text pages for the server to reject."""
    return math.ceil(SCANNED_RULE[1] * page_count) if page_count > 0 else 0


def scan_sample_size(page_count: int, sample_max: int) -> int:
    """Exact copy of text-stats.ts scanSampleSize: as many pages as needed, at most 50; 0 if more are needed."""
    limit = min(sample_max, SCAN_SAMPLE_LIMIT) if sample_max > 0 else SCAN_SAMPLE_LIMIT
    need = scanned_need(page_count)
    return need if need <= limit else 0


def browser_rejects(page_count: int, sampled: int, low_text: int) -> bool:
    """Exact copy of text-stats.ts isScannedSample."""
    return sampled > 0 and low_text == sampled and low_text >= scanned_need(page_count)


def test_sample_indices_match_engine():
    assert sample_indices(25, 12) == [0, 2, 4, 6, 8, 10, 13, 15, 17, 19, 21, 24]
    assert sample_indices(3, 12) == [0, 1, 2]
    assert sample_indices(5, 4) == [0, 1, 2, 4]


def test_sample_size_matches_engine():
    # Same table as packages/engine/test/render/text-stats.test.ts
    table = {0: 0, 1: 1, 3: 3, 5: 4, 12: 10, 15: 12, 16: 13, 20: 16, 62: 50, 63: 0, 100: 0}
    assert {n: scan_sample_size(n, 50) for n in table} == table
    assert CASES["sampleMax"] == SCAN_SAMPLE_LIMIT


def test_scanned_need_is_server_threshold():
    for n in range(1, 201):
        need = scanned_need(n)
        assert is_scanned([0] * need + [100] * (n - need))
        assert not is_scanned([0] * (need - 1) + [100] * (n - need + 1))


def test_browser_reject_implies_server_reject_bruteforce():
    # Worst case: every page that is not sampled has text.
    for n in range(0, 201):
        for sample_max in (0, 1, 12, 16, 50, 500):
            idx = sample_indices(n, scan_sample_size(n, sample_max))
            assert len(idx) <= SCAN_SAMPLE_LIMIT
            for low_sampled in range(len(idx) + 1):
                if browser_rejects(n, len(idx), low_sampled):
                    assert is_scanned([0] * low_sampled + [100] * (n - low_sampled)), (n, sample_max, low_sampled)


@pytest.mark.parametrize("case", CASES["pdfs"], ids=lambda c: c["file"])
def test_browser_decision_follows_sample(case):
    # The browser samples as many pages as needed and rejects only if ALL sampled pages are low-text.
    n = len(case["pages"])
    idx = sample_indices(n, scan_sample_size(n, CASES["sampleMax"]))
    low = sum(1 for i in idx if case["pages"][i] != "T" and CASES["pageChars"][case["pages"][i]] < 20)
    assert browser_rejects(n, len(idx), low) is case["browser"]


def test_long_mixed_pdf_passes_browser_but_not_server():
    # Mixed PDF longer than 12 pages: a text page falls into the sample, the browser passes it, the server rejects it.
    long_mixed = [c for c in CASES["pdfs"] if len(c["pages"]) > 12 and not c["browser"] and c["server"]]
    assert long_mixed, "no mixed PDF longer than 12 pages that the browser passes and the server rejects"


def test_counterexample_server_accepts_browser_passes():
    # Counterexample from spec §5.2: the old 12-page sample is scanned, most other pages have text; both sides accept.
    case = next(c for c in CASES["pdfs"] if c["file"] == "counterexample-20p.pdf")
    old = set(sample_indices(20, 12))
    assert all(case["pages"][i] == "I" for i in old)
    assert (case["server"], case["browser"]) == (False, False)


@pytest.mark.parametrize("row", CASES["whitespace"], ids=lambda r: repr(r["text"]))
def test_whitespace_table(row):
    assert non_space_chars(row["text"]) == row["count"]
