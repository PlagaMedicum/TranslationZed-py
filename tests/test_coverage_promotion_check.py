"""Regression tests for coverage promotion readiness checker script."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


def _repo_root() -> Path:
    """Return repository root path for subprocess calls."""
    return Path(__file__).resolve().parents[1]


def _write_summary(
    path: Path,
    *,
    gate_passed: bool = True,
    overall_percent: float = 92.2,
    core_percent: float = 97.1,
    overall_fail_under: float = 92.0,
    core_fail_under: float = 97.0,
) -> None:
    """Write a synthetic coverage-summary artifact JSON payload."""
    payload = {
        "gate_passed": gate_passed,
        "overall_percent": overall_percent,
        "core_percent": core_percent,
        "overall_fail_under": overall_fail_under,
        "core_fail_under": core_fail_under,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _run_checker(*args: str) -> subprocess.CompletedProcess[str]:
    """Run coverage promotion checker script with captured output."""
    return subprocess.run(
        [sys.executable, "scripts/check_coverage_promotion.py", *args],
        cwd=_repo_root(),
        capture_output=True,
        text=True,
        check=False,
    )


def test_checker_reports_ready_for_two_qualifying_coverage_summaries(
    tmp_path: Path,
) -> None:
    """Return ready when two ordered summaries satisfy phase-2 thresholds."""
    older = tmp_path / "older.json"
    newer = tmp_path / "newer.json"
    out_json = tmp_path / "result.json"
    _write_summary(older, overall_percent=92.4, core_percent=97.2)
    _write_summary(newer, overall_percent=92.1, core_percent=97.0)

    proc = _run_checker(
        "--summaries",
        str(older),
        str(newer),
        "--required-consecutive",
        "2",
        "--min-overall",
        "92",
        "--min-core",
        "97",
        "--out-json",
        str(out_json),
    )

    assert proc.returncode == 0
    assert "ready=True" in proc.stdout
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["ready"] is True
    assert payload["qualifying_tail_streak"] == 2
    assert payload["required_consecutive"] == 2


def test_checker_returns_not_ready_when_latest_summary_misses_core_threshold(
    tmp_path: Path,
) -> None:
    """Return not-ready when one of latest summaries misses core threshold."""
    older = tmp_path / "older.json"
    newer = tmp_path / "newer.json"
    _write_summary(older, overall_percent=92.4, core_percent=97.2)
    _write_summary(newer, overall_percent=92.3, core_percent=96.7)

    proc = _run_checker(
        "--summaries",
        str(older),
        str(newer),
        "--required-consecutive",
        "2",
        "--min-overall",
        "92",
        "--min-core",
        "97",
    )

    assert proc.returncode == 1
    assert "ready=False" in proc.stdout
    assert "core_percent=96.70 < 97.00" in proc.stdout


def test_checker_returns_not_ready_when_fail_under_metadata_is_too_low(
    tmp_path: Path,
) -> None:
    """Return not-ready when summary shows gate was run with weaker floor values."""
    older = tmp_path / "older.json"
    newer = tmp_path / "newer.json"
    _write_summary(
        older,
        overall_percent=93.0,
        core_percent=97.5,
        overall_fail_under=91.0,
        core_fail_under=96.0,
    )
    _write_summary(newer, overall_percent=92.3, core_percent=97.1)

    proc = _run_checker(
        "--summaries",
        str(older),
        str(newer),
        "--required-consecutive",
        "2",
        "--min-overall",
        "92",
        "--min-core",
        "97",
    )

    assert proc.returncode == 1
    assert "ready=False" in proc.stdout
    assert "overall_fail_under=91.00 < 92.00" in proc.stdout
    assert "core_fail_under=96.00 < 97.00" in proc.stdout


@pytest.mark.parametrize(
    "mode",
    ("missing", "malformed"),
)
def test_checker_returns_input_error_for_missing_or_malformed_summary(
    tmp_path: Path,
    mode: str,
) -> None:
    """Return exit code 2 when summary input path is missing or malformed JSON."""
    summary = tmp_path / "summary.json"
    if mode == "malformed":
        summary.write_text("{", encoding="utf-8")
    else:
        summary = tmp_path / "does-not-exist.json"

    proc = _run_checker(
        "--summaries",
        str(summary),
        "--required-consecutive",
        "1",
        "--min-overall",
        "92",
        "--min-core",
        "97",
    )

    assert proc.returncode == 2
    assert "input error" in proc.stderr.lower()
