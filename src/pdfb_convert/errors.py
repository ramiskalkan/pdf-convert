# SPDX-License-Identifier: AGPL-3.0-only

"""Converter errors. Each class's exit code is part of the contract with the Node caller (apps/api/src/office/python.ts
in the pdfbirlestirme monorepo).

Error objects carry no message: no file name, path or document content ever reaches any output.
"""


class ConvertError(Exception):
    exit_code = 1

    def __init__(self) -> None:
        super().__init__()


class ScannedPdf(ConvertError):
    exit_code = 10


class TooManyPages(ConvertError):
    exit_code = 11


class Unreadable(ConvertError):
    exit_code = 12


class EncryptedPdf(ConvertError):
    exit_code = 13
