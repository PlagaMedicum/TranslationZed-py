"""Regression tests for mutation runner shell script behavior."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path


def _repo_root() -> Path:
    """Return repository root for subprocess script execution."""
    return Path(__file__).resolve().parents[1]


def _write_fake_python(path: Path) -> None:
    """Write a fake Python runner used to stub mutmut command outcomes."""
    path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                'if [ "${1:-}" = "-m" ] && [ "${2:-}" = "mutmut" ] \\',
                '  && [ "${3:-}" = "--help" ]; then',
                '  exit "${FAKE_MUTMUT_HELP_STATUS:-0}"',
                "fi",
                'if [ "${1:-}" = "-m" ] && [ "${2:-}" = "mutmut" ] \\',
                '  && [ "${3:-}" = "run" ]; then',
                '  echo "${FAKE_MUTMUT_RUN_OUTPUT:-}"',
                '  exit "${FAKE_MUTMUT_RUN_STATUS:-0}"',
                "fi",
                'if [ "${1:-}" = "-m" ] && [ "${2:-}" = "mutmut" ] \\',
                '  && [ "${3:-}" = "results" ]; then',
                '  echo "${FAKE_MUTMUT_RESULTS_OUTPUT:-}"',
                '  exit "${FAKE_MUTMUT_RESULTS_STATUS:-0}"',
                "fi",
                'if [ "${1:-}" = "scripts/mutation_summary.py" ]; then',
                '  echo "${FAKE_MUTATION_SUMMARY_OUTPUT:-}"',
                '  exit "${FAKE_MUTATION_SUMMARY_STATUS:-0}"',
                "fi",
                'echo "unexpected fake runner invocation: $*" >&2',
                "exit 99",
                "",
            ]
        ),
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


def _run_mutation_script(
    *,
    tmp_path: Path,
    mode: str,
    run_status: int,
    results_status: int,
    summary_status: int,
) -> subprocess.CompletedProcess[str]:
    """Run `scripts/mutation.sh` with fake mutmut statuses and captured output."""
    repo_root = _repo_root()
    fake_python = tmp_path / "fake-python.sh"
    _write_fake_python(fake_python)

    artifacts_rel = f"artifacts/test-mutation-script/{tmp_path.name}"
    env = dict(os.environ)
    env.update(
        {
            "VENV_PY_OVERRIDE": str(fake_python),
            "MUTATION_SCORE_MODE": mode,
            "MUTATION_MIN_KILLED_PERCENT": "25",
            "FAKE_MUTMUT_RUN_STATUS": str(run_status),
            "FAKE_MUTMUT_RESULTS_STATUS": str(results_status),
            "FAKE_MUTATION_SUMMARY_STATUS": str(summary_status),
            "ARTIFACTS": artifacts_rel,
        }
    )

    try:
        return subprocess.run(
            ["bash", "scripts/mutation.sh"],
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        shutil.rmtree(repo_root / artifacts_rel, ignore_errors=True)


def test_mutation_script_strict_mode_fails_when_mutmut_execution_fails(
    tmp_path: Path,
) -> None:
    """Strict mode returns non-zero if mutmut run/results fail even when summary passes."""
    proc = _run_mutation_script(
        tmp_path=tmp_path,
        mode="fail",
        run_status=1,
        results_status=0,
        summary_status=0,
    )
    assert proc.returncode == 1
    assert "mutmut reported issues" in proc.stderr
    assert "strict gate failed" in proc.stderr


def test_mutation_script_warn_mode_keeps_mutmut_failures_advisory(
    tmp_path: Path,
) -> None:
    """Warn mode remains advisory for mutmut run/results failures."""
    proc = _run_mutation_script(
        tmp_path=tmp_path,
        mode="warn",
        run_status=1,
        results_status=0,
        summary_status=0,
    )
    assert proc.returncode == 0
    assert "mutmut reported issues" in proc.stderr


def test_mutation_script_strict_mode_fails_on_summary_gate_failure(
    tmp_path: Path,
) -> None:
    """Strict mode fails when mutation score gate summary returns non-zero."""
    proc = _run_mutation_script(
        tmp_path=tmp_path,
        mode="fail",
        run_status=0,
        results_status=0,
        summary_status=1,
    )
    assert proc.returncode == 1
    assert "score gate did not pass" in proc.stderr
    assert "strict gate failed" in proc.stderr
