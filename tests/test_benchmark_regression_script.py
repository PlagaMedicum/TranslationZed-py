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
