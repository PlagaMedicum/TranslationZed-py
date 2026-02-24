"""Regression tests for performance dependency evaluator script."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_perf_dependency_eval_marks_missing_candidate_as_rejected(
    tmp_path: Path,
) -> None:
    """Verify missing dependency is rejected with a deterministic gate payload."""
    root = Path(__file__).resolve().parents[1]
    report_path = tmp_path / "dependency_eval.json"

    proc = subprocess.run(
        [
            sys.executable,
            "scripts/perf_dependency_eval.py",
            "--candidate",
            "tzp_nonexistent_candidate_backend",
            "--out-json",
            str(report_path),
        ],
        cwd=root,
        check=False,
        text=True,
        capture_output=True,
    )

    assert proc.returncode == 1
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["candidate"] == "tzp_nonexistent_candidate_backend"
    assert payload["passed"] is False
    gates = payload["gates"]
    assert any(
        gate["name"] == "measurement" and gate["passed"] is False for gate in gates
    )
