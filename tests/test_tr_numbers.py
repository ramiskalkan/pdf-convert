# SPDX-License-Identifier: AGPL-3.0-only

from datetime import date

import pytest

from pdfb_convert.tr_numbers import Parsed, column_has_comma_decimal, parse_cell

# (input, column has comma decimals, expected value, expected format) — None: stays text.
CASES = [
    # Turkish thousands separator and decimal comma
    ("1.234,56", False, 1234.56, "#,##0.00"),
    ("-1.234,56", False, -1234.56, "#,##0.00"),
    ("1.234.567,8", False, 1234567.8, "#,##0.0"),
    ("12,5", False, 12.5, "#,##0.0"),
    ("0,5", False, 0.5, "#,##0.0"),
    ("1234,56", False, 1234.56, "#,##0.00"),
    ("-0,75", False, -0.75, "#,##0.00"),
    # Integers
    ("1234", False, 1234, "0"),
    ("123456789", False, 123456789, "0"),  # 9 digits: within the limit, a number
    ("1234567890", False, None, None),  # 10 digits (tax number): a code, text (review M5)
    ("12.345.678.901", False, 12345678901, "#,##0"),  # 11 digits with separators: an amount, a number
    ("7", False, 7, "0"),
    ("-42", False, -42, "0"),
    ("1.234.567", False, 1234567, "#,##0"),
    # Ambiguous 1.234: column rule
    ("1.234", True, 1234, "#,##0"),
    ("1.234", False, None, None),
    ("-12.500", True, -12500, "#,##0"),
    # Percent
    ("%12,5", False, 0.125, "0.0%"),
    ("%12", False, 0.12, "0%"),
    ("12,5%", False, 0.125, "0.0%"),
    ("%-3,25", False, -0.0325, "0.00%"),
    # Currency
    ("₺1.234,56", False, 1234.56, '"₺"#,##0.00'),
    ("₺ 1.234,56", False, 1234.56, '"₺"#,##0.00'),
    ("1.234,56 ₺", False, 1234.56, '#,##0.00" ₺"'),
    ("1.234,56 TL", False, 1234.56, '#,##0.00" TL"'),
    ("1.234,56TL", False, 1234.56, '#,##0.00" TL"'),
    ("-₺99,90", False, -99.9, '"₺"#,##0.00'),
    # Date
    ("25.09.2026", False, date(2026, 9, 25), "dd.mm.yyyy"),
    ("1.2.2026", False, date(2026, 2, 1), "dd.mm.yyyy"),
    ("29.02.2024", False, date(2024, 2, 29), "dd.mm.yyyy"),
    ("31.02.2026", False, None, None),
    ("25.13.2026", False, None, None),
    # Values that stay text (Review Focus 1: ID-like values)
    ("0532 123 45 67", False, None, None),
    ("05321234567", False, None, None),
    ("00123", False, None, None),
    ("06100", False, None, None),
    ("123456789012", False, None, None),
    ("12345678901", False, None, None),  # Turkish national ID: 11 digits, no separators
    ("TR12 0006 4000 0011 2345 6789 01", False, None, None),
    ("1.234,5,6", False, None, None),
    ("12,34,56", False, None, None),
    ("1,234.56", False, None, None),
    ("abc", False, None, None),
    ("", False, None, None),
    ("   ", False, None, None),
    ("=1+2", False, None, None),
    ("+90 212 555 00 00", False, None, None),
    ("1234567890123456,5", False, None, None),
    # Review I1: an English thousands comma (1,234) is ambiguous; it becomes 1.234 only with Turkish decimal evidence.
    ("1,234", False, None, None),
    ("1,234", True, 1.234, "#,##0.000"),
    ("-12,500", False, None, None),
    ("-12,500", True, -12.5, "#,##0.000"),
    ("₺1,234", False, None, None),
    ("₺1,234", True, 1.234, '"₺"#,##0.000'),
    # M2: in percentages too, ambiguous 1.234 and 1,234 follow the column rule
    ("%1.234", False, None, None),
    ("%1.234", True, 12.34, "0%"),
    ("1,234%", False, None, None),
    ("1,234%", True, 0.01234, "0.000%"),
    # M1: years before 1900 stay text (outside Excel's date range)
    ("31.12.1899", False, None, None),
    ("01.01.0001", False, None, None),
    ("01.01.1900", False, date(1900, 1, 1), "dd.mm.yyyy"),
    # M3: Unicode digits are not numbers (re.ASCII); a no-break space is still accepted
    ("١٢٣", False, None, None),
    ("１２３", False, None, None),
    ("１.２３４,５", False, None, None),
    ("12,5\u00a0%", False, 0.125, "0.0%"),
    ("₺\u00a01.234,56", False, 1234.56, '"₺"#,##0.00'),
    # M4: in a grouped number the first group cannot be 0
    ("0.500.000", False, None, None),
    ("0.123", True, None, None),
    ("-0.123.456,5", False, None, None),
]


@pytest.mark.parametrize(("text", "comma", "value", "fmt"), CASES)
def test_turkish_number_and_date_table(text, comma, value, fmt):
    result = parse_cell(text, comma)
    if value is None:
        assert result is None
        return
    assert isinstance(result, Parsed)
    if isinstance(value, float):
        assert result.value == pytest.approx(value)
        assert isinstance(result.value, float)
    else:
        assert result.value == value
        assert type(result.value) is type(value)
    assert result.number_format == fmt


def test_id_like_values_stay_text():
    values = ["0532 123 45 67", "00123", "06100", "05321234567", "12345678901", "123456789012"]
    for v in [*values, "TR120006400000112345678901"]:
        assert parse_cell(v, True) is None, v


def test_national_id_and_tax_number_stay_text_9_digits_is_number():
    # Decision (docs/02-kararlar.md "Faz 2c" in the pdfbirlestirme monorepo; review M5): integers without separators
    # and with at least 10 digits stay text (_ID_DIGITS = 10). A national ID (11 digits) or tax number (10 digits) is
    # not converted; up to 9 digits is a number.
    assert parse_cell("12345678901", False) is None
    assert parse_cell("12345678901", True) is None
    assert parse_cell("1234567890", False) is None  # a 10-digit tax number is a code too (review M5)
    assert parse_cell("123456789", False) == Parsed(123456789, "0")
    assert parse_cell("-12345678901", False) is None


def test_whitespace_is_trimmed():
    assert parse_cell("  1.234,56  ", False) == Parsed(1234.56, "#,##0.00")


def test_column_comma_decimal_detection():
    assert column_has_comma_decimal(["Tutar", "1.234", "12,50", ""]) is True
    assert column_has_comma_decimal(["1.234", "2.500", "Toplam"]) is False
    assert column_has_comma_decimal(["%12,5"]) is True
    assert column_has_comma_decimal(["₺1.234,56"]) is True
    assert column_has_comma_decimal(["25.09.2026"]) is False


def test_english_thousands_comma_is_not_column_evidence():
    # Review I1: 1,234 and 2,500 alone are no evidence of Turkish decimals (they may be English thousands).
    assert column_has_comma_decimal(["1,234", "2,500", "Toplam"]) is False
    assert column_has_comma_decimal(["-1,500", "%1,234", "₺1,234"]) is False
    # Counter-evidence: a dotted thousands group or a decimal digit count other than 3.
    assert column_has_comma_decimal(["1,234", "1.234,5"]) is True
    assert column_has_comma_decimal(["1,234", "12,5"]) is True
    assert column_has_comma_decimal(["1,234", "0,75"]) is True
    assert column_has_comma_decimal(["1,234", "1.234,567"]) is True


def test_english_thousands_column_is_not_shrunk_1000_times():
    column = ["1,234", "2,500", "10,000"]
    comma = column_has_comma_decimal(column)
    assert [parse_cell(v, comma) for v in column] == [None, None, None]
