from __future__ import annotations

from pathlib import Path

from translationzed_py.core.qa_service import (
    QA_CODE_NEWLINES,
    QA_CODE_TOKENS,
    QA_CODE_TRAILING,
    QAFinding,
    QAInputRow,
    QAService,
    build_qa_panel_plan,
    qa_finding_label,
)


def test_qa_finding_label_uses_relative_posix_path() -> None:
    root = Path("/tmp/proj")
    finding = QAFinding(
        file=root / "BE" / "ui.txt",
        row=7,
        code="qa.trailing",
        excerpt="Missing '.'",
    )
    assert qa_finding_label(finding=finding, root=root) == (
        "BE/ui.txt:8 · qa.trailing · Missing '.'"
    )


def test_build_qa_panel_plan_empty() -> None:
    plan = build_qa_panel_plan(
        findings=[],
        root=Path("/tmp/proj"),
        result_limit=200,
    )
    assert plan.items == ()
    assert plan.truncated is False
    assert plan.status_message == "No QA findings in current file."


def test_build_qa_panel_plan_truncates() -> None:
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
    root = Path("/tmp/proj")
    finding = QAFinding(
        file=root / "BE" / "ui.txt",
        row=0,
        code="qa.same_source",
        excerpt="Source equals translation",
    )
    service = QAService()
    label = service.finding_label(finding=finding, root=root)
    assert label.startswith("BE/ui.txt:1 · qa.same_source")
    plan = service.build_panel_plan(findings=[finding], root=root, result_limit=10)
    assert len(plan.items) == 1


def test_qa_service_scan_rows_runs_trailing_and_newline_checks() -> None:
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
    service = QAService()
    findings = service.scan_rows(
        file=Path("/tmp/proj/BE/ui.txt"),
        rows=(QAInputRow(row=0, source_text="Hello.", target_text="Privet"),),
        check_trailing=False,
        check_newlines=True,
    )
    assert findings == ()


def test_qa_service_scan_rows_detects_missing_protected_tokens() -> None:
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
