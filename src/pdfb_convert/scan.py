# SPDX-License-Identifier: AGPL-3.0-only

"""Scanned PDF threshold (spec §4.5). The server-side safeguard behind the browser pre-check
(packages/engine/src/render/text-stats.ts in the pdfbirlestirme monorepo); the values on both sides must stay equal.
"""

import re
from collections.abc import Sequence

import pymupdf

# (minimum non-whitespace characters per page, ratio of low-text pages)
SCANNED_RULE: tuple[int, float] = (20, 0.8)

# The SINGLE source of the whitespace set. packages/engine/src/render/text-stats.ts and apps/api/src/office/scan-rule.ts
# (in the monorepo) carry this string verbatim; their tests read this line and compare. Neither str.isspace() nor
# JS /\s/u is used.
WHITESPACE_CLASS = r"[\t\n\x0b\f\r \u0085\u00a0\u1680\u2000-\u200b\u2028\u2029\u202f\u205f\u3000\ufeff]"
_WHITESPACE = re.compile(WHITESPACE_CLASS)


def non_space_chars(text: str) -> int:
    """Number of code points outside the whitespace set (same unit as `for (const ch of s)` in JS)."""
    return len(_WHITESPACE.sub("", text))


def page_char_counts(doc: pymupdf.Document) -> list[int]:
    """Number of non-whitespace characters in each page's extractable text."""
    return [non_space_chars(page.get_text("text")) for page in doc]


def is_scanned(counts: Sequence[int]) -> bool:
    if not counts:
        return True
    min_chars, ratio = SCANNED_RULE
    low = sum(1 for c in counts if c < min_chars)
    return low >= ratio * len(counts)
