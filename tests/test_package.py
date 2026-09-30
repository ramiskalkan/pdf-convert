# SPDX-License-Identifier: AGPL-3.0-only

from pathlib import Path

import pdfb_convert
from pdfb_convert.errors import ConvertError, EncryptedPdf, ScannedPdf, TooManyPages, Unreadable


def test_version_is_semver():
    parts = pdfb_convert.__version__.split(".")
    assert len(parts) == 3 and all(p.isdigit() for p in parts)


def test_exit_codes_match_contract():
    # Roadmap §E: the Node side (apps/api/src/office/python.ts PYTHON_EXIT in the pdfbirlestirme monorepo) uses the
    # same table.
    assert ConvertError().exit_code == 1
    assert ScannedPdf().exit_code == 10
    assert TooManyPages().exit_code == 11
    assert Unreadable().exit_code == 12
    assert EncryptedPdf().exit_code == 13


def test_errors_carry_no_message():
    # Error objects carry no file name or content: only class and code.
    for cls in (ConvertError, ScannedPdf, TooManyPages, Unreadable, EncryptedPdf):
        assert str(cls()) == ""


def _pip_block(text: str) -> list[str]:
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("pip=="))
    block = [lines[start]]
    for line in lines[start + 1 :]:
        if not block[-1].rstrip().endswith("\\"):
            break
        block.append(line)
    return [line.strip() for line in block]


def test_pip_lock_is_the_pinned_pip_block():
    # First installation stage (Global Constraints "Installation"): requirements-pip.lock is an exact copy of the pip
    # block in requirements.lock; the pip version and hashes cannot diverge between the two files.
    root = Path(__file__).resolve().parents[1]
    full = _pip_block((root / "requirements.lock").read_text(encoding="utf-8"))
    only = _pip_block((root / "requirements-pip.lock").read_text(encoding="utf-8"))
    assert full == only
    assert full[0].startswith("pip==26.2.1")
    assert any("--hash=sha256:" in line for line in full)


def test_every_python_file_has_spdx_header():
    # AGPL mirror (2c C4): every Python file in the mirror states its license on the first line (as LICENSE: 3.0 only).
    root = Path(__file__).resolve().parents[1]
    files = [p for d in ("src", "tests", "scripts") for p in (root / d).rglob("*.py")]
    assert files
    missing = [
        str(p.relative_to(root))
        for p in files
        if p.read_text(encoding="utf-8").splitlines()[:1] != ["# SPDX-License-Identifier: AGPL-3.0-only"]
    ]
    assert missing == []
