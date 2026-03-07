"""Focused tests for v0.9 QA progress rule-state model."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

import translationzed_py.core.qa_service as qa_service
from translationzed_py.core.qa_service import (
    QA_RULE_ORDER,
    QA_RULE_STATE_TEXT,
    QAFinding,
    QARuleProgressRecord,
    QARuleState,
    build_auto_mark_rows,
    build_qa_navigation_plan,
    build_qa_progress_records,
    build_qa_progress_snapshot,
    qa_completion_ratio,
    qa_finding_label,
    transition_qa_rule_state,
)


@pytest.mark.parametrize(
    ("source_state", "target_state"),
    [
        (QARuleState.QUEUED, QARuleState.RUNNING),
        (QARuleState.RUNNING, QARuleState.DONE),
        (QARuleState.RUNNING, QARuleState.SKIPPED),
        (QARuleState.RUNNING, QARuleState.FAILED),
    ],
)
def test_progress_model_allows_expected_transition_table(
    source_state: QARuleState,
    target_state: QARuleState,
) -> None:
    """Verify legal transition-table rows are accepted."""
    records = build_qa_progress_records(run_id="run-1")
    if source_state == QARuleState.RUNNING:
        records = transition_qa_rule_state(
            records=records,
            run_id="run-1",
            rule_id="trailing",
            new_state=QARuleState.RUNNING,
            timestamp_ms=10,
        )
    transitioned = transition_qa_rule_state(
        records=records,
        run_id="run-1",
        rule_id="trailing",
        new_state=target_state,
        timestamp_ms=20,
    )
    trailing = next(record for record in transitioned if record.rule_id == "trailing")
    assert trailing.state == target_state


@pytest.mark.parametrize(
    ("source_state", "target_state"),
    [
        (QARuleState.QUEUED, QARuleState.DONE),
        (QARuleState.QUEUED, QARuleState.SKIPPED),
        (QARuleState.QUEUED, QARuleState.FAILED),
        (QARuleState.RUNNING, QARuleState.QUEUED),
        (QARuleState.DONE, QARuleState.RUNNING),
        (QARuleState.SKIPPED, QARuleState.RUNNING),
        (QARuleState.FAILED, QARuleState.RUNNING),
    ],
)
def test_progress_model_rejects_invalid_transition_table(
    source_state: QARuleState,
    target_state: QARuleState,
) -> None:
    """Verify illegal transition-table rows are rejected."""
    records = build_qa_progress_records(run_id="run-1")
    if source_state == QARuleState.RUNNING:
        records = transition_qa_rule_state(
            records=records,
            run_id="run-1",
            rule_id="trailing",
            new_state=QARuleState.RUNNING,
            timestamp_ms=10,
        )
    elif source_state in {
        QARuleState.DONE,
        QARuleState.SKIPPED,
        QARuleState.FAILED,
    }:
        records = transition_qa_rule_state(
            records=records,
            run_id="run-1",
            rule_id="trailing",
            new_state=QARuleState.RUNNING,
            timestamp_ms=10,
        )
        records = transition_qa_rule_state(
            records=records,
            run_id="run-1",
            rule_id="trailing",
            new_state=source_state,
            timestamp_ms=20,
        )
    with pytest.raises(ValueError, match="illegal QA rule transition"):
        transition_qa_rule_state(
            records=records,
            run_id="run-1",
            rule_id="trailing",
            new_state=target_state,
            timestamp_ms=30,
        )


def test_qa_completion_ratio_bounds() -> None:
    """Verify completion ratio stays within [0, 1] bounds."""
    queued = build_qa_progress_records(run_id="run-1")
    assert qa_completion_ratio(queued) == 0.0

    records = queued
    for index, rule_id in enumerate(QA_RULE_ORDER):
        records = transition_qa_rule_state(
            records=records,
            run_id="run-1",
            rule_id=rule_id,
            new_state=QARuleState.RUNNING,
            timestamp_ms=100 + (index * 2),
        )
        records = transition_qa_rule_state(
            records=records,
            run_id="run-1",
            rule_id=rule_id,
            new_state=QARuleState.DONE,
            timestamp_ms=101 + (index * 2),
        )
    assert qa_completion_ratio(records) == 1.0


def test_progress_snapshot_keeps_order_and_state_text_contract() -> None:
    """Verify snapshot preserves fixed order and state-text mapping contract."""
    records = build_qa_progress_records(run_id="run-1")
    snapshot = build_qa_progress_snapshot(
        run_id="run-1",
        file_path="/tmp/proj/BE/ui.txt",
        ordered_rules=records,
        final_summary="summary",
    )
    assert tuple(record.rule_id for record in snapshot.ordered_rules) == QA_RULE_ORDER
    assert QA_RULE_STATE_TEXT[QARuleState.QUEUED] == "Queued"
    assert QA_RULE_STATE_TEXT[QARuleState.RUNNING] == "Running…"
    assert QA_RULE_STATE_TEXT[QARuleState.DONE] == "Completed"
    assert QA_RULE_STATE_TEXT[QARuleState.SKIPPED] == "Skipped"
    assert QA_RULE_STATE_TEXT[QARuleState.FAILED] == "Failed"


def test_transition_updates_timestamps_findings_and_note() -> None:
    """Verify transition updates timestamp, findings count, and note values."""
    records = build_qa_progress_records(run_id="run-1")
    records = transition_qa_rule_state(
        records=records,
        run_id="run-1",
        rule_id="trailing",
        new_state=QARuleState.RUNNING,
        timestamp_ms=123,
        note="running",
    )
    records = transition_qa_rule_state(
        records=records,
        run_id="run-1",
        rule_id="trailing",
        new_state=QARuleState.FAILED,
        timestamp_ms=140,
        findings_count=2,
        note="rule exception",
    )
    trailing = next(record for record in records if record.rule_id == "trailing")
    assert trailing.started_at_ms == 123
    assert trailing.ended_at_ms == 140
    assert trailing.findings_count == 2
    assert trailing.note == "rule exception"


def test_qa_finding_label_handles_non_relative_path_and_blank_excerpt() -> None:
    """Verify label formatter falls back to absolute path and path-only summary."""
    finding = QAFinding(
        file=Path("/tmp/external.txt"),
        row=0,
        code="",
        excerpt="   ",
        severity="critical",
        group="",
    )
    label = qa_finding_label(finding=finding, root=Path("/tmp/project"))
    assert label == "#1 qa C/U · /tmp/external.txt"


def test_build_auto_mark_rows_ignores_non_warning_findings() -> None:
    """Verify auto-mark only collects warning severities."""
    findings = [
        QAFinding(
            file=Path("/tmp/p/BE/ui.txt"),
            row=4,
            code="qa.trailing",
            excerpt="x",
            severity="error",
        ),
        QAFinding(
            file=Path("/tmp/p/BE/ui.txt"),
            row=2,
            code="qa.newlines",
            excerpt="y",
            severity="warning",
        ),
    ]
    assert build_auto_mark_rows(findings) == (2,)


def test_progress_records_require_non_empty_run_id() -> None:
    """Verify progress records builder rejects empty run IDs."""
    with pytest.raises(ValueError, match="run_id must be non-empty"):
        build_qa_progress_records(run_id="   ")


def test_transition_rejects_empty_run_id_and_empty_records() -> None:
    """Verify transition helper validates run_id and records presence."""
    records = build_qa_progress_records(run_id="run-1")
    with pytest.raises(ValueError, match="run_id must be non-empty"):
        transition_qa_rule_state(
            records=records,
            run_id="   ",
            rule_id="trailing",
            new_state=QARuleState.RUNNING,
        )
    with pytest.raises(ValueError, match="records must be non-empty"):
        transition_qa_rule_state(
            records=(),
            run_id="run-1",
            rule_id="trailing",
            new_state=QARuleState.RUNNING,
        )


def test_transition_rejects_manual_second_running_attempt() -> None:
    """Verify started-at sentinel blocks entering running again in same run."""
    records = list(build_qa_progress_records(run_id="run-1"))
    records[0] = QARuleProgressRecord(
        run_id="run-1",
        rule_id="trailing",
        state=QARuleState.QUEUED,
        started_at_ms=10,
        ended_at_ms=None,
        findings_count=0,
        note="",
    )
    with pytest.raises(ValueError, match="cannot enter running state more than once"):
        transition_qa_rule_state(
            records=tuple(records),
            run_id="run-1",
            rule_id="trailing",
            new_state=QARuleState.RUNNING,
            timestamp_ms=20,
        )


def test_transition_ratio_guard_rejects_decrease(monkeypatch) -> None:
    """Verify ratio guard raises if internal ratio calculation decreases."""
    records = build_qa_progress_records(run_id="run-1")
    calls = {"count": 0}

    def _fake_ratio(_records):  # type: ignore[no-untyped-def]
        calls["count"] += 1
        return 0.8 if calls["count"] == 1 else 0.2

    monkeypatch.setattr(qa_service, "qa_completion_ratio", _fake_ratio)
    with pytest.raises(
        ValueError, match="completion ratio must be non-decreasing within one run"
    ):
        transition_qa_rule_state(
            records=records,
            run_id="run-1",
            rule_id="trailing",
            new_state=QARuleState.RUNNING,
        )


def test_qa_completion_ratio_handles_empty_record_sequence() -> None:
    """Verify ratio helper returns 0 for empty input."""
    assert qa_completion_ratio(()) == 0.0


def test_build_progress_snapshot_rejects_empty_run_id() -> None:
    """Verify snapshot builder rejects empty run IDs."""
    records = build_qa_progress_records(run_id="run-1")
    with pytest.raises(ValueError, match="run_id must be non-empty"):
        build_qa_progress_snapshot(
            run_id="  ",
            file_path="/tmp/proj/BE/ui.txt",
            ordered_rules=records,
            final_summary="summary",
        )


def test_navigation_plan_handles_empty_initial_and_wrap_forward() -> None:
    """Verify navigation helper supports empty scope, initial jump, and wrap-forward."""
    root = Path("/tmp/proj")
    file_path = root / "BE" / "ui.txt"
    findings = (
        QAFinding(file=file_path, row=1, code="qa.trailing", excerpt="x"),
        QAFinding(file=file_path, row=3, code="qa.newlines", excerpt="y"),
    )
    empty_plan = build_qa_navigation_plan(
        findings=(),
        current_path=file_path,
        current_row=1,
        direction=1,
        root=root,
    )
    assert empty_plan.finding is None
    assert empty_plan.status_message == "No QA findings in current scope."

    initial_backward = build_qa_navigation_plan(
        findings=findings,
        current_path=None,
        current_row=None,
        direction=-1,
        root=root,
    )
    assert initial_backward.finding is not None
    assert initial_backward.finding.row == 3

    wrapped = build_qa_navigation_plan(
        findings=findings,
        current_path=file_path,
        current_row=9,
        direction=1,
        root=root,
    )
    assert wrapped.finding is not None
    assert wrapped.finding.row == 1


def test_scan_rows_token_duplicates_and_same_source_blank_excerpt() -> None:
    """Verify token duplicate summary and blank same-source fallback excerpt."""
    service = qa_service.QAService()
    findings = service.scan_rows(
        file=Path("/tmp/proj/BE/ui.txt"),
        rows=(
            qa_service.QAInputRow(row=0, source_text="%1 %1", target_text=""),
            qa_service.QAInputRow(row=1, source_text="   ", target_text="   "),
        ),
        check_trailing=False,
        check_newlines=False,
        check_tokens=True,
        check_same_as_source=True,
    )
    by_code = {finding.code: finding for finding in findings}
    assert "%1x2" in by_code["qa.tokens"].excerpt
    assert by_code["qa.same_source"].excerpt == "Translation equals source"


def test_progress_record_validation_errors_and_missing_rule_guard() -> None:
    """Verify snapshot/transition validators catch malformed record sets."""
    records = build_qa_progress_records(run_id="run-1")
    first = records[0]

    with pytest.raises(ValueError, match="record run_id mismatch"):
        build_qa_progress_snapshot(
            run_id="run-2",
            file_path="/tmp/proj/BE/ui.txt",
            ordered_rules=records,
            final_summary="summary",
        )

    with pytest.raises(ValueError, match="duplicate QA rule progress record"):
        build_qa_progress_snapshot(
            run_id="run-1",
            file_path="/tmp/proj/BE/ui.txt",
            ordered_rules=(first, first),
            final_summary="summary",
        )

    queued_with_end = QARuleProgressRecord(
        run_id="run-1",
        rule_id="trailing",
        state=QARuleState.QUEUED,
        started_at_ms=None,
        ended_at_ms=1,
        findings_count=0,
        note="",
    )
    with pytest.raises(ValueError, match="queued rule cannot have ended_at_ms"):
        build_qa_progress_snapshot(
            run_id="run-1",
            file_path="/tmp/proj/BE/ui.txt",
            ordered_rules=(queued_with_end,),
            final_summary="summary",
        )

    running_with_end = QARuleProgressRecord(
        run_id="run-1",
        rule_id="trailing",
        state=QARuleState.RUNNING,
        started_at_ms=1,
        ended_at_ms=2,
        findings_count=0,
        note="",
    )
    with pytest.raises(ValueError, match="running rule cannot have ended_at_ms"):
        build_qa_progress_snapshot(
            run_id="run-1",
            file_path="/tmp/proj/BE/ui.txt",
            ordered_rules=(running_with_end,),
            final_summary="summary",
        )

    unknown_rule = QARuleProgressRecord(
        run_id="run-1",
        rule_id=cast("qa_service.QARuleId", "unknown_rule"),
        state=QARuleState.QUEUED,
        started_at_ms=None,
        ended_at_ms=None,
        findings_count=0,
        note="",
    )
    with pytest.raises(ValueError, match="unknown QA rule id"):
        build_qa_progress_snapshot(
            run_id="run-1",
            file_path="/tmp/proj/BE/ui.txt",
            ordered_rules=(unknown_rule,),
            final_summary="summary",
        )

    with pytest.raises(ValueError, match="missing QA progress record for rule"):
        transition_qa_rule_state(
            records=records[:2],
            run_id="run-1",
            rule_id="tokens",
            new_state=QARuleState.RUNNING,
        )


def test_compact_helpers_cover_edge_branches() -> None:
    """Verify compact helper edge paths used by label rendering."""
    assert qa_service._compact_excerpt("   ", max_chars=8) == ""
    assert qa_service._compact_excerpt("abcdef", max_chars=3) == "abc"
    assert qa_service._compact_excerpt("long excerpt text", max_chars=8) == "long..."
    assert qa_service._compact_path_label("abcdef", max_chars=3) == "def"
    assert qa_service._compact_path_label("abcdef", max_chars=2) == "ef"
