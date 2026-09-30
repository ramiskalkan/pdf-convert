# SPDX-License-Identifier: AGPL-3.0-only

"""Command line: python -m pdfb_convert <word|excel> --in <pdf> --out <path> --max-pages <n>

Contract with the caller (the site's API, apps/api/src/office/python.ts in the pdfbirlestirme monorepo): the exit code
tells the result, and a single line of JSON is written to stdout ONLY on success. The caller never logs stderr; even so,
no file name or content is ever printed.
"""

import argparse
import json
import logging
import os
import sys
import warnings
from collections.abc import Callable

from pdfb_convert.errors import ConvertError


def _word(src: str, dst: str, max_pages: int) -> dict[str, int]:
    # Importing pdf2docx prints a warning about the legacy `fitz` name to stdout, so the converter is only loaded after
    # fd isolation (_isolate_stdio). Importing cli produces no output.
    from pdfb_convert.word import convert_word  # noqa: PLC0415

    return convert_word(src, dst, max_pages)


def _excel(src: str, dst: str, max_pages: int) -> dict[str, int]:
    # The libraries (pymupdf, openpyxl) are loaded after fd isolation (_isolate_stdio); importing cli produces no
    # output.
    from pdfb_convert.excel import convert_excel  # noqa: PLC0415

    return convert_excel(src, dst, max_pages)


CONVERTERS: dict[str, tuple[str, Callable[[str, str, int], dict[str, int]]]] = {
    "word": (".docx", _word),
    "excel": (".xlsx", _excel),
}
BAD_ARGS = 2


def _quiet() -> None:
    # pdf2docx and PyMuPDF print progress and warnings (including the input path); all of it is silenced.
    logging.disable(logging.CRITICAL)
    warnings.simplefilter("ignore")
    import pymupdf  # noqa: PLC0415 - libraries load only after fd isolation (they may write while importing)

    pymupdf.TOOLS.mupdf_display_errors(False)
    pymupdf.TOOLS.mupdf_display_warnings(False)
    try:
        import cv2  # noqa: PLC0415 - OpenCV is needed only for conversion; its thread limit is set before that

        cv2.setNumThreads(1)
    except ImportError:
        pass


def _parse(argv: list[str] | None) -> argparse.Namespace | None:
    parser = argparse.ArgumentParser(prog="pdfb_convert", add_help=False, exit_on_error=False)
    parser.add_argument("mode", choices=sorted(CONVERTERS))
    parser.add_argument("--in", dest="src", required=True)
    parser.add_argument("--out", dest="dst", required=True)
    parser.add_argument("--max-pages", dest="max_pages", type=int, required=True)
    try:
        args = parser.parse_args(argv)
    except (argparse.ArgumentError, SystemExit):
        return None
    ext, _ = CONVERTERS[args.mode]
    if args.max_pages < 1 or not args.dst.endswith(ext):
        return None
    return args


def _isolate_stdio() -> int:
    """Points fds 1 and 2 at /dev/null and returns a duplicate of the original stdout.

    Replacing sys.stdout/sys.stderr only silences the Python layer; the C layers of MuPDF, OpenCV and pdf2docx can
    write straight to fd 1/2 and break the stdout contract (a single line of JSON). Silencing therefore happens at
    the fd level, and the contract JSON is written only to the fd returned here. Called only once, at process start
    (python -m pdfb_convert).
    """
    sys.stdout.flush()
    sys.stderr.flush()
    contract_fd = os.dup(1)
    devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull, 1)
    os.dup2(devnull, 2)
    os.close(devnull)
    return contract_fd


def main(argv: list[str] | None = None) -> int:
    contract_fd = _isolate_stdio()  # messages from argparse, the libraries and the C layers go nowhere
    try:
        args = _parse(argv)
        if args is None:
            return BAD_ARGS
        _, convert = CONVERTERS[args.mode]
        try:
            _quiet()
            result = convert(args.src, args.dst, args.max_pages)
        except ConvertError as exc:
            return exc.exit_code
        except KeyboardInterrupt:
            raise
        except BaseException:  # noqa: BLE001 - any unexpected error (incl. MemoryError, SystemExit) is CONVERT_FAILED
            return 1
        line = json.dumps({"pages": int(result["pages"]), "tables": int(result["tables"])}, separators=(",", ":"))
        os.write(contract_fd, (line + "\n").encode("ascii"))
        return 0
    finally:
        os.close(contract_fd)
