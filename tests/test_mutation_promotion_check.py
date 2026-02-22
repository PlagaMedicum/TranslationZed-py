"""Regression tests for mutation promotion readiness checker script."""

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
    mode: str = "fail",
    passed: bool = True,
    warned: bool = False,
    actionable_total: int = 10,
    killed_percent: float = 30.0,
) -> None:
    """Write a synthetic mutation summary artifact JSON payload."""
    payload = {
        "mode": mode,
        "passed": passed,
        "warned": warned,
        "message": "synthetic summary payload",
        "summary": {
            "killed": 3,
            "survived": 7,
            "timeout": 0,
            "suspicious": 0,
            "skipped": 0,
            "actionable_total": actionable_total,
            "total": actionable_total,
            "killed_percent": killed_percent,
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _run_checker(*args: str) -> subprocess.CompletedProcess[str]:
    """Run mutation promotion checker script with captured output."""
    return subprocess.run(
        [sys.executable, "scripts/check_mutation_promotion.py", *args],
        cwd=_repo_root(),
        capture_output=True,
        text=True,
        check=False,
    )


def test_checker_reports_ready_for_two_qualifying_strict_summaries(
    tmp_path: Path,
) -> None:
    """Return ready when two ordered strict summaries satisfy all criteria."""
    older = tmp_path / "older.json"
    newer = tmp_path / "newer.json"
    out_json = tmp_path / "result.json"
    _write_summary(older, mode="fail", passed=True, warned=False, killed_percent=27.0)
    _write_summary(newer, mode="fail", passed=True, warned=False, killed_percent=28.0)

    proc = _run_checker(
        "--summaries",
        str(older),
        str(newer),
        "--required-consecutive",
        "2",
        "--min-killed-percent",
        "25",
        "--require-mode",
        "fail",
        "--out-json",
        str(out_json),
    )

    assert proc.returncode == 0
    assert "ready=True" in proc.stdout
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["ready"] is True
    assert payload["qualifying_tail_streak"] == 2
    assert payload["required_consecutive"] == 2


def test_checker_returns_not_ready_when_last_summary_fails_threshold(
    tmp_path: Path,
) -> None:
    """Return not-ready when one of latest summaries misses killed-percent threshold."""
    older = tmp_path / "older.json"
    newer = tmp_path / "newer.json"
    _write_summary(older, mode="fail", passed=True, warned=False, killed_percent=27.0)
    _write_summary(newer, mode="fail", passed=True, warned=False, killed_percent=19.0)

    proc = _run_checker(
        "--summaries",
        str(older),
        str(newer),
        "--required-consecutive",
        "2",
        "--min-killed-percent",
        "25",
        "--require-mode",
        "fail",
    )

    assert proc.returncode == 1
    assert "ready=False" in proc.stdout
    assert "killed_percent=19.00 < 25.00" in proc.stdout


def test_checker_returns_not_ready_when_mode_is_warn(
    tmp_path: Path,
) -> None:
    """Return not-ready when summaries are warn-mode instead of required fail mode."""
    older = tmp_path / "older.json"
    newer = tmp_path / "newer.json"
    _write_summary(older, mode="warn", passed=True, warned=True, killed_percent=40.0)
    _write_summary(newer, mode="warn", passed=True, warned=True, killed_percent=42.0)

    proc = _run_checker(
        "--summaries",
        str(older),
        str(newer),
        "--required-consecutive",
        "2",
        "--min-killed-percent",
        "25",
        "--require-mode",
        "fail",
    )

    assert proc.returncode == 1
    assert "ready=False" in proc.stdout
    assert "mode='warn' != 'fail'" in proc.stdout


def test_checker_returns_not_ready_when_actionable_total_is_zero(
    tmp_path: Path,
) -> None:
    """Return not-ready when summary has no actionable mutants."""
    summary = tmp_path / "summary.json"
    _write_summary(
        summary,
        mode="fail",
        passed=True,
        warned=False,
        actionable_total=0,
        killed_percent=0.0,
    )

    proc = _run_checker(
        "--summaries",
        str(summary),
        "--required-consecutive",
        "1",
        "--min-killed-percent",
        "25",
        "--require-mode",
        "fail",
    )

    assert proc.returncode == 1
    assert "actionable_total<=0" in proc.stdout


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
        "--min-killed-percent",
        "25",
        "--require-mode",
        "fail",
    )

    assert proc.returncode == 2
    assert "input error" in proc.stderr.lower()
