# SPDX-License-Identifier: AGPL-3.0-only

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import BROKEN_TREES, encrypted_pdf

SRC = str(Path(__file__).resolve().parents[1] / "src")


def run(*args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": SRC + os.pathsep + os.environ.get("PYTHONPATH", "")}
    return subprocess.run(
        [sys.executable, "-m", "pdfb_convert", *args], capture_output=True, text=True, env=env, timeout=240, check=False
    )


def test_success_prints_single_json_line(make_text_pdf, tmp_path):
    src = make_text_pdf(["cli testi için yeterince uzun bir metin satırı"], name="SECRET-NAME.pdf")
    out = tmp_path / "output.docx"
    r = run("word", "--in", str(src), "--out", str(out), "--max-pages", "100")
    assert r.returncode == 0, r.stderr[-500:]
    lines = r.stdout.splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == {"pages": 1, "tables": 0}
    assert "SECRET-NAME" not in r.stdout and "SECRET-NAME" not in r.stderr
    assert out.read_bytes()[:4] == b"PK\x03\x04"


def test_exit_codes(make_text_pdf, make_image_pdf, tmp_path):
    out = str(tmp_path / "o.docx")
    assert run("word", "--in", str(make_image_pdf(1)), "--out", out, "--max-pages", "100").returncode == 10
    many = make_text_pdf(["x" * 30] * 3, name="three.pdf")
    assert run("word", "--in", str(many), "--out", out, "--max-pages", "2").returncode == 11
    bad = tmp_path / "broken.pdf"
    bad.write_bytes(b"%PDF-1.7\n broken")
    assert run("word", "--in", str(bad), "--out", out, "--max-pages", "100").returncode == 12


def test_bad_arguments_are_generic_failure(tmp_path):
    for args in (
        [],
        ["word"],
        ["pptx", "--in", "a", "--out", "b", "--max-pages", "1"],
        ["word", "--in", "a", "--out", "b.pdf", "--max-pages", "1"],
        ["word", "--in", "a", "--out", "b.docx", "--max-pages", "0"],
    ):
        r = run(*args)
        assert r.returncode not in (0, 10, 11, 12, 13), args
        assert r.stdout == ""


def test_output_extension_must_match_mode(make_text_pdf, tmp_path):
    src = make_text_pdf(["uzantı denetimi için metin satırı yeterli uzunlukta"])
    r = run("word", "--in", str(src), "--out", str(tmp_path / "o.xlsx"), "--max-pages", "100")
    assert r.returncode == 2


def test_fd_level_output_never_reaches_stdout(tmp_path):
    # MuPDF and OpenCV can write straight to fd 1/2 from their C layer; replacing sys.stdout/sys.stderr does not stop
    # that. main() points fd 1 and 2 at /dev/null and writes the JSON to a previously duplicated fd.
    code = (
        "import os, sys\n"
        "from pdfb_convert import cli\n"
        "def fake(src, dst, n):\n"
        "    os.write(1, b'C-LAYER-STDOUT\\n')\n"
        "    os.write(2, b'C-LAYER-STDERR\\n')\n"
        "    print('python-print')\n"
        "    print('python-stderr', file=sys.stderr)\n"
        "    return {'pages': 1, 'tables': 0}\n"
        "cli.CONVERTERS['word'] = ('.docx', fake)\n"
        "raise SystemExit(cli.main(sys.argv[1:]))\n"
    )
    env = {**os.environ, "PYTHONPATH": SRC + os.pathsep + os.environ.get("PYTHONPATH", "")}
    r = subprocess.run(
        [sys.executable, "-c", code, "word", "--in", "none.pdf", "--out", str(tmp_path / "o.docx"), "--max-pages", "1"],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
        check=False,
    )
    assert r.returncode == 0
    assert r.stdout == '{"pages":1,"tables":0}\n'
    assert r.stderr == ""


def test_encrypted_exit_code(make_text_pdf, tmp_path):
    src = encrypted_pdf(make_text_pdf(["şifreli belge metni"]), tmp_path / "encrypted.pdf", "secret")
    r = run("word", "--in", str(src), "--out", str(tmp_path / "o.docx"), "--max-pages", "100")
    assert r.returncode == 13
    assert r.stdout == ""


@pytest.mark.parametrize("name", sorted(BROKEN_TREES))
def test_broken_page_tree_exit_code(make_broken_tree, tmp_path, name):
    r = run("word", "--in", str(make_broken_tree(name)), "--out", str(tmp_path / "o.docx"), "--max-pages", "100")
    assert r.returncode == 12
    assert r.stdout == ""


def test_page_error_fails_whole_conversion(make_text_pdf, tmp_path):
    # A failing page is not skipped to produce an incomplete document: exit 1 (CONVERT_FAILED), empty stdout.
    src = make_text_pdf(["sayfa hatası testi için yeterince uzun metin"] * 3)
    # pdf2docx is imported inside the patch, i.e. after fd isolation (importing it prints a warning to stdout).
    code = (
        "import sys\n"
        "from pdfb_convert import cli\n"
        "_, real = cli.CONVERTERS['word']\n"
        "def patched(src, dst, n):\n"
        "    from pdf2docx.page.Page import Page\n"
        "    original = Page.parse\n"
        "    def failing(self, **settings):\n"
        "        if self.id == 1:\n"
        "            raise ValueError('broken page')\n"
        "        return original(self, **settings)\n"
        "    Page.parse = failing\n"
        "    return real(src, dst, n)\n"
        "cli.CONVERTERS['word'] = ('.docx', patched)\n"
        "raise SystemExit(cli.main(sys.argv[1:]))\n"
    )
    env = {**os.environ, "PYTHONPATH": SRC + os.pathsep + os.environ.get("PYTHONPATH", "")}
    r = subprocess.run(
        [sys.executable, "-c", code, "word", "--in", str(src), "--out", str(tmp_path / "o.docx"), "--max-pages", "9"],
        capture_output=True,
        text=True,
        env=env,
        timeout=240,
        check=False,
    )
    assert r.returncode == 1
    assert r.stdout == ""
