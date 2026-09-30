# SPDX-License-Identifier: AGPL-3.0-only

"""scripts/extract_licenses.py: license files of the locked packages are copied byte for byte from installed wheels."""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "extract_licenses.py"
spec = importlib.util.spec_from_file_location("extract_licenses", SCRIPT)
assert spec and spec.loader
el = importlib.util.module_from_spec(spec)
spec.loader.exec_module(el)


def fake_dist(site: Path, name: str, version: str, files: dict[str, bytes], license_expr: str = "MIT") -> None:
    """Smallest dist-info with a RECORD (importlib.metadata reads the file list from RECORD)."""
    di = f"{name.replace('-', '_')}-{version}.dist-info"
    (site / di).mkdir(parents=True)
    (site / di / "METADATA").write_text(
        f"Metadata-Version: 2.4\nName: {name}\nVersion: {version}\nLicense-Expression: {license_expr}\n",
        encoding="utf-8",
    )
    for rel, data in files.items():
        p = site / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    record = [*files, f"{di}/METADATA", f"{di}/RECORD"]
    (site / di / "RECORD").write_text("".join(f"{r},,\n" for r in record), encoding="utf-8")


LOCK = (
    "alpha-pkg==1.0 \\\n    --hash=sha256:00\n"
    "beta==2.0 \\\n    --hash=sha256:11\n"
    "pip==26.2.1 \\\n    --hash=sha256:22\n"
)


@pytest.fixture
def site(tmp_path: Path) -> Path:
    s = tmp_path / "site"
    fake_dist(
        s,
        "alpha_pkg",
        "1.0",
        {
            "alpha_pkg-1.0.dist-info/licenses/LICENSE": b"alpha license\n",
            "alpha_pkg-1.0.dist-info/licenses/vendor/LICENSE": b"vendored\n",
            "alpha_pkg/LICENSE-3RD-PARTY.txt": b"third party\n",
            "alpha_pkg/__init__.py": b"",
        },
    )
    fake_dist(s, "beta", "2.0", {"beta-2.0.dist-info/COPYING": b"beta copying\x00\xff\n"}, "BSD-3-Clause")
    fake_dist(s, "pytest", "9.1.1", {"pytest-9.1.1.dist-info/licenses/LICENSE": b"dev tool\n"})
    return s


def test_copies_only_locked_packages_byte_for_byte(site: Path, tmp_path: Path) -> None:
    dest = tmp_path / "out"
    report = el.extract(site, LOCK, dest)
    assert [r["name"] for r in report] == ["alpha-pkg", "beta"]
    assert (dest / "alpha-pkg" / "LICENSE").read_bytes() == b"alpha license\n"
    assert (dest / "alpha-pkg" / "vendor" / "LICENSE").read_bytes() == b"vendored\n"
    assert (dest / "alpha-pkg" / "alpha_pkg" / "LICENSE-3RD-PARTY.txt").read_bytes() == b"third party\n"
    assert (dest / "beta" / "COPYING").read_bytes() == b"beta copying\x00\xff\n"
    assert not (dest / "pytest").exists()
    assert not (dest / "pip").exists()
    assert report[1]["license_expression"] == "BSD-3-Clause"
    assert report[0]["files"]["LICENSE"] == "alpha_pkg-1.0.dist-info/licenses/LICENSE"


def test_version_mismatch_fails(site: Path, tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="beta: installed 2.0, lock 2.1"):
        el.extract(site, LOCK.replace("beta==2.0", "beta==2.1"), tmp_path / "out")


def test_missing_package_fails(site: Path, tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="not installed: gamma"):
        el.extract(site, LOCK + "gamma==1 \\\n    --hash=sha256:33\n", tmp_path / "out")


def test_same_target_twice_different_fails(tmp_path: Path) -> None:
    s = tmp_path / "site"
    fake_dist(s, "beta", "2.0", {"beta-2.0.dist-info/LICENSE": b"a\n", "beta-2.0.dist-info/licenses/LICENSE": b"b\n"})
    with pytest.raises(SystemExit, match="appears twice with different content"):
        el.extract(s, "beta==2.0\n", tmp_path / "out")


def test_same_target_twice_identical_copied_once(tmp_path: Path) -> None:
    # numpy: numpy/ma/LICENSE both in the package and as dist-info/licenses/numpy/ma/LICENSE (PEP 639).
    s = tmp_path / "site"
    fake_dist(
        s, "beta", "2.0", {"beta/ma/LICENSE": b"same\n", "beta-2.0.dist-info/licenses/beta/ma/LICENSE": b"same\n"}
    )
    report = el.extract(s, "beta==2.0\n", tmp_path / "out")
    assert report[0]["files"] == {"beta/ma/LICENSE": "beta-2.0.dist-info/licenses/beta/ma/LICENSE"}
    assert report[0]["duplicates"] == {"beta/ma/LICENSE": "beta/ma/LICENSE"}
    assert (tmp_path / "out" / "beta" / "beta" / "ma" / "LICENSE").read_bytes() == b"same\n"


def test_identical_text_in_two_places_copied_once_from_dist_info(tmp_path: Path) -> None:
    # opencv: LICENSE-3RD-PARTY.txt both in dist-info and under cv2/, byte for byte identical.
    s = tmp_path / "site"
    fake_dist(s, "cv", "1.0", {"cv-1.0.dist-info/LICENSE.txt": b"x\n", "cv2/LICENSE.txt": b"x\n", "cv2/NOTICE": b"y\n"})
    report = el.extract(s, "cv==1.0\n", tmp_path / "out")
    assert report[0]["files"] == {"LICENSE.txt": "cv-1.0.dist-info/LICENSE.txt", "cv2/NOTICE": "cv2/NOTICE"}
    assert report[0]["duplicates"] == {"cv2/LICENSE.txt": "LICENSE.txt"}
    assert sorted(p.name for p in (tmp_path / "out" / "cv").rglob("*") if p.is_file()) == ["LICENSE.txt", "NOTICE"]


def test_package_without_license_file_fails(tmp_path: Path) -> None:
    s = tmp_path / "site"
    fake_dist(s, "beta", "2.0", {"beta/__init__.py": b""})
    with pytest.raises(SystemExit, match="no license file in the wheel"):
        el.extract(s, "beta==2.0\n", tmp_path / "out")


def test_normalize() -> None:
    assert el.normalize("Typing_Extensions") == "typing-extensions"
    assert el.normalize("opencv.python__headless") == "opencv-python-headless"
