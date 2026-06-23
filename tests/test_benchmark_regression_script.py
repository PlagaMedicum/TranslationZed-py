"""Test module for benchmark regression script."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


def _repo_root() -> Path:
    """Return repository root path for subprocess calls."""
    return Path(__file__).resolve().parents[1]


def _write_json(path: Path, payload: dict[str, object]) -> None:
    """Write JSON payload in UTF-8 for benchmark script tests."""
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_benchmark_regression_script_fails_on_regression(tmp_path: Path) -> None:
    """Fail mode returns non-zero when a benchmark regresses beyond threshold."""
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    _write_json(
        baseline,
        {
            "platforms": {
                "linux": {
                    "benchmarks": {
                        "test_alpha": {"median_ms": 100.0},
                    }
                }
            }
        },
    )
    _write_json(
        current,
        {
            "benchmarks": [
                {
                    "name": "test_alpha",
                    "stats": {"median": 0.2},
                }
            ]
        },
    )

    proc = subprocess.run(
        [
            sys.executable,
            "scripts/check_benchmark_regression.py",
            "--baseline",
            str(baseline),
            "--current",
            str(current),
            "--threshold-percent",
            "20",
            "--mode",
            "fail",
            "--platform",
            "linux",
        ],
        cwd=_repo_root(),
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 1
    assert "regressions" in proc.stdout.lower()


def test_benchmark_regression_script_warn_mode_is_advisory(tmp_path: Path) -> None:
    """Warn mode always exits successfully while reporting regressions."""
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    _write_json(
        baseline,
        {
            "platforms": {
                "linux": {
                    "benchmarks": {
                        "test_alpha": {"median_ms": 100.0},
                    }
                }
            }
        },
    )
    _write_json(
        current,
        {
            "benchmarks": [
                {
                    "name": "test_alpha",
                    "stats": {"median": 0.2},
                }
            ]
        },
    )

    proc = subprocess.run(
        [
            sys.executable,
            "scripts/check_benchmark_regression.py",
            "--baseline",
            str(baseline),
            "--current",
            str(current),
            "--threshold-percent",
            "20",
            "--mode",
            "warn",
            "--platform",
            "linux",
        ],
        cwd=_repo_root(),
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0
    assert "advisory" in proc.stderr.lower()


def test_benchmark_regression_script_writes_summary_json(tmp_path: Path) -> None:
    """Benchmark checker should emit a neutral machine-readable summary artifact."""
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    out_json = tmp_path / "benchmark_summary.json"
    _write_json(
        baseline,
        {
            "platforms": {
                "linux": {
                    "benchmarks": {
                        "test_alpha": {"median_ms": 100.0},
                    }
                }
            }
        },
    )
    _write_json(
        current,
        {
            "datetime": "2026-04-10T10:20:30+00:00",
            "version": "5.0.0",
            "machine_info": {
                "cpu": "Test CPU",
                "arch": "x86_64",
            },
            "commit_info": {
                "id": "deadbeef",
                "branch": "dev",
            },
            "benchmarks": [
                {
                    "name": "test_zeta",
                    "stats": {"median": 0.15},
                },
                {
                    "name": "test_alpha",
                    "stats": {"median": 0.1},
                },
            ],
        },
    )

    proc = subprocess.run(
        [
            sys.executable,
            "scripts/check_benchmark_regression.py",
            "--baseline",
            str(baseline),
            "--current",
            str(current),
            "--threshold-percent",
            "20",
            "--mode",
            "fail",
            "--platform",
            "linux",
            "--json-out",
            str(out_json),
            "--verbose",
        ],
        cwd=_repo_root(),
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"
    assert payload["baseline"]["platform"] == "linux"
    assert payload["baseline"]["threshold_percent"] == 20.0
    assert payload["current"]["path"] == str(current.resolve())
    assert payload["current"]["source"]["path"] == str(current.resolve())
    assert payload["current"]["source"]["generated_at"] == "2026-04-10T10:20:30+00:00"
    assert payload["current"]["source"]["version"] == "5.0.0"
    assert payload["current"]["source"]["machine_info"] == {
        "cpu": "Test CPU",
        "arch": "x86_64",
    }
    assert payload["current"]["source"]["commit_info"] == {
        "id": "deadbeef",
        "branch": "dev",
    }
    assert payload["current"]["source"]["sample_count"] == 2
    assert payload["current"]["source"]["sample_names"] == ["test_alpha", "test_zeta"]
    assert payload["current"]["samples"] == [
        {"name": "test_alpha", "median_ms": 100.0},
        {"name": "test_zeta", "median_ms": 150.0},
    ]
    assert payload["regressions"] == []
    assert '"status": "passed"' in proc.stdout


def test_benchmark_regression_script_writes_summary_on_baseline_skip(
    tmp_path: Path,
) -> None:
    """Skipped comparisons still emit a normalized summary of the raw benchmark file."""
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    out_json = tmp_path / "benchmark_summary.json"
    _write_json(
        baseline,
        {
            "platforms": {
                "macos": {
                    "benchmarks": {
                        "test_alpha": {"median_ms": 100.0},
                    }
                }
            }
        },
    )
    _write_json(
        current,
        {
            "datetime": "2026-04-10T10:20:30+00:00",
            "machine_info": {"cpu": "Test CPU"},
            "benchmarks": [
                {
                    "name": "test_zeta",
                    "stats": {"median": 0.15},
                },
                {
                    "name": "test_alpha",
                    "stats": {"median": 0.1},
                },
            ],
        },
    )

    proc = subprocess.run(
        [
            sys.executable,
            "scripts/check_benchmark_regression.py",
            "--baseline",
            str(baseline),
            "--current",
            str(current),
            "--threshold-percent",
            "20",
            "--mode",
            "fail",
            "--platform",
            "linux",
            "--json-out",
            str(out_json),
        ],
        cwd=_repo_root(),
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["status"] == "skipped"
    assert payload["baseline"]["platform"] == "linux"
    assert payload["current"]["source"]["path"] == str(current.resolve())
    assert payload["current"]["source"]["generated_at"] == "2026-04-10T10:20:30+00:00"
    assert payload["current"]["source"]["machine_info"] == {"cpu": "Test CPU"}
    assert payload["current"]["source"]["sample_names"] == ["test_alpha", "test_zeta"]
    assert payload["current"]["samples"] == [
        {"name": "test_alpha", "median_ms": 100.0},
        {"name": "test_zeta", "median_ms": 150.0},
    ]
    assert "skipping regression check" in proc.stderr.lower()


@pytest.mark.parametrize(
    ("platform_key", "baseline_ms", "current_median_seconds"),
    [
        ("macos", 320.0, 0.33),
        ("windows", 410.0, 0.42),
    ],
)
def test_benchmark_regression_script_uses_platform_baseline(
    tmp_path: Path,
    platform_key: str,
    baseline_ms: float,
    current_median_seconds: float,
) -> None:
    """Selected platform section is used when baseline has per-platform values."""
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    _write_json(
        baseline,
        {
            "platforms": {
                "linux": {
                    "benchmarks": {
                        "test_alpha": {"median_ms": 120.0},
                    }
                },
                platform_key: {
                    "benchmarks": {
                        "test_alpha": {"median_ms": baseline_ms},
                    }
                },
            }
        },
    )
    _write_json(
        current,
        {
            "benchmarks": [
                {
                    "name": "test_alpha",
                    "stats": {"median": current_median_seconds},
                }
            ]
        },
    )

    proc = subprocess.run(
        [
            sys.executable,
            "scripts/check_benchmark_regression.py",
            "--baseline",
            str(baseline),
            "--current",
            str(current),
            "--threshold-percent",
            "20",
            "--mode",
            "fail",
            "--platform",
            platform_key,
        ],
        cwd=_repo_root(),
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0
    assert f"platform={platform_key}" in proc.stdout
