"""CI workflow contracts for layered gate entrypoints."""

from __future__ import annotations

import re
from pathlib import Path


def _read(path: str) -> str:
    repo_root = Path(__file__).resolve().parents[1]
    return (repo_root / path).read_text(encoding="utf-8")


def test_ci_workflow_uses_layered_gate_commands() -> None:
    """Main CI workflow should call layered gate commands instead of legacy umbrellas."""
    text = _read(".github/workflows/ci.yml")
    assert "make gate-dev" in text
    assert "make test-core-fast" in text
    assert "make test-cov" in text
    assert "make docs-check" in text
    assert "make security" in text
    assert "bash scripts/test_perf_scale.sh" in text
    assert "bash scripts/test_readonly_clean.sh" in text
    assert "make gate-heavy-advisory" in text
    assert "make test-perf-scale" not in text
    assert "make test-readonly-clean" not in text
    assert "make verify" not in text
    assert "make verify-ci" not in text
    assert "make verify-heavy" not in text


def test_ci_workflow_keeps_release_tags_out_of_branch_ci() -> None:
    """Release tags should run their L6 workflow without duplicating ordinary CI."""
    text = _read(".github/workflows/ci.yml")
    trigger = text.split("jobs:", 1)[0]
    assert 'push:\n    branches:\n      - "**"' in trigger
    assert "tags:" not in trigger


def test_manual_contract_ci_job_has_headless_qt_prerequisites() -> None:
    """Selector collection imports GUI modules and needs Linux Qt runtime libraries."""
    text = _read(".github/workflows/ci.yml")
    job = text.split("  manual-contract:", 1)[1].split("\n  ci-pr:", 1)[0]
    assert "run: make ci-deps" in job
    assert 'echo "QT_QPA_PLATFORM=offscreen" >> $GITHUB_ENV' in job
    assert job.index("run: make ci-deps") < job.index("make test-ui-manual-contract")


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


def test_every_workflow_make_target_exists() -> None:
    """Workflow commands must resolve to current Make targets."""
    repo_root = Path(__file__).resolve().parents[1]
    makefile = (repo_root / "Makefile").read_text(encoding="utf-8")
    targets = set(re.findall(r"^([A-Za-z0-9_.-]+):", makefile, flags=re.MULTILINE))
    for workflow in sorted((repo_root / ".github/workflows").glob("*.yml")):
        text = workflow.read_text(encoding="utf-8")
        for target in re.findall(
            r"^\s*(?:run:\s*)?make\s+([A-Za-z0-9_.-]+)",
            text,
            flags=re.MULTILINE,
        ):
            assert target in targets, f"{workflow} references missing target {target}"


def test_strict_gate_scripts_keep_quality_and_benchmark_components() -> None:
    """Gate refactors must not silently drop blocking quality components."""
    ci_gate = _read("scripts/gates/gate_ci_pr.sh")
    release_gate = _read("scripts/gates/gate_release.sh")
    for token in (
        "test_cov.sh",
        "security.sh",
        "docs_check.sh",
        "test_perf_scale.sh",
    ):
        assert token in ci_gate
    for token in (
        "bench_check.sh",
        "test_perf_heavy.sh",
        "test_mutation_stage_internal.sh",
        "release_evidence_check.py",
    ):
        assert token in release_gate
