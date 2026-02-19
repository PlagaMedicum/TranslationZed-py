"""Test module for mutation summary and score-gate helpers."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_mutation_summary_module():
    path = Path("scripts/mutation_summary.py").resolve()
    spec = importlib.util.spec_from_file_location("mutation_summary_module", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_summarize_mutation_outputs_prefers_summary_and_emoji_counts() -> None:
    """Verify summary parser reads explicit counts and emoji progress snapshots."""
    module = _load_mutation_summary_module()
    run_log = "progress 🎉 7 🙁 2 ⏰ 1 🤔 3 🔇 4\n"
    results = "\n".join(
        (
            "killed: 9",
            "survived: 1",
            "timeout: 2",
            "suspicious: 1",
            "skipped: 5",
        )
    )
    summary = module.summarize_mutation_outputs(run_log, results)
    assert summary.killed == 9
    assert summary.survived == 1
    assert summary.timeout == 2
    assert summary.suspicious == 1
    assert summary.skipped == 5
    assert summary.actionable_total == 13
    assert summary.total == 18
    assert round(summary.killed_percent, 3) == round(100.0 * 9 / 13, 3)


def test_summarize_mutation_outputs_falls_back_to_line_status_counts() -> None:
    """Verify parser falls back to per-line status counting when no summary exists."""
    module = _load_mutation_summary_module()
    results = "\n".join(
        (
            "mutant_a survived",
            "mutant_b survived",
            "mutant_c killed",
            "mutant_d timeout",
            "mutant_e suspicious",
            "mutant_f skipped",
        )
    )
    summary = module.summarize_mutation_outputs("", results)
    assert summary.killed == 1
    assert summary.survived == 2
    assert summary.timeout == 1
    assert summary.suspicious == 1
    assert summary.skipped == 1
    assert summary.actionable_total == 5
    assert summary.total == 6


def test_evaluate_gate_supports_warn_fail_and_off_modes() -> None:
    """Verify gate evaluator keeps advisory behavior and supports fail mode."""
    module = _load_mutation_summary_module()
    summary = module.MutationSummary(
        killed=3,
        survived=7,
        timeout=0,
        suspicious=0,
        skipped=0,
        actionable_total=10,
        total=10,
        killed_percent=30.0,
    )

    warn = module.evaluate_gate(summary, mode="warn", min_killed_percent=40.0)
    assert warn.passed is True
    assert warn.warned is True

    fail = module.evaluate_gate(summary, mode="fail", min_killed_percent=40.0)
    assert fail.passed is False
    assert fail.warned is False

    off = module.evaluate_gate(summary, mode="off", min_killed_percent=95.0)
    assert off.passed is True
    assert off.warned is False
