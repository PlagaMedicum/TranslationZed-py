"""Qa service module."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .qa_rules import (
    has_missing_trailing_fragment,
    has_newline_mismatch,
    missing_protected_tokens,
    newline_count,
    same_as_source,
    trailing_fragment,
)

QA_CODE_TRAILING = "qa.trailing"
QA_CODE_NEWLINES = "qa.newlines"
QA_CODE_TOKENS = "qa.tokens"
QA_CODE_SAME_AS_SOURCE = "qa.same_source"


@dataclass(frozen=True, slots=True)
class QAInputRow:
    """Represent QAInputRow."""

    row: int
    source_text: str
    target_text: str


@dataclass(frozen=True, slots=True)
class QAFinding:
    """Represent QAFinding."""

    file: Path
    row: int
    code: str
    excerpt: str
    severity: str = "warning"
    group: str = "format"


@dataclass(frozen=True, slots=True)
class QAPanelItem:
    """Represent QAPanelItem."""

    finding: QAFinding
    label: str


@dataclass(frozen=True, slots=True)
class QAPanelPlan:
    """Represent QAPanelPlan."""

    status_message: str
    items: tuple[QAPanelItem, ...]
    truncated: bool


@dataclass(frozen=True, slots=True)
class QANavigationPlan:
    """Represent QANavigationPlan."""

    finding: QAFinding | None
    status_message: str


@dataclass(frozen=True, slots=True)
class QAService:
    """Represent QAService."""

    def finding_label(self, *, finding: QAFinding, root: Path) -> str:
        """Execute finding label."""
        return qa_finding_label(finding=finding, root=root)

    def build_panel_plan(
        self,
        *,
        findings: Sequence[QAFinding],
        root: Path,
        result_limit: int,
    ) -> QAPanelPlan:
        """Build panel plan."""
        return build_qa_panel_plan(
            findings=findings,
            root=root,
            result_limit=result_limit,
        )

    def scan_rows(
        self,
        *,
        file: Path,
        rows: Sequence[QAInputRow],
        check_trailing: bool,
        check_newlines: bool,
        check_tokens: bool = False,
        check_same_as_source: bool = False,
    ) -> tuple[QAFinding, ...]:
        """Execute scan rows."""
        return scan_qa_rows(
            file=file,
            rows=rows,
            check_trailing=check_trailing,
            check_newlines=check_newlines,
            check_tokens=check_tokens,
            check_same_as_source=check_same_as_source,
        )

    def auto_mark_rows(self, findings: Sequence[QAFinding]) -> tuple[int, ...]:
        """Execute auto mark rows."""
        return build_auto_mark_rows(findings)

    def build_navigation_plan(
        self,
        *,
        findings: Sequence[QAFinding],
        current_path: Path | None,
        current_row: int | None,
        direction: int,
        root: Path,
    ) -> QANavigationPlan:
        """Build navigation plan."""
        return build_qa_navigation_plan(
            findings=findings,
            current_path=current_path,
            current_row=current_row,
            direction=direction,
            root=root,
        )


def qa_finding_label(*, finding: QAFinding, root: Path) -> str:
    """Execute qa finding label."""
    try:
        rel = finding.file.relative_to(root).as_posix()
    except ValueError:
        rel = finding.file.as_posix()
    label = (
        f"{rel}:{finding.row + 1} · "
        f"{finding.severity.lower()}/{finding.group.lower()} · {finding.code}"
    )
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
    """Build qa panel plan."""
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


def scan_qa_rows(
    *,
    file: Path,
    rows: Sequence[QAInputRow],
    check_trailing: bool,
    check_newlines: bool,
    check_tokens: bool,
    check_same_as_source: bool,
) -> tuple[QAFinding, ...]:
    """Execute scan qa rows."""
    findings: list[QAFinding] = []
    for row in rows:
        if check_trailing and has_missing_trailing_fragment(
            row.source_text,
            row.target_text,
        ):
            findings.append(
                QAFinding(
                    file=file,
                    row=row.row,
                    code=QA_CODE_TRAILING,
                    excerpt=_trailing_excerpt(row.source_text, row.target_text),
                    severity="warning",
                    group="format",
                )
            )
        if check_newlines and has_newline_mismatch(row.source_text, row.target_text):
            findings.append(
                QAFinding(
                    file=file,
                    row=row.row,
                    code=QA_CODE_NEWLINES,
                    excerpt=_newline_excerpt(row.source_text, row.target_text),
                    severity="warning",
                    group="format",
                )
            )
        if check_tokens:
            missing_tokens = missing_protected_tokens(
                row.source_text,
                row.target_text,
            )
            if missing_tokens:
                findings.append(
                    QAFinding(
                        file=file,
                        row=row.row,
                        code=QA_CODE_TOKENS,
                        excerpt=_tokens_excerpt(missing_tokens),
                        severity="warning",
                        group="format",
                    )
                )
        if (
            check_same_as_source
            and row.source_text
            and row.target_text
            and same_as_source(row.source_text, row.target_text)
        ):
            findings.append(
                QAFinding(
                    file=file,
                    row=row.row,
                    code=QA_CODE_SAME_AS_SOURCE,
                    excerpt="Translation equals source",
                    severity="warning",
                    group="content",
                )
            )
    return tuple(findings)


def build_auto_mark_rows(findings: Sequence[QAFinding]) -> tuple[int, ...]:
    """Build auto mark rows."""
    rows: set[int] = set()
    for finding in findings:
        if finding.severity.lower() != "warning":
            continue
        rows.add(finding.row)
    return tuple(sorted(rows))


def build_qa_navigation_plan(
    *,
    findings: Sequence[QAFinding],
    current_path: Path | None,
    current_row: int | None,
    direction: int,
    root: Path,
) -> QANavigationPlan:
    """Build qa navigation plan."""
    if not findings:
        return QANavigationPlan(
            finding=None,
            status_message="No QA findings in current scope.",
        )
    ordered = sorted(findings, key=_finding_sort_key)
    if not current_path or current_row is None:
        initial_target = ordered[0 if direction >= 0 else -1]
        return QANavigationPlan(
            finding=initial_target,
            status_message=f"QA 1/{len(ordered)} · {initial_target.code}",
        )
    anchor = (current_path.as_posix(), int(current_row))
    target: QAFinding | None = None
    if direction >= 0:
        for candidate in ordered:
            key = _finding_sort_key(candidate)
            if (key[0], key[1]) > anchor:
                target = candidate
                break
        if target is None:
            target = ordered[0]
    else:
        for candidate in reversed(ordered):
            key = _finding_sort_key(candidate)
            if (key[0], key[1]) < anchor:
                target = candidate
                break
        if target is None:
            target = ordered[-1]
    assert target is not None
    position = ordered.index(target) + 1
    label = qa_finding_label(finding=target, root=root)
    return QANavigationPlan(
        finding=target,
        status_message=f"QA {position}/{len(ordered)} · {label}",
    )


def _trailing_excerpt(source_text: str, target_text: str) -> str:
    """Execute trailing excerpt."""
    source_tail = trailing_fragment(source_text)
    target_tail = trailing_fragment(target_text)
    return f"S:{source_tail!r} T:{target_tail!r}"


def _newline_excerpt(source_text: str, target_text: str) -> str:
    """Execute newline excerpt."""
    source_nl = newline_count(source_text)
    target_nl = newline_count(target_text)
    return f"S newlines={source_nl}, T newlines={target_nl}"


def _tokens_excerpt(tokens: Sequence[str]) -> str:
    """Execute tokens excerpt."""
    counts = Counter(tokens)
    parts: list[str] = []
    for token, count in counts.items():
        if count == 1:
            parts.append(token)
        else:
            parts.append(f"{token}x{count}")
    return "Missing: " + ", ".join(parts[:5])


def _finding_sort_key(finding: QAFinding) -> tuple[str, int, str]:
    """Execute finding sort key."""
    return (
        finding.file.as_posix(),
        finding.row,
        finding.code,
    )
