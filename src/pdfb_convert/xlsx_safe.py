# SPDX-License-Identifier: AGPL-3.0-only

"""Cell writing protected against formula injection, and worksheet names (spec §4.5).

Rule: no cell is ever a formula. Values converted to numbers or dates (tr_numbers.Parsed) are written with their own
type; every other text is written with ``data_type='s'``. openpyxl treats text starting with ``=`` as a formula
(``'f'``), so the type is forced back to text after assignment. Text starting with ``+ - @ TAB CR`` (CSV/DDE injection
patterns) takes the same path.
"""

from __future__ import annotations

import re

from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.worksheet.worksheet import Worksheet

from .tr_numbers import Parsed

__all__ = ["FORMULA_PREFIXES", "MAX_CELL_CHARS", "put_cell", "sheet_title"]

FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
_INVALID_TITLE = re.compile(r"[\[\]:*?/\\]")
_MAX_TITLE = 31
# Excel's per-cell text limit; anything longer makes Excel show a "repair" warning for the file (review M6).
MAX_CELL_CHARS = 32_767
# Code points that are not allowed in XML 1.0 but are not covered by ILLEGAL_CHARACTERS_RE: lone surrogates and
# U+FFFE/U+FFFF. lxml fails the save on them (review I3); U+FFFD (the replacement character) is written instead.
_NON_XML = re.compile("[\ud800-\udfff\ufffe\uffff]")
# Excel reserves the name "History" (culture-independent, case-insensitive; review M10).
_RESERVED_TITLES = frozenset({"history"})


def put_cell(ws: Worksheet, row: int, col: int, raw: str | None, parsed: Parsed | None) -> bool:
    """Writes the cell. Returns True if the text was truncated at MAX_CELL_CHARS (the caller counts; the content is
    never written anywhere else)."""
    if parsed is not None:
        c = ws.cell(row=row, column=col)
        c.value = parsed.value
        c.number_format = parsed.number_format
        return False
    if raw is None:
        return False
    text = _NON_XML.sub("\ufffd", ILLEGAL_CHARACTERS_RE.sub("", raw))
    if text == "":
        return False
    truncated = len(text) > MAX_CELL_CHARS
    if truncated:
        text = text[:MAX_CELL_CHARS]
    c = ws.cell(row=row, column=col)
    c.value = text
    # Text is always text, with or without a formula prefix (openpyxl turns anything starting with '=' into 'f').
    c.data_type = "s"
    return truncated


def _fold(s: str) -> str:
    # Turkish case folding: "I" lowers to dotless "ı" and "İ" to "i".
    return s.replace("I", "ı").replace("İ", "i").casefold()


def _taken(candidate: str, used: set[str]) -> bool:
    return _fold(candidate) in used or candidate.casefold() in _RESERVED_TITLES


def _trim(s: str) -> str:
    # Excel does not accept ' at the start or end of a name; it can also end up at the end after truncation.
    return s.strip().strip("'").strip()


def sheet_title(base: str, used: set[str]) -> str:
    """A name that follows Excel's rules and is unique in ``used``, case-insensitively (≤ 31 characters).

    "Sayfa" (Turkish for "Page") is the fallback name shown to users.
    """
    clean = _trim(_INVALID_TITLE.sub(" ", base)) or "Sayfa"
    candidate = _trim(clean[:_MAX_TITLE]) or "Sayfa"
    n = 2
    while _taken(candidate, used):
        suffix = f" ({n})"
        candidate = (_trim(clean[: _MAX_TITLE - len(suffix)]) or "Sayfa") + suffix
        n += 1
    used.add(_fold(candidate))
    return candidate
