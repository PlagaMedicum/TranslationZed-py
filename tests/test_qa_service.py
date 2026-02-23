"""Test module for qa service."""

from __future__ import annotations

from pathlib import Path

from translationzed_py.core.qa_service import (
    QA_CODE_NEWLINES,
    QA_CODE_SAME_AS_SOURCE,
    QA_CODE_TOKENS,
    QA_CODE_TRAILING,
    QAFinding,
    QAInputRow,
    QAService,
    build_qa_panel_plan,
    qa_finding_label,
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
