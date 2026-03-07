"""Qa service module."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Literal

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
QA_CODE_LANGUAGETOOL = "qa.languagetool"

QARuleId = Literal[
    "trailing",
    "newlines",
    "tokens",
    "same_source",
    "languagetool",
]


class QARuleState(Enum):
    """Represent QA rule state."""

    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    SKIPPED = "skipped"
    FAILED = "failed"


QA_RULE_ORDER: tuple[QARuleId, ...] = (
    "trailing",
    "newlines",
    "tokens",
    "same_source",
    "languagetool",
)

QA_RULE_LABELS: dict[QARuleId, str] = {
    "trailing": "Missing trailing characters",
    "newlines": "Missing/extra newlines",
    "tokens": "Protected tokens / placeholders",
    "same_source": "Translation equals source",
    "languagetool": "LanguageTool",
}

QA_RULE_STATE_TEXT: dict[QARuleState, str] = {
    QARuleState.QUEUED: "Queued",
    QARuleState.RUNNING: "Running…",
    QARuleState.DONE: "Completed",
    QARuleState.SKIPPED: "Skipped",
    QARuleState.FAILED: "Failed",
}

_TERMINAL_QA_RULE_STATES = frozenset(
    {QARuleState.DONE, QARuleState.SKIPPED, QARuleState.FAILED}
)

_ALLOWED_QA_RULE_TRANSITIONS: dict[QARuleState, frozenset[QARuleState]] = {
    QARuleState.QUEUED: frozenset({QARuleState.RUNNING}),
    QARuleState.RUNNING: _TERMINAL_QA_RULE_STATES,
    QARuleState.DONE: frozenset(),
    QARuleState.SKIPPED: frozenset(),
    QARuleState.FAILED: frozenset(),
}
_QA_CODE_SHORT_LABELS = {
    QA_CODE_TRAILING: "trailing",
    QA_CODE_NEWLINES: "newlines",
    QA_CODE_TOKENS: "tokens",
    QA_CODE_SAME_AS_SOURCE: "same-src",
    QA_CODE_LANGUAGETOOL: "LT",
}
_QA_CODE_PRIORITY = {
    QA_CODE_TRAILING: 10,
    QA_CODE_NEWLINES: 20,
    QA_CODE_TOKENS: 30,
    QA_CODE_LANGUAGETOOL: 40,
    QA_CODE_SAME_AS_SOURCE: 90,
}
_QA_GROUP_SHORT_LABELS = {
    "format": "F",
    "content": "C",
    "language": "L",
}
_QA_SEVERITY_SHORT_LABELS = {
    "warning": "W",
    "error": "E",
    "info": "I",
}


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
class QARuleProgressRecord:
    """Represent QARuleProgressRecord."""

    run_id: str
    rule_id: QARuleId
    state: QARuleState
    started_at_ms: int | None
    ended_at_ms: int | None
    findings_count: int
    note: str = ""


@dataclass(frozen=True, slots=True)
class QAScanProgressSnapshot:
    """Represent QAScanProgressSnapshot."""

    run_id: str
    file_path: str
    ordered_rules: tuple[QARuleProgressRecord, ...]
    completion_ratio: float
    final_summary: str


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

    def build_progress_records(
        self,
        *,
        run_id: str,
        enabled_rules: Sequence[QARuleId] | None = None,
        skip_disabled_rules: bool = False,
        disabled_note: str = "Rule disabled.",
    ) -> tuple[QARuleProgressRecord, ...]:
        """Build progress records."""
        return build_qa_progress_records(
            run_id=run_id,
            enabled_rules=enabled_rules,
            skip_disabled_rules=skip_disabled_rules,
            disabled_note=disabled_note,
        )

    def transition_rule_state(
        self,
        *,
        records: Sequence[QARuleProgressRecord],
        run_id: str,
        rule_id: QARuleId,
        new_state: QARuleState,
        timestamp_ms: int | None = None,
        findings_count: int | None = None,
        note: str | None = None,
    ) -> tuple[QARuleProgressRecord, ...]:
        """Transition one QA rule state."""
        return transition_qa_rule_state(
            records=records,
            run_id=run_id,
            rule_id=rule_id,
            new_state=new_state,
            timestamp_ms=timestamp_ms,
            findings_count=findings_count,
            note=note,
        )

    def completion_ratio(self, records: Sequence[QARuleProgressRecord]) -> float:
        """Return completion ratio."""
        return qa_completion_ratio(records)

    def build_progress_snapshot(
        self,
        *,
        run_id: str,
        file_path: str | Path,
        ordered_rules: Sequence[QARuleProgressRecord],
        final_summary: str,
    ) -> QAScanProgressSnapshot:
        """Build progress snapshot."""
        return build_qa_progress_snapshot(
            run_id=run_id,
            file_path=file_path,
            ordered_rules=ordered_rules,
            final_summary=final_summary,
        )


def qa_finding_label(*, finding: QAFinding, root: Path) -> str:
    """Execute qa finding label."""
    try:
        rel = finding.file.relative_to(root).as_posix()
    except ValueError:
        rel = finding.file.as_posix()
    rule = _short_rule_label(finding.code)
    level = _short_level_label(finding.severity, finding.group)
    label = f"#{finding.row + 1} {rule} {level}"
    excerpt = _compact_excerpt(finding.excerpt, max_chars=80)
    if not excerpt:
        return f"{label} · {_compact_path_label(rel)}"
    return f"{label} · {excerpt} · {_compact_path_label(rel)}"


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
    ordered_findings = sorted(findings, key=_panel_sort_key)
    items: list[QAPanelItem] = []
    truncated = False
    for finding in ordered_findings:
        items.append(
            QAPanelItem(
                finding=finding,
                label=qa_finding_label(finding=finding, root=root),
            )
        )
        if len(items) >= limit:
            truncated = len(ordered_findings) > limit
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
                    excerpt=_same_source_excerpt(row.source_text),
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


def build_qa_progress_records(
    *,
    run_id: str,
    enabled_rules: Sequence[QARuleId] | None = None,
    skip_disabled_rules: bool = False,
    disabled_note: str = "Rule disabled.",
) -> tuple[QARuleProgressRecord, ...]:
    """Build ordered QA progress records for a scan run."""
    normalized_run_id = str(run_id).strip()
    if not normalized_run_id:
        raise ValueError("run_id must be non-empty")
    enabled = set(enabled_rules or QA_RULE_ORDER)
    ordered: list[QARuleProgressRecord] = []
    disabled_note_text = str(disabled_note).strip()
    for rule_id in QA_RULE_ORDER:
        state = QARuleState.QUEUED
        note = ""
        if rule_id not in enabled and skip_disabled_rules:
            state = QARuleState.SKIPPED
            note = disabled_note_text
        ordered.append(
            QARuleProgressRecord(
                run_id=normalized_run_id,
                rule_id=rule_id,
                state=state,
                started_at_ms=None,
                ended_at_ms=None,
                findings_count=0,
                note=note,
            )
        )
    return tuple(ordered)


def transition_qa_rule_state(
    *,
    records: Sequence[QARuleProgressRecord],
    run_id: str,
    rule_id: QARuleId,
    new_state: QARuleState,
    timestamp_ms: int | None = None,
    findings_count: int | None = None,
    note: str | None = None,
) -> tuple[QARuleProgressRecord, ...]:
    """Apply one legal state transition for a single QA rule."""
    current_records = tuple(records)
    normalized_run_id = str(run_id).strip()
    if not normalized_run_id:
        raise ValueError("run_id must be non-empty")
    if not current_records:
        raise ValueError("records must be non-empty")
    _validate_progress_records(current_records, run_id=normalized_run_id)
    record_index = _find_rule_record_index(current_records, rule_id=rule_id)
    current = current_records[record_index]
    if current.state == new_state:
        raise ValueError(
            f"rule '{rule_id}' is already in state '{current.state.value}'"
        )
    allowed = _ALLOWED_QA_RULE_TRANSITIONS[current.state]
    if new_state not in allowed:
        raise ValueError(
            "illegal QA rule transition: "
            f"{current.state.value} -> {new_state.value} for '{rule_id}'"
        )
    if new_state == QARuleState.RUNNING and current.started_at_ms is not None:
        raise ValueError(
            f"rule '{rule_id}' cannot enter running state more than once in a run"
        )
    before_ratio = qa_completion_ratio(current_records)
    updated = replace(
        current,
        state=new_state,
        started_at_ms=(
            timestamp_ms
            if new_state == QARuleState.RUNNING and timestamp_ms is not None
            else current.started_at_ms
        ),
        ended_at_ms=(
            timestamp_ms
            if new_state in _TERMINAL_QA_RULE_STATES and timestamp_ms is not None
            else current.ended_at_ms
        ),
        findings_count=(
            int(findings_count)
            if findings_count is not None
            else current.findings_count
        ),
        note=str(note).strip() if note is not None else current.note,
    )
    updated_records = (
        current_records[:record_index]
        + (updated,)
        + current_records[record_index + 1 :]
    )
    after_ratio = qa_completion_ratio(updated_records)
    if after_ratio + 1e-12 < before_ratio:
        raise ValueError("completion ratio must be non-decreasing within one run")
    return updated_records


def qa_completion_ratio(records: Sequence[QARuleProgressRecord]) -> float:
    """Return QA scan completion ratio based on terminal rule states."""
    total = len(records)
    if total <= 0:
        return 0.0
    completed = sum(1 for record in records if record.state in _TERMINAL_QA_RULE_STATES)
    ratio = completed / total
    return max(0.0, min(1.0, ratio))


def build_qa_progress_snapshot(
    *,
    run_id: str,
    file_path: str | Path,
    ordered_rules: Sequence[QARuleProgressRecord],
    final_summary: str,
) -> QAScanProgressSnapshot:
    """Build QA progress snapshot DTO for one run/file."""
    records = tuple(ordered_rules)
    normalized_run_id = str(run_id).strip()
    if not normalized_run_id:
        raise ValueError("run_id must be non-empty")
    _validate_progress_records(records, run_id=normalized_run_id)
    normalized_path = (
        file_path.as_posix()
        if isinstance(file_path, Path)
        else Path(str(file_path)).as_posix()
    )
    return QAScanProgressSnapshot(
        run_id=normalized_run_id,
        file_path=normalized_path,
        ordered_rules=records,
        completion_ratio=qa_completion_ratio(records),
        final_summary=str(final_summary),
    )


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


def _same_source_excerpt(source_text: str) -> str:
    """Build excerpt for same-as-source finding."""
    snippet = _compact_excerpt(source_text, max_chars=56)
    if not snippet:
        return "Translation equals source"
    return f'Same text: "{snippet}"'


def _short_rule_label(code: str) -> str:
    """Build compact rule label for QA list entries."""
    normalized = str(code).strip()
    if normalized in _QA_CODE_SHORT_LABELS:
        return _QA_CODE_SHORT_LABELS[normalized]
    if normalized.startswith("qa.") and len(normalized) > 3:
        return normalized[3:]
    return normalized or "qa"


def _short_level_label(severity: str, group: str) -> str:
    """Build compact severity/group label."""
    severity_key = str(severity).strip().lower()
    group_key = str(group).strip().lower()
    severity_short = _QA_SEVERITY_SHORT_LABELS.get(
        severity_key,
        severity_key[:1].upper() or "U",
    )
    group_short = _QA_GROUP_SHORT_LABELS.get(
        group_key,
        group_key[:1].upper() or "U",
    )
    return f"{severity_short}/{group_short}"


def _compact_excerpt(excerpt: str, *, max_chars: int) -> str:
    """Trim, normalize, and compact excerpt text for sidebar labels."""
    normalized = " ".join(str(excerpt).strip().split())
    if not normalized:
        return ""
    if max_chars <= 3 or len(normalized) <= max_chars:
        return normalized[:max_chars]
    return normalized[: max_chars - 3].rstrip() + "..."


def _compact_path_label(path: str, *, max_chars: int = 28) -> str:
    """Compact path label to keep QA entries readable in narrow sidebars."""
    normalized = str(path).strip()
    if len(normalized) <= max_chars:
        return normalized
    if max_chars <= 3:
        return normalized[-max_chars:]
    return "..." + normalized[-(max_chars - 3) :]


def _panel_sort_key(finding: QAFinding) -> tuple[int, str, int, str]:
    """Sort findings for QA panel with low-priority same-source entries last."""
    priority = _QA_CODE_PRIORITY.get(finding.code, 50)
    return (
        priority,
        finding.file.as_posix(),
        finding.row,
        finding.code,
    )


def _finding_sort_key(finding: QAFinding) -> tuple[str, int, str]:
    """Execute finding sort key."""
    return (
        finding.file.as_posix(),
        finding.row,
        finding.code,
    )


def _validate_progress_records(
    records: Sequence[QARuleProgressRecord], *, run_id: str
) -> None:
    """Validate QA progress record integrity for one run."""
    seen: set[QARuleId] = set()
    for record in records:
        if record.run_id != run_id:
            raise ValueError(
                f"record run_id mismatch: expected '{run_id}', got '{record.run_id}'"
            )
        if record.rule_id in seen:
            raise ValueError(f"duplicate QA rule progress record: {record.rule_id}")
        seen.add(record.rule_id)
        if record.state == QARuleState.QUEUED and record.ended_at_ms is not None:
            raise ValueError("queued rule cannot have ended_at_ms")
        if record.state == QARuleState.RUNNING and record.ended_at_ms is not None:
            raise ValueError("running rule cannot have ended_at_ms")
    unknown = set(seen) - set(QA_RULE_ORDER)
    if unknown:
        raise ValueError(f"unknown QA rule id(s): {sorted(unknown)}")


def _find_rule_record_index(
    records: Sequence[QARuleProgressRecord], *, rule_id: QARuleId
) -> int:
    """Return index of rule progress record in ordered sequence."""
    for index, record in enumerate(records):
        if record.rule_id == rule_id:
            return index
    raise ValueError(f"missing QA progress record for rule '{rule_id}'")
