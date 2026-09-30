# SPDX-License-Identifier: AGPL-3.0-only

"""Parser for Turkish-formatted numbers, percentages, currency and dates (spec §4.5, PDF to Excel).

Turkish notation uses "." as the thousands separator and "," as the decimal separator (1.234,56), a leading or
trailing % sign, ₺ or TL for the Turkish lira, and dd.mm.yyyy dates.

Any value that cannot be parsed stays text (None is returned). The cell format of a converted number keeps the
number of decimal places and the currency of the source. Excel displays ``#,##0.00`` in the user's locale: ``1.234,56``
in Turkish Excel. ID-like values (a leading zero; an integer without separators of 10 or more digits, e.g. the 11-digit
Turkish national ID number) are not converted: leading zeros must not be lost, and codes must not look like amounts.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

__all__ = ["Parsed", "column_has_comma_decimal", "parse_cell"]


@dataclass(frozen=True)
class Parsed:
    value: float | int | date
    number_format: str


# Patterns are compiled with re.ASCII: \d is only 0-9 (Arabic-Indic or full-width digits are not numbers; review M3).
# The space between a symbol and the number may be a plain space or a no-break space (U+00A0).
_SP = "[  ]?"
# Body: dotted thousands (1.234.567) or a plain integer; optional comma decimal part.
_BODY = r"(?P<int>\d{1,3}(?:\.\d{3})+|\d+)(?:,(?P<frac>\d+))?"
_NUMBER = re.compile(rf"^(?P<sign>-)?{_BODY}$", re.ASCII)
_PERCENT_PRE = re.compile(rf"^%{_SP}(?P<sign>-)?{_BODY}$", re.ASCII)
_PERCENT_POST = re.compile(rf"^(?P<sign>-)?{_BODY}{_SP}%$", re.ASCII)
_TL_PRE = re.compile(rf"^(?P<sign>-)?₺{_SP}{_BODY}$", re.ASCII)
_TL_POST = re.compile(rf"^(?P<sign>-)?{_BODY}{_SP}(?P<cur>₺|TL)$", re.ASCII)
_DATE = re.compile(r"^(?P<d>\d{1,2})\.(?P<m>\d{1,2})\.(?P<y>\d{4})$", re.ASCII)
# Ambiguous bodies: 1.234 (Turkish thousands or English decimal?) and 1,234 (Turkish decimal or English thousands?).
# Both are converted only if the column has evidence of Turkish decimals (column_has_comma_decimal).
_AMBIGUOUS_DOT = re.compile(r"^\d{1,3}\.\d{3}$", re.ASCII)
_MAX_DIGITS = 15
# An integer without separators with at least this many digits is an ID or code and stays text: the 11-digit national
# ID, the 10-digit tax number (VKN), invoice numbers, IBAN fragments (review M5).
_ID_DIGITS = 10
# Excel's 1900 date system cannot represent days before 1900 (review M1).
_MIN_YEAR = 1900


def _decimal_format(frac: str | None, grouped: bool) -> str:
    base = "#,##0" if grouped or frac else "0"
    return base + ("." + "0" * len(frac) if frac else "")


def _is_ambiguous(m: re.Match[str]) -> bool:
    """Is the body of the form 1.234 or 1,234 (a single group of exactly 3 digits)?"""
    raw_int, frac = m.group("int"), m.group("frac")
    if frac is None:
        return _AMBIGUOUS_DOT.match(raw_int) is not None
    return "." not in raw_int and len(raw_int) <= 3 and len(frac) == 3


def _is_comma_decimal_evidence(m: re.Match[str]) -> bool:
    """Does the value prove a Turkish comma decimal? Dotted thousands, or a decimal part that is not 3 digits long
    (review I1)."""
    frac = m.group("frac")
    return frac is not None and ("." in m.group("int") or len(frac) != 3)


def _to_number(m: re.Match[str], column_comma_decimal: bool) -> tuple[float | int, str | None, bool] | None:
    if _is_ambiguous(m) and not column_comma_decimal:
        return None  # 1.234 / 1,234: text unless the column has evidence of Turkish decimals
    raw_int = m.group("int")
    frac = m.group("frac")
    digits = raw_int.replace(".", "")
    grouped = "." in raw_int
    if len(raw_int) > 1 and raw_int.startswith("0"):
        return None  # 00123, 06100, 0532…: an ID or code; grouped 0.500.000 is invalid (review M4)
    if not grouped and frac is None and len(digits) >= _ID_DIGITS:
        return None  # national ID (11 digits), tax number (10 digits), invoice number, IBAN fragment
    if len(digits) + len(frac or "") > _MAX_DIGITS:
        return None
    sign = -1 if m.group("sign") else 1
    if frac is None:
        return sign * int(digits), None, grouped
    return sign * float(f"{digits}.{frac}"), frac, grouped


def _parse_date(text: str) -> Parsed | None:
    m = _DATE.match(text)
    if not m or int(m.group("y")) < _MIN_YEAR:
        return None
    try:
        return Parsed(date(int(m.group("y")), int(m.group("m")), int(m.group("d"))), "dd.mm.yyyy")
    except ValueError:
        return None


def _parse_percent(t: str, column_comma_decimal: bool) -> Parsed | None | bool:
    """Parsed or None (text) if the value looks like a percentage; False otherwise."""
    m = _PERCENT_PRE.match(t) or _PERCENT_POST.match(t)
    if not m:
        return False
    n = _to_number(m, column_comma_decimal)
    if n is None:
        return None
    value, frac, _ = n
    places = len(frac) if frac else 0
    return Parsed(float(value) / 100, "0" + ("." + "0" * places if places else "") + "%")


def _parse_currency(t: str, column_comma_decimal: bool) -> Parsed | None | bool:
    """Parsed or None (text) if the value has a currency (₺ before or after, TL after); False otherwise."""
    m = _TL_PRE.match(t)
    post = m is None
    if post:
        m = _TL_POST.match(t)
        if not m:
            return False
    n = _to_number(m, column_comma_decimal)
    if n is None:
        return None
    value, frac, _ = n
    body = _decimal_format(frac, True)
    return Parsed(float(value), body + f'" {m.group("cur")}"' if post else '"₺"' + body)


def parse_cell(text: str, column_comma_decimal: bool) -> Parsed | None:
    t = text.strip()
    if not t:
        return None
    if _DATE.match(t):
        return _parse_date(t)  # an invalid date (31.02.2026) or one before 1900 is None: text
    for special in (_parse_percent, _parse_currency):
        r = special(t, column_comma_decimal)
        if r is not False:
            return r
    m = _NUMBER.match(t)
    n = _to_number(m, column_comma_decimal) if m else None
    if n is None:
        return None
    value, frac, grouped = n
    return Parsed(value, _decimal_format(frac, grouped))


def column_has_comma_decimal(values: Iterable[str]) -> bool:
    """Does the column contain evidence of Turkish comma decimals (1.234,5; 12,5; %12,5; ₺…,56)?

    This is the input to the rule for the ambiguous 1.234 and 1,234. A single-group value with exactly 3 decimal digits,
    such as 1,234, is not evidence: it may be an English thousands separator (review I1).
    """
    for v in values:
        t = v.strip()
        for rx in (_NUMBER, _PERCENT_PRE, _PERCENT_POST, _TL_PRE, _TL_POST):
            m = rx.match(t)
            if m and _is_comma_decimal_evidence(m):
                return True
    return False
