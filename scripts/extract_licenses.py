# SPDX-License-Identifier: AGPL-3.0-only

"""Copies the license files of the packages in requirements.lock from their installed wheels into a folder (byte for
byte).

The licenses page of pdfbirlestirme.com (/lisanslar) shows these copies. It runs in the container, with the same
installation as on the server (venv: /opt/pdfb-office/venv):

    python extract_licenses.py <site-packages> <requirements.lock> <destination folder>

- Only the runtime packages in the lock are taken (except pip); development tools in the same venv (pytest, ruff…)
  are not.
- A <destination>/<package>/ folder is created for each package. File paths are kept relative to the `licenses/`
  folder in dist-info (PEP 639) or to the package root. If byte-identical text appears in several places in a package,
  it is taken once (the dist-info copy); two different files that map to the same path are an error (nothing is
  overwritten).
- Fails if a package in the lock is not installed or its version differs from the lock.
- Writes one JSON line per package to stdout: name, version, license fields and the copied files.
"""

from __future__ import annotations

import json
import re
import sys
from importlib.metadata import Distribution, distributions
from pathlib import Path, PurePosixPath

LICENSE_NAMES = ("LICENSE", "LICENCE", "COPYING", "NOTICE", "AUTHORS")
PIN = re.compile(r"^([A-Za-z0-9_.-]+)==([^\s\\;]+)", re.M)


def normalize(name: str) -> str:
    """PEP 503 name: lower case, runs of '-', '_' and '.' become a single '-'."""
    return re.sub(r"[-_.]+", "-", name).lower()


def locked(lock_text: str) -> dict[str, str]:
    """Pinned versions in the lock (except pip)."""
    return {normalize(n): v for n, v in PIN.findall(lock_text) if normalize(n) != "pip"}


def is_license_file(rel: PurePosixPath) -> bool:
    if any(p.lower() == "licenses" for p in rel.parts[:-1]) and rel.parts[0].endswith(".dist-info"):
        return True
    return rel.name.upper().startswith(LICENSE_NAMES)


def target_path(rel: PurePosixPath) -> PurePosixPath:
    """Path of the copy inside the package folder: the dist-info (and licenses/) prefix is dropped; other files are
    relative to the root."""
    parts = rel.parts
    if parts[0].endswith(".dist-info"):
        rest = parts[1:]
        if rest and rest[0].lower() == "licenses":
            rest = rest[1:]
        return PurePosixPath(*rest)
    return rel


def license_files(dist: Distribution) -> list[PurePosixPath]:
    """License files, dist-info ones first (if the same text is in two places, the dist-info copy is kept)."""
    out = []
    for f in dist.files or []:
        rel = PurePosixPath(str(f))
        if rel.parts[0] == ".." or not is_license_file(rel):
            continue
        # Text files only, not binaries (shared libraries, .pyc): only files that match by name.
        if rel.suffix in {".so", ".pyc", ".py", ".pyi", ".dylib", ".dll"}:
            continue
        out.append(rel)
    return sorted(out, key=lambda r: (not r.parts[0].endswith(".dist-info"), r))


def extract(site: Path, lock_text: str, dest: Path) -> list[dict]:
    want = locked(lock_text)
    found: dict[str, Distribution] = {}
    for dist in distributions(path=[str(site)]):
        name = normalize(dist.metadata["Name"])
        if name in want:
            found[name] = dist
    missing = sorted(set(want) - set(found))
    if missing:
        raise SystemExit(f"not installed: {', '.join(missing)}")
    report = []
    for name in sorted(want):
        dist = found[name]
        if dist.version != want[name]:
            raise SystemExit(f"{name}: installed {dist.version}, lock {want[name]}")
        out = dest / name
        copied: dict[str, str] = {}
        seen: dict[bytes, str] = {}  # content -> path of the first copy
        duplicates: dict[str, str] = {}
        for rel in license_files(dist):
            src = Path(dist.locate_file(rel))
            if not src.is_file():
                continue
            data = src.read_bytes()
            to = target_path(rel)
            if str(to) in copied and seen.get(data) != str(to):
                raise SystemExit(f"{name}: {to} appears twice with different content ({copied[str(to)]} and {rel})")
            if data in seen:
                # The same text in two places in a package (opencv: dist-info and cv2/; numpy: dist-info/licenses/
                # and inside the package, PEP 639): shown once on the page. The identical paths go into the report.
                duplicates[str(rel)] = seen[data]
                continue
            seen[data] = str(to)
            copied[str(to)] = str(rel)
            (out / to).parent.mkdir(parents=True, exist_ok=True)
            (out / to).write_bytes(data)
        if not copied:
            raise SystemExit(f"{name}: no license file in the wheel (take the text from upstream)")
        meta = dist.metadata
        report.append(
            {
                "name": name,
                "version": dist.version,
                "license_expression": meta.get("License-Expression"),
                "license": next(iter((meta.get("License") or "").splitlines()), "")[:120] or None,
                "classifiers": [c for c in meta.get_all("Classifier") or [] if c.startswith("License ::")],
                "files": {k: copied[k] for k in sorted(copied)},
                "duplicates": duplicates,
            }
        )
    return report


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print(__doc__, file=sys.stderr)
        return 2
    site, lock, dest = Path(argv[1]), Path(argv[2]), Path(argv[3])
    for row in extract(site, lock.read_text(encoding="utf-8"), dest):
        print(json.dumps(row, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
