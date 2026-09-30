# SPDX-License-Identifier: AGPL-3.0-only

"""S4 (spec §13): cold start and worst-case time for 100 pages. Invoked the same way as in production: system
python3.12, PYTHONHOME=/usr, PYTHONPATH=<release>/venv/...:<release>/src, compiled pyc (unchecked-hash) and a warm
cache.

    python3 bench.py [--mode word|excel] <release dir> <unit corpus> <shared corpus>
--mode defaults to word. The PDF to Excel work repeats the same measurement with `--mode excel` on tablo-100s.pdf;
the Python timeout is set from the worse of the two modes.
Unit corpus: output of tests/corpus/make_corpus.py (petition.pdf).
Shared corpus: output of infra/office/corpus/make_corpus.py --pdfs in the pdfbirlestirme monorepo
(pdf/bench-20p-tablo.pdf, pdf/tablo-100s.pdf); the load test uses the same files.
Output: JSON (times in seconds): cold_p50, cold_p95, p100_max, p100_all, bench20_p50, bench20_p95.
The time of each run is written to stderr for progress; stdout carries only the JSON.
"""

import argparse
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

EXT = {"word": ".docx", "excel": ".xlsx"}


def env_for(release: Path) -> dict[str, str]:
    return {
        "PATH": "/usr/bin:/bin",
        "PYTHONHOME": "/usr",
        "PYTHONPATH": f"{release}/venv/lib/python3.12/site-packages:{release}/src",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "HOME": "/tmp",  # noqa: S108 (same HOME as in the production sandbox)
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "XDG_CACHE_HOME": f"{release}/cache",
    }


def timed(release: Path, src: Path, mode: str = "word") -> float:
    with tempfile.TemporaryDirectory() as tmp:
        t0 = time.monotonic()
        r = subprocess.run(
            [
                "/usr/bin/python3.12",
                "-m",
                "pdfb_convert",
                mode,
                "--in",
                str(src),
                "--out",
                f"{tmp}/o{EXT[mode]}",
                "--max-pages",
                "100",
            ],
            env=env_for(release),
            capture_output=True,
            check=False,
            timeout=900,
        )
        dt = time.monotonic() - t0
    if r.returncode != 0:
        raise SystemExit(f"{src.name}: exit code {r.returncode}")
    print(f"{src.name} {dt:.3f}", file=sys.stderr, flush=True)
    return dt


def p95(xs: list[float]) -> float:
    return statistics.quantiles(xs, n=20)[18] if len(xs) >= 2 else xs[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=sorted(EXT), default="word")
    parser.add_argument("release", type=Path)
    parser.add_argument("unit", type=Path)
    parser.add_argument("shared", type=Path)
    a = parser.parse_args()
    release, unit, shared, mode = a.release, a.unit, a.shared, a.mode
    cold = [timed(release, unit / "petition.pdf", mode) for _ in range(20)]
    bench20 = [timed(release, shared / "pdf" / "bench-20p-tablo.pdf", mode) for _ in range(20)]
    p100 = [timed(release, shared / "pdf" / "tablo-100s.pdf", mode) for _ in range(5)]
    print(
        json.dumps(
            {
                "mode": mode,
                "cold_p50": statistics.median(cold),
                "cold_p95": p95(cold),
                "bench20_p50": statistics.median(bench20),
                "bench20_p95": p95(bench20),
                "p100_max": max(p100),
                "p100_all": p100,
                "timeout_ms": max(240_000, round(max(p100) * 1.5 * 1000)),
                "cpus": os.cpu_count(),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
