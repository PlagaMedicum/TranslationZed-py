from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class QAFinding:
    file: Path
    row: int
    code: str
    excerpt: str
    severity: str = "warning"


@dataclass(frozen=True, slots=True)
class QAPanelItem:
    finding: QAFinding
    label: str


@dataclass(frozen=True, slots=True)
class QAPanelPlan:
    status_message: str
    items: tuple[QAPanelItem, ...]
    truncated: bool


@dataclass(frozen=True, slots=True)
class QAService:
    def finding_label(self, *, finding: QAFinding, root: Path) -> str:
        return qa_finding_label(finding=finding, root=root)

    def build_panel_plan(
        self,
        *,
        findings: Sequence[QAFinding],
        root: Path,
        result_limit: int,
    ) -> QAPanelPlan:
        return build_qa_panel_plan(
            findings=findings,
            root=root,
            result_limit=result_limit,
        )


def qa_finding_label(*, finding: QAFinding, root: Path) -> str:
    try:
        rel = finding.file.relative_to(root).as_posix()
    except ValueError:
        rel = finding.file.as_posix()
    label = f"{rel}:{finding.row + 1} · {finding.code}"
    excerpt = finding.excerpt.strip()
    if not excerpt:
        return label
    return f"{label} · {excerpt}"


def build_qa_panel_plan(
    *,
    findings: Sequence[QAFinding],
    root: Path,
    result_limit: int,
) -> QAPanelPlan:
    if not findings:
        return QAPanelPlan(
            status_message="No QA findings in current file.",
            items=(),
            truncated=False,
        )
    limit = max(1, int(result_limit))
    items: list[QAPanelItem] = []
    truncated = False
    for finding in findings:
        items.append(
            QAPanelItem(
                finding=finding,
                label=qa_finding_label(finding=finding, root=root),
            )
        )
        if len(items) >= limit:
            truncated = len(findings) > limit
            break
    if truncated:
        return QAPanelPlan(
            status_message=f"Showing first {len(items)} QA findings (limit {limit}).",
            items=tuple(items),
            truncated=True,
        )
    return QAPanelPlan(
        status_message=f"{len(items)} QA findings in current scope.",
        items=tuple(items),
        truncated=False,
    )
