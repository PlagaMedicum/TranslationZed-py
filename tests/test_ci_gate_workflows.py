"""CI workflow contracts for layered gate entrypoints."""

from __future__ import annotations

from pathlib import Path


def _read(path: str) -> str:
    repo_root = Path(__file__).resolve().parents[1]
    return (repo_root / path).read_text(encoding="utf-8")


def test_ci_workflow_uses_layered_gate_commands() -> None:
    """Main CI workflow should call layered gate commands instead of legacy umbrellas."""
    text = _read(".github/workflows/ci.yml")
    assert "make gate-dev" in text
    assert "make test-cov" in text
    assert "make docs-check" in text
    assert "make security" in text
    assert "make test-perf-scale" in text
    assert "make gate-heavy-advisory" in text
    assert "make verify" not in text
    assert "make verify-ci" not in text
    assert "make verify-heavy" not in text


def test_release_workflows_use_gate_release() -> None:
    """Release and RC workflows should use strict L6 gate-release entrypoint."""
    release = _read(".github/workflows/release.yml")
    dry_run = _read(".github/workflows/release-dry-run.yml")
    assert "make gate-release TAG=${{ env.RELEASE_TAG }}" in release
    assert "make gate-release TAG=${{ env.RC_TAG }}" in dry_run
    assert "make verify-ci" not in release
    assert "make verify-ci" not in dry_run


def test_heavy_advisory_ci_trigger_policy() -> None:
    """Heavy advisory lane should be restricted to schedule/manual triggers."""
    text = _read(".github/workflows/ci.yml")
    assert (
        "github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'"
        in text
    )
