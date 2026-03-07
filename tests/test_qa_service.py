"""Test module for qa service."""

from __future__ import annotations

from pathlib import Path

import pytest

from translationzed_py.core.qa_service import (
    QA_CODE_NEWLINES,
    QA_CODE_SAME_AS_SOURCE,
    QA_CODE_TOKENS,
    QA_CODE_TRAILING,
    QA_RULE_ORDER,
    QA_RULE_STATE_TEXT,
    QAFinding,
    QAInputRow,
    QARuleState,
    QAScanProgressSnapshot,
    QAService,
    build_qa_panel_plan,
    build_qa_progress_records,
    build_qa_progress_snapshot,
    qa_completion_ratio,
    qa_finding_label,
    transition_qa_rule_state,
)


def test_qa_finding_label_uses_relative_posix_path() -> None:
    """Verify qa finding label uses relative posix path."""
    root = Path("/tmp/proj")
    finding = QAFinding(
        file=root / "BE" / "ui.txt",
        row=7,
        code="qa.trailing",
        excerpt="Missing '.'",
    )
    assert qa_finding_label(finding=finding, root=root) == (
        "#8 trailing W/F · Missing '.' · BE/ui.txt"
    )


def test_build_qa_panel_plan_empty() -> None:
    """Verify build qa panel plan empty."""
    plan = build_qa_panel_plan(
        findings=[],
        root=Path("/tmp/proj"),
        result_limit=200,
    )
    assert plan.items == ()
    assert plan.truncated is False
    assert plan.status_message == "No QA findings in current file."


def test_build_qa_panel_plan_truncates() -> None:
    """Verify build qa panel plan truncates."""
    root = Path("/tmp/proj")
    findings = [
        QAFinding(
            file=root / "BE" / "ui.txt",
            row=i,
            code="qa.newline",
            excerpt=f"row {i}",
        )
        for i in range(3)
    ]
    plan = build_qa_panel_plan(
        findings=findings,
        root=root,
        result_limit=2,
    )
    assert len(plan.items) == 2
    assert plan.truncated is True
    assert plan.status_message == "Showing first 2 QA findings (limit 2)."


def test_build_qa_panel_plan_deprioritizes_same_as_source() -> None:
    """Verify same-as-source findings are listed after other standard checks."""
    root = Path("/tmp/proj")
    findings = [
        QAFinding(
            file=root / "BE" / "ui.txt",
            row=0,
            code=QA_CODE_SAME_AS_SOURCE,
            excerpt='Same text: "A"',
            severity="warning",
            group="content",
        ),
        QAFinding(
            file=root / "BE" / "ui.txt",
            row=10,
            code=QA_CODE_TRAILING,
            excerpt="S:'.' T:''",
            severity="warning",
            group="format",
        ),
    ]
    plan = build_qa_panel_plan(
        findings=findings,
        root=root,
        result_limit=1,
    )
    assert len(plan.items) == 1
    assert plan.items[0].finding.code == QA_CODE_TRAILING
    assert plan.truncated is True


def test_qa_service_wrapper_delegates() -> None:
    """Verify qa service wrapper delegates."""
    root = Path("/tmp/proj")
    finding = QAFinding(
        file=root / "BE" / "ui.txt",
        row=0,
        code="qa.same_source",
        excerpt="Source equals translation",
    )
    service = QAService()
    label = service.finding_label(finding=finding, root=root)
    assert label.startswith("#1 same-src W/F")
    assert label.endswith("· BE/ui.txt")
    plan = service.build_panel_plan(findings=[finding], root=root, result_limit=10)
    assert len(plan.items) == 1


def test_qa_service_scan_rows_runs_trailing_and_newline_checks() -> None:
    """Verify qa service scan rows runs trailing and newline checks."""
    service = QAService()
    findings = service.scan_rows(
        file=Path("/tmp/proj/BE/ui.txt"),
        rows=(
            QAInputRow(row=0, source_text="Hello.", target_text="Privet"),
            QAInputRow(row=1, source_text="Line 1\nLine 2", target_text="Radok"),
        ),
        check_trailing=True,
        check_newlines=True,
    )
    assert [f.code for f in findings] == [QA_CODE_TRAILING, QA_CODE_NEWLINES]
    assert findings[0].row == 0
    assert findings[1].row == 1


def test_qa_service_scan_rows_respects_check_toggles() -> None:
    """Verify qa service scan rows respects check toggles."""
    service = QAService()
    findings = service.scan_rows(
        file=Path("/tmp/proj/BE/ui.txt"),
        rows=(QAInputRow(row=0, source_text="Hello.", target_text="Privet"),),
        check_trailing=False,
        check_newlines=True,
    )
    assert findings == ()


def test_qa_service_scan_rows_detects_missing_protected_tokens() -> None:
    """Verify qa service scan rows detects missing protected tokens."""
    service = QAService()
    findings = service.scan_rows(
        file=Path("/tmp/proj/BE/ui.txt"),
        rows=(
            QAInputRow(
                row=0,
                source_text="<LINE> [img=music] %1 <gasps from the courtroom>",
                target_text="<gasps from the courtroom>",
            ),
        ),
        check_trailing=False,
        check_newlines=False,
        check_tokens=True,
    )
    assert len(findings) == 1
    assert findings[0].code == QA_CODE_TOKENS
    assert "<LINE>" in findings[0].excerpt
    assert "[img=music]" in findings[0].excerpt
    assert "%1" in findings[0].excerpt


def test_qa_service_auto_mark_rows_is_sorted_unique() -> None:
    """Verify qa service auto mark rows is sorted unique."""
    service = QAService()
    rows = service.auto_mark_rows(
        [
            QAFinding(
                file=Path("/tmp/proj/BE/ui.txt"),
                row=5,
                code=QA_CODE_TRAILING,
                excerpt="x",
            ),
            QAFinding(
                file=Path("/tmp/proj/BE/ui.txt"),
                row=2,
                code=QA_CODE_NEWLINES,
                excerpt="y",
            ),
            QAFinding(
                file=Path("/tmp/proj/BE/ui.txt"),
                row=5,
                code=QA_CODE_NEWLINES,
                excerpt="z",
            ),
        ]
    )
    assert rows == (2, 5)


def test_qa_service_scan_rows_detects_same_as_source_when_enabled() -> None:
    """Verify qa service scan rows detects same as source when enabled."""
    service = QAService()
    findings = service.scan_rows(
        file=Path("/tmp/proj/BE/ui.txt"),
        rows=(QAInputRow(row=3, source_text="Same", target_text="Same"),),
        check_trailing=False,
        check_newlines=False,
        check_tokens=False,
        check_same_as_source=True,
    )
    assert len(findings) == 1
    assert findings[0].code == QA_CODE_SAME_AS_SOURCE
    assert findings[0].group == "content"
    assert findings[0].excerpt.startswith('Same text: "Same"')


def test_qa_service_navigation_plan_moves_and_wraps() -> None:
    """Verify qa service navigation plan moves and wraps."""
    service = QAService()
    file_path = Path("/tmp/proj/BE/ui.txt")
    findings = [
        QAFinding(file=file_path, row=1, code=QA_CODE_TRAILING, excerpt="x"),
        QAFinding(file=file_path, row=3, code=QA_CODE_NEWLINES, excerpt="y"),
    ]
    next_plan = service.build_navigation_plan(
        findings=findings,
        current_path=file_path,
        current_row=1,
        direction=1,
        root=Path("/tmp/proj"),
    )
    assert next_plan.finding is not None
    assert next_plan.finding.row == 3
    assert next_plan.status_message.startswith("QA 2/2")

    prev_wrap_plan = service.build_navigation_plan(
        findings=findings,
        current_path=file_path,
        current_row=1,
        direction=-1,
        root=Path("/tmp/proj"),
    )
    assert prev_wrap_plan.finding is not None
    assert prev_wrap_plan.finding.row == 3


def test_build_qa_progress_records_uses_fixed_rule_order() -> None:
    """Verify QA progress records use deterministic fixed ordering."""
    records = build_qa_progress_records(run_id="run-1")
    assert tuple(record.rule_id for record in records) == QA_RULE_ORDER
    assert all(record.state == QARuleState.QUEUED for record in records)
    assert QA_RULE_STATE_TEXT[QARuleState.QUEUED] == "Queued"
    assert QA_RULE_STATE_TEXT[QARuleState.RUNNING] == "Running…"
    assert QA_RULE_STATE_TEXT[QARuleState.DONE] == "Completed"
    assert QA_RULE_STATE_TEXT[QARuleState.SKIPPED] == "Skipped"
    assert QA_RULE_STATE_TEXT[QARuleState.FAILED] == "Failed"


def test_build_qa_progress_records_can_mark_disabled_rules_as_skipped() -> None:
    """Verify disabled rules are deterministic skipped records when requested."""
    records = build_qa_progress_records(
        run_id="run-1",
        enabled_rules=("trailing", "tokens"),
        skip_disabled_rules=True,
        disabled_note="Disabled by settings.",
    )
    by_rule = {record.rule_id: record for record in records}
    assert by_rule["trailing"].state == QARuleState.QUEUED
    assert by_rule["tokens"].state == QARuleState.QUEUED
    assert by_rule["newlines"].state == QARuleState.SKIPPED
    assert by_rule["same_source"].state == QARuleState.SKIPPED
    assert by_rule["languagetool"].state == QARuleState.SKIPPED
    assert by_rule["newlines"].note == "Disabled by settings."


def test_transition_qa_rule_state_accepts_legal_transitions() -> None:
    """Verify queued->running->done transition chain is accepted."""
    records = build_qa_progress_records(run_id="run-1")
    records = transition_qa_rule_state(
        records=records,
        run_id="run-1",
        rule_id="trailing",
        new_state=QARuleState.RUNNING,
        timestamp_ms=10,
    )
    trailing = next(record for record in records if record.rule_id == "trailing")
    assert trailing.started_at_ms == 10
    assert trailing.state == QARuleState.RUNNING

    records = transition_qa_rule_state(
        records=records,
        run_id="run-1",
        rule_id="trailing",
        new_state=QARuleState.DONE,
        timestamp_ms=25,
        findings_count=3,
        note="ok",
    )
    trailing = next(record for record in records if record.rule_id == "trailing")
    assert trailing.state == QARuleState.DONE
    assert trailing.ended_at_ms == 25
    assert trailing.findings_count == 3
    assert trailing.note == "ok"


def test_transition_qa_rule_state_rejects_illegal_transitions() -> None:
    """Verify invalid state transitions are rejected with ValueError."""
    records = build_qa_progress_records(run_id="run-1")
    with pytest.raises(ValueError, match="illegal QA rule transition"):
        transition_qa_rule_state(
            records=records,
            run_id="run-1",
            rule_id="trailing",
            new_state=QARuleState.DONE,
        )

    running = transition_qa_rule_state(
        records=records,
        run_id="run-1",
        rule_id="trailing",
        new_state=QARuleState.RUNNING,
    )
    with pytest.raises(ValueError, match="illegal QA rule transition"):
        transition_qa_rule_state(
            records=running,
            run_id="run-1",
            rule_id="trailing",
            new_state=QARuleState.QUEUED,
        )
    done = transition_qa_rule_state(
        records=running,
        run_id="run-1",
        rule_id="trailing",
        new_state=QARuleState.DONE,
    )
    with pytest.raises(ValueError, match="illegal QA rule transition"):
        transition_qa_rule_state(
            records=done,
            run_id="run-1",
            rule_id="trailing",
            new_state=QARuleState.RUNNING,
        )


def test_transition_qa_rule_state_rejects_second_running_in_same_run() -> None:
    """Verify running state cannot be entered twice for one rule/run."""
    records = build_qa_progress_records(run_id="run-1")
    running = transition_qa_rule_state(
        records=records,
        run_id="run-1",
        rule_id="trailing",
        new_state=QARuleState.RUNNING,
        timestamp_ms=10,
    )
    with pytest.raises(ValueError, match="already in state 'running'"):
        transition_qa_rule_state(
            records=running,
            run_id="run-1",
            rule_id="trailing",
            new_state=QARuleState.RUNNING,
            timestamp_ms=15,
        )


def test_qa_completion_ratio_is_non_decreasing_for_legal_sequence() -> None:
    """Verify completion ratio does not decrease for legal transitions."""
    records = build_qa_progress_records(run_id="run-1")
    ratios = [qa_completion_ratio(records)]

    records = transition_qa_rule_state(
        records=records,
        run_id="run-1",
        rule_id="trailing",
        new_state=QARuleState.RUNNING,
        timestamp_ms=10,
    )
    ratios.append(qa_completion_ratio(records))
    records = transition_qa_rule_state(
        records=records,
        run_id="run-1",
        rule_id="trailing",
        new_state=QARuleState.DONE,
        timestamp_ms=20,
    )
    ratios.append(qa_completion_ratio(records))
    records = transition_qa_rule_state(
        records=records,
        run_id="run-1",
        rule_id="newlines",
        new_state=QARuleState.RUNNING,
        timestamp_ms=21,
    )
    ratios.append(qa_completion_ratio(records))
    records = transition_qa_rule_state(
        records=records,
        run_id="run-1",
        rule_id="newlines",
        new_state=QARuleState.SKIPPED,
        timestamp_ms=22,
    )
    ratios.append(qa_completion_ratio(records))
    assert ratios == sorted(ratios)


def test_build_qa_progress_snapshot_preserves_schema_fields() -> None:
    """Verify progress snapshot fields and summary passthrough are preserved."""
    records = build_qa_progress_records(run_id="run-1")
    snapshot = build_qa_progress_snapshot(
        run_id="run-1",
        file_path=Path("/tmp/proj/BE/ui.txt"),
        ordered_rules=records,
        final_summary="QA completed: 0 finding(s) across 0/5 rules.",
    )
    assert isinstance(snapshot, QAScanProgressSnapshot)
    assert snapshot.run_id == "run-1"
    assert snapshot.file_path == "/tmp/proj/BE/ui.txt"
    assert tuple(record.rule_id for record in snapshot.ordered_rules) == QA_RULE_ORDER
    assert snapshot.completion_ratio == 0.0
    assert snapshot.final_summary == "QA completed: 0 finding(s) across 0/5 rules."


def test_qa_service_progress_wrappers_delegate() -> None:
    """Verify QAService wrappers delegate progress-model helpers."""
    service = QAService()
    records = service.build_progress_records(run_id="run-1")
    assert len(records) == len(QA_RULE_ORDER)
    records = service.transition_rule_state(
        records=records,
        run_id="run-1",
        rule_id="trailing",
        new_state=QARuleState.RUNNING,
        timestamp_ms=10,
    )
    ratio = service.completion_ratio(records)
    assert ratio == 0.0
    snapshot = service.build_progress_snapshot(
        run_id="run-1",
        file_path="/tmp/proj/BE/ui.txt",
        ordered_rules=records,
        final_summary="scan running",
    )
    assert snapshot.final_summary == "scan running"
