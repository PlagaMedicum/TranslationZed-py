from __future__ import annotations

from pathlib import Path

from translationzed_py.core.qa_service import (
    QAFinding,
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
