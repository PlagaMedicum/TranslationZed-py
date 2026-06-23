"""Regression contracts for the reduced public Makefile facade."""

from __future__ import annotations

from pathlib import Path

REQUIRED_PUBLIC_TARGETS = (
    "venv",
    "install",
    "precommit",
    "gate-dev",
    "gate-commit",
    "gate-push",
    "gate-task-close",
    "gate-ci-pr",
    "gate-heavy-advisory",
    "gate-release",
    "test",
    "test-core-fast",
    "test-cov",
    "test-ui-manual-contract",
    "arch-check",
    "locale-agnostic-check",
    "docs-check",
    "bench",
    "bench-check",
    "security",
    "test-mutation",
    "test-mutation-stage",
    "mutation-promotion-check",
    "mutation-promotion-readiness",
    "coverage-promotion-check",
    "ui-manual-list",
    "ui-manual-run",
    "release-evidence-check",
    "release-evidence-sync",
    "release-evidence-sync-all",
    "run",
    "pack",
    "pack-win",
    "dist",
    "ci-deps",
    "clean",
    "clean-cache",
    "clean-config",
    "clean-manual-artifacts",
    "release-check",
    "release-dry-run",
)

REMOVED_PUBLIC_TARGETS = (
    "fmt",
    "fmt-check",
    "fmt-check-changed",
    "lint",
    "lint-check",
    "typecheck",
    "test-routed-fast",
    "test-routed-full",
    "test-prop-fast",
    "test-prop-slow",
    "test-search-a35",
    "test-search-a37",
    "test-status-a34",
    "test-cov-promotion-contract",
    "test-qa-v09",
    "test-tmq-v09",
    "test-tmw-v09",
    "test-cr-v09",
    "test-src-a29",
    "test-tzp-a30",
    "test-a31-manual",
    "test-perf",
    "test-perf-scale",
    "test-perf-heavy",
    "docstyle",
    "docs-build",
    "docs-build-lite",
    "docs-index",
    "docs-index-write",
    "docs-api",
    "review-queue-check",
    "code-triage",
    "docs-contract",
    "test-encoding-integrity",
    "diagnose-encoding",
    "test-readonly-clean",
    "test-warnings",
    "perf-scenarios",
    "perf-dependency-eval",
    "ui-manual-headless",
    "ui-manual-batch",
    "ui-manual-conflict-flow",
    "ui-manual-conflict-triad",
    "release-evidence-sync-conflict",
)


def _makefile_text() -> str:
    return (Path(__file__).resolve().parents[1] / "Makefile").read_text(
        encoding="utf-8"
    )


def _target_recipe(makefile_text: str, target: str) -> str:
    lines = makefile_text.splitlines()
    for idx, line in enumerate(lines):
        if not line.startswith(f"{target}:"):
            continue
        body: list[str] = []
        next_idx = idx + 1
        while next_idx < len(lines):
            candidate = lines[next_idx]
            if candidate.startswith("\t"):
                body.append(candidate)
                next_idx += 1
                continue
            if not candidate.strip():
                next_idx += 1
                continue
            break
        return "\n".join(body)
    return ""


def test_required_public_targets_exist() -> None:
    """The root Makefile should expose only the stable public facade."""
    text = _makefile_text()
    for target in REQUIRED_PUBLIC_TARGETS:
        assert f"\n{target}:" in f"\n{text}"


def test_internal_and_packet_specific_targets_are_not_public() -> None:
    """Packet lanes and helper checks should stay behind script-level orchestration."""
    text = _makefile_text()
    for target in REMOVED_PUBLIC_TARGETS:
        assert f"\n{target}:" not in f"\n{text}"


def test_gate_targets_delegate_to_grouped_gate_scripts() -> None:
    """Layer gates should delegate to scripts/gates instead of Make dependencies."""
    text = _makefile_text()
    assert "bash scripts/gates/gate_dev.sh" in _target_recipe(text, "gate-dev")
    assert "bash scripts/gates/gate_commit.sh" in _target_recipe(text, "gate-commit")
    assert "bash scripts/gates/gate_push.sh" in _target_recipe(text, "gate-push")
    assert "bash scripts/gates/gate_task_close.sh" in _target_recipe(
        text, "gate-task-close"
    )
    assert "bash scripts/gates/gate_ci_pr.sh" in _target_recipe(text, "gate-ci-pr")
    assert "bash scripts/gates/gate_heavy_advisory.sh" in _target_recipe(
        text, "gate-heavy-advisory"
    )
    assert "bash scripts/gates/gate_release.sh" in _target_recipe(text, "gate-release")


def test_public_checker_targets_emit_neutral_summary_outputs() -> None:
    """Public checkers should write stable JSON summaries useful from terminal/CI."""
    text = _makefile_text()
    manual_contract = _target_recipe(text, "test-ui-manual-contract")
    assert (
        "--json-out $(ARTIFACTS)/manual-ui/manual_contract_check.json"
        in manual_contract
    )
    release_evidence = _target_recipe(text, "release-evidence-check")
    assert (
        "--json-out $(ARTIFACTS)/release/release_evidence_check.json"
        in release_evidence
    )
    docs_check = _target_recipe(text, "docs-check")
    assert "bash scripts/gates/docs_check.sh" in docs_check
