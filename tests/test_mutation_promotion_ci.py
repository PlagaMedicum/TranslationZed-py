"""Regression tests for CI mutation-promotion readiness checker."""

from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import zipfile
from pathlib import Path

import pytest


def _load_module():
    """Load check_mutation_promotion_ci module from scripts path."""
    path = Path("scripts/check_mutation_promotion_ci.py").resolve()
    spec = importlib.util.spec_from_file_location("mutation_promotion_ci_module", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _summary_payload(
    *,
    mode: str = "fail",
    passed: bool = True,
    warned: bool = False,
    actionable_total: int = 10,
    killed_percent: float = 30.0,
) -> dict[str, object]:
    """Build synthetic mutation summary payload."""
    return {
        "mode": mode,
        "passed": passed,
        "warned": warned,
        "summary": {
            "actionable_total": actionable_total,
            "killed_percent": killed_percent,
        },
    }


def _zip_summary(payload: dict[str, object]) -> bytes:
    """Build a ZIP archive payload containing summary.json."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w") as archive:
        archive.writestr("summary.json", json.dumps(payload))
    return buffer.getvalue()


def _mock_two_runs(module, monkeypatch: pytest.MonkeyPatch, run_data: dict[int, bytes]) -> None:
    """Install mocks for two latest scheduled runs and per-run artifacts."""
    newest_to_oldest = [
        {
            "id": 200,
            "run_number": 20,
            "run_attempt": 1,
            "created_at": "2026-02-22T04:00:00Z",
            "html_url": "https://example.test/runs/200",
        },
        {
            "id": 100,
            "run_number": 19,
            "run_attempt": 1,
            "created_at": "2026-02-21T04:00:00Z",
            "html_url": "https://example.test/runs/100",
        },
    ]

    def fake_fetch_completed_runs(**_: object) -> list[dict[str, object]]:
        return newest_to_oldest

    def fake_fetch_named_artifact(**kwargs: object) -> dict[str, object] | None:
        run_id = int(kwargs["run_id"])
        if run_id not in run_data:
            return None
        return {
            "id": run_id,
            "name": "heavy-mutation-summary",
            "expired": False,
            "archive_download_url": f"https://example.test/artifacts/{run_id}.zip",
        }

    def fake_download_bytes(*, url: str, token: str) -> bytes:
        assert token == "token"
        run_id = int(url.rsplit("/", maxsplit=1)[-1].removesuffix(".zip"))
        return run_data[run_id]

    monkeypatch.setattr(module, "_fetch_completed_runs", fake_fetch_completed_runs)
    monkeypatch.setattr(module, "_fetch_named_artifact", fake_fetch_named_artifact)
    monkeypatch.setattr(module, "_github_download_bytes", fake_download_bytes)


def test_evaluate_reports_ready_for_two_qualifying_strict_runs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Return ready when both latest scheduled runs satisfy strict criteria."""
    module = _load_module()
    _mock_two_runs(
        module,
        monkeypatch,
        {
            100: _zip_summary(_summary_payload(killed_percent=27.0)),
            200: _zip_summary(_summary_payload(killed_percent=29.0)),
        },
    )

    evaluation = module.evaluate_promotion_readiness(
        repo="owner/repo",
        workflow="ci.yml",
        branch="main",
        event="schedule",
        artifact_name="heavy-mutation-summary",
        required_consecutive=2,
        min_killed_percent=25.0,
        require_mode="fail",
        token="token",
        work_dir=tmp_path,
    )

    assert evaluation.ready is True
    assert evaluation.qualifying_tail_streak == 2
    assert evaluation.total_runs_considered == 2


def test_evaluate_reports_not_ready_when_latest_run_misses_threshold(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Return not-ready when latest run killed-percent is below threshold."""
    module = _load_module()
    _mock_two_runs(
        module,
        monkeypatch,
        {
            100: _zip_summary(_summary_payload(killed_percent=27.0)),
            200: _zip_summary(_summary_payload(killed_percent=19.0)),
        },
    )

    evaluation = module.evaluate_promotion_readiness(
        repo="owner/repo",
        workflow="ci.yml",
        branch="main",
        event="schedule",
        artifact_name="heavy-mutation-summary",
        required_consecutive=2,
        min_killed_percent=25.0,
        require_mode="fail",
        token="token",
        work_dir=tmp_path,
    )

    assert evaluation.ready is False
    assert evaluation.qualifying_tail_streak == 0
    assert "killed_percent=19.00 < 25.00" in evaluation.results[-1].reasons


def test_evaluate_reports_not_ready_when_mode_is_warn(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Return not-ready when run summaries are warn-mode instead of fail-mode."""
    module = _load_module()
    _mock_two_runs(
        module,
        monkeypatch,
        {
            100: _zip_summary(_summary_payload(mode="warn", warned=True, killed_percent=40.0)),
            200: _zip_summary(_summary_payload(mode="warn", warned=True, killed_percent=42.0)),
        },
    )

    evaluation = module.evaluate_promotion_readiness(
        repo="owner/repo",
        workflow="ci.yml",
        branch="main",
        event="schedule",
        artifact_name="heavy-mutation-summary",
        required_consecutive=2,
        min_killed_percent=25.0,
        require_mode="fail",
        token="token",
        work_dir=tmp_path,
    )

    assert evaluation.ready is False
    assert "mode='warn' != 'fail'" in evaluation.results[-1].reasons


def test_evaluate_reports_not_ready_when_actionable_mutants_are_zero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Return not-ready when latest run reports zero actionable mutants."""
    module = _load_module()
    _mock_two_runs(
        module,
        monkeypatch,
        {
            100: _zip_summary(_summary_payload(killed_percent=35.0)),
            200: _zip_summary(
                _summary_payload(actionable_total=0, killed_percent=0.0)
            ),
        },
    )

    evaluation = module.evaluate_promotion_readiness(
        repo="owner/repo",
        workflow="ci.yml",
        branch="main",
        event="schedule",
        artifact_name="heavy-mutation-summary",
        required_consecutive=2,
        min_killed_percent=25.0,
        require_mode="fail",
        token="token",
        work_dir=tmp_path,
    )

    assert evaluation.ready is False
    assert "actionable_total<=0" in evaluation.results[-1].reasons


def test_evaluate_reports_not_ready_when_artifact_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Return not-ready when one of the latest runs has no summary artifact."""
    module = _load_module()
    _mock_two_runs(
        module,
        monkeypatch,
        {
            100: _zip_summary(_summary_payload(killed_percent=31.0)),
        },
    )

    evaluation = module.evaluate_promotion_readiness(
        repo="owner/repo",
        workflow="ci.yml",
        branch="main",
        event="schedule",
        artifact_name="heavy-mutation-summary",
        required_consecutive=2,
        min_killed_percent=25.0,
        require_mode="fail",
        token="token",
        work_dir=tmp_path,
    )

    assert evaluation.ready is False
    assert evaluation.results[-1].artifact_state == "missing"
    assert "artifact 'heavy-mutation-summary' not found" in evaluation.results[-1].reasons


def test_evaluate_raises_value_error_for_unreadable_zip_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Raise ValueError when artifact download is not a readable ZIP archive."""
    module = _load_module()
    _mock_two_runs(
        module,
        monkeypatch,
        {
            100: _zip_summary(_summary_payload(killed_percent=35.0)),
            200: b"not-a-zip",
        },
    )

    with pytest.raises(ValueError, match="Unreadable artifact archive"):
        module.evaluate_promotion_readiness(
            repo="owner/repo",
            workflow="ci.yml",
            branch="main",
            event="schedule",
            artifact_name="heavy-mutation-summary",
            required_consecutive=2,
            min_killed_percent=25.0,
            require_mode="fail",
            token="token",
            work_dir=tmp_path,
        )


def test_main_returns_invalid_input_when_github_token_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Return exit code 2 when token env variable is missing."""
    module = _load_module()
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setattr(
        module,
        "evaluate_promotion_readiness",
        lambda **_: (_ for _ in ()).throw(AssertionError("must not be called")),
    )
    monkeypatch.setenv("PYTHONHASHSEED", os.environ.get("PYTHONHASHSEED", "0"))

    old_argv = sys.argv
    try:
        sys.argv = [
            "check_mutation_promotion_ci.py",
            "--repo",
            "owner/repo",
            "--branch",
            "main",
        ]
        result = module.main()
    finally:
        sys.argv = old_argv

    assert result == module.EXIT_INVALID_INPUT


def test_main_returns_invalid_input_for_malformed_workflow_runs_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Return exit code 2 when workflow-runs payload shape is malformed."""
    module = _load_module()
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.setattr(
        module,
        "_fetch_completed_runs",
        lambda **_: [{"id": "bad"}],
    )

    old_argv = sys.argv
    try:
        sys.argv = [
            "check_mutation_promotion_ci.py",
            "--repo",
            "owner/repo",
            "--branch",
            "main",
        ]
        result = module.main()
    finally:
        sys.argv = old_argv

    assert result == module.EXIT_INVALID_INPUT
