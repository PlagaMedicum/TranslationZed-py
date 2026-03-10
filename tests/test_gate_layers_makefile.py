"""Regression contracts for layered gate composition in Makefile."""

from __future__ import annotations

from pathlib import Path

REQUIRED_GATES = (
    "gate-dev",
    "gate-commit",
    "gate-push",
    "gate-task-close",
    "gate-ci-pr",
    "gate-heavy-advisory",
    "gate-release",
)

LEGACY_UMBRELLA_TARGETS = (
    "check",
    "check-local",
    "verify",
    "verify-core",
    "verify-ci",
    "verify-ci-core",
    "verify-heavy",
    "verify-heavy-extra",
    "verify-fast",
)


def _makefile_text() -> str:
    return (Path(__file__).resolve().parents[1] / "Makefile").read_text(
        encoding="utf-8"
    )


def _target_dependencies(makefile_text: str, target: str) -> list[str]:
    lines = makefile_text.splitlines()
    for idx, line in enumerate(lines):
        if not line.startswith(f"{target}:"):
            continue
        payload = line.split(":", 1)[1].rstrip()
        chunks = [payload]
        next_idx = idx + 1
        while chunks[-1].endswith("\\") and next_idx < len(lines):
            chunks[-1] = chunks[-1][:-1].rstrip()
            continuation = lines[next_idx].strip()
            chunks.append(continuation)
            next_idx += 1
        deps = " ".join(chunks).split()
        return deps
    return []


def test_required_layered_gate_targets_exist() -> None:
    """Layered gate targets should be defined in Makefile."""
    text = _makefile_text()
    for target in REQUIRED_GATES:
        assert f"{target}:" in text


def test_legacy_umbrella_targets_removed() -> None:
    """Legacy umbrella targets should not remain after layered gate migration."""
    text = _makefile_text()
    for target in LEGACY_UMBRELLA_TARGETS:
        assert f"\n{target}:" not in text


def test_gate_dependencies_match_layered_contract() -> None:
    """Layered gates should compose through explicit non-overlapping dependencies."""
    text = _makefile_text()

    assert _target_dependencies(text, "gate-dev") == [
        "fmt-check-changed",
        "lint-check",
        "typecheck",
        "arch-check",
        "locale-agnostic-check",
    ]
    assert _target_dependencies(text, "gate-commit") == [
        "gate-dev",
        "test-ui-manual-contract",
    ]
    assert _target_dependencies(text, "gate-push") == [
        "gate-commit",
        "test-core-fast",
        "test-routed-fast",
        "test-readonly-clean",
    ]
    assert _target_dependencies(text, "gate-task-close") == [
        "gate-push",
        "test-cov",
        "docs-check",
        "test-perf-scale",
    ]

    ci_pr_deps = _target_dependencies(text, "gate-ci-pr")
    assert "fmt-check" in ci_pr_deps
    assert "lint-check" in ci_pr_deps
    assert "typecheck" in ci_pr_deps
    assert "arch-check" in ci_pr_deps
    assert "locale-agnostic-check" in ci_pr_deps
    assert "test-cov" in ci_pr_deps
    assert "docs-check" in ci_pr_deps
    assert "test-perf-scale" in ci_pr_deps
