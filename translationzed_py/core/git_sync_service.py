"""Qt-free committed EN change classification for Git synchronization."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import xxhash

from translationzed_py.core.git_sync import (
    GitFileChange,
    GitSyncInspection,
    read_blob,
)
from translationzed_py.core.model import Status
from translationzed_py.core.parse_utils import _decode_text, _resolve_encoding
from translationzed_py.core.parser import parse_bytes
from translationzed_py.core.project_scanner import LocaleMeta
from translationzed_py.core.status_cache import read as read_status_cache
from translationzed_py.core.translation_format import is_json_translation
from translationzed_py.core.tzp_comment_policy import parse_tzp_status_comment

MAX_SYNC_BLOB_BYTES = 64 * 1024 * 1024
MAX_SYNC_PLAN_ITEMS = 100_000
GitKeyChangeKind = Literal["added", "removed", "modified", "comments", "reordered"]
GitSyncDecision = Literal["apply", "ignore", "conflict"]
GitSyncCommentDecision = Literal["none", "use_en", "keep_locale", "choose"]

_KEY_LINE_RE = re.compile(r"^\s*([^\s=#][^=]*)=\s*(.*)$")


class GitSyncDocumentError(ValueError):
    """Report a historical translation blob that cannot be merged safely."""


@dataclass(frozen=True, slots=True)
class GitSourceRow:
    """Describe one ordered EN key/value and its adjacent leading comments."""

    key: str
    value: str
    index: int
    leading_comments: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GitSourceDocument:
    """Describe one parsed EN translation blob without filesystem state."""

    path: str
    rows: tuple[GitSourceRow, ...]


@dataclass(frozen=True, slots=True)
class GitKeyDelta:
    """Describe all committed changes affecting one EN key."""

    key: str
    kinds: tuple[GitKeyChangeKind, ...]
    base_value: str | None
    head_value: str | None
    base_index: int | None
    head_index: int | None
    base_comments: tuple[str, ...] = ()
    head_comments: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GitFileDelta:
    """Describe one committed EN file delta or its safe-classification failure."""

    kind: str
    path: str
    previous_path: str | None
    keys: tuple[GitKeyDelta, ...] = ()
    error: str | None = None


@dataclass(frozen=True, slots=True)
class GitSyncChangeSet:
    """Describe a complete, deterministic committed EN change range."""

    baseline: str
    head: str
    files: tuple[GitFileDelta, ...]
    dirty_paths: tuple[str, ...] = ()
    unsupported_paths: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GitTargetRow:
    """Describe the target value/status visible after cache overlay."""

    key: str
    value: str
    file_value: str
    status: Status
    index: int
    leading_comments: tuple[str, ...] = ()
    has_draft: bool = False


@dataclass(frozen=True, slots=True)
class GitTargetDocument:
    """Describe one current target locale file for merge planning."""

    path: Path
    rows: tuple[GitTargetRow, ...]


@dataclass(frozen=True, slots=True)
class GitSyncPlanItem:
    """Describe one independently previewable target-locale decision."""

    item_id: str
    locale: str
    source_path: str
    target_path: str
    key: str
    kinds: tuple[str, ...]
    base_source: str | None
    head_source: str | None
    target_value: str | None
    target_file_value: str | None
    target_status: Status | None
    base_comments: tuple[str, ...] = ()
    head_comments: tuple[str, ...] = ()
    target_comments: tuple[str, ...] = ()
    default_decision: GitSyncDecision = "apply"
    comment_decision: GitSyncCommentDecision = "none"
    propose_for_review: bool = False
    can_apply: bool = True
    conflict_reason: str | None = None


@dataclass(frozen=True, slots=True)
class GitSyncMergePlan:
    """Describe immutable preview items for selected target locales."""

    baseline: str
    head: str
    items: tuple[GitSyncPlanItem, ...]
    dirty_paths: tuple[str, ...] = ()
    unsupported_paths: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GitSyncItemChoice:
    """Capture one explicit preview decision without performing effects."""

    item_id: str
    decision: GitSyncDecision
    comment_decision: GitSyncCommentDecision = "none"
    mark_for_review: bool = False


@dataclass(frozen=True, slots=True)
class GitSyncResolvedPlan:
    """Describe validated choices and whether the baseline may advance."""

    plan: GitSyncMergePlan
    choices: tuple[GitSyncItemChoice, ...]
    unresolved_item_ids: tuple[str, ...]
    advance_baseline: bool


def normalize_comment_prefixes(prefixes: tuple[str, ...]) -> tuple[str, ...]:
    normalized: list[str] = []
    for raw in (*prefixes, "--", "#", "//"):
        prefix = str(raw).strip()
        if prefix and prefix not in normalized:
            normalized.append(prefix)
    return tuple(normalized)


def leading_comments_by_key(
    text: str,
    *,
    prefixes: tuple[str, ...],
) -> dict[str, tuple[str, ...]]:
    lines = text.splitlines()
    out: dict[str, tuple[str, ...]] = {}
    for index, line in enumerate(lines):
        match = _KEY_LINE_RE.match(line)
        if not match:
            continue
        key = match.group(1).strip()
        if not key or key in out:
            continue
        comments: list[str] = []
        cursor = index - 1
        while cursor >= 0:
            candidate = lines[cursor]
            stripped = candidate.lstrip()
            if not stripped or not any(
                stripped.startswith(prefix) for prefix in prefixes
            ):
                break
            if parse_tzp_status_comment(candidate) is None:
                comments.append(candidate)
            cursor -= 1
        comments.reverse()
        out[key] = tuple(comments)
    return out


def parse_source_document(
    *,
    path: str,
    raw: bytes,
    encoding: str,
    comment_prefixes: tuple[str, ...] = ("--",),
) -> GitSourceDocument:
    """Parse one historical EN blob through the production format boundary."""
    if len(raw) > MAX_SYNC_BLOB_BYTES:
        raise GitSyncDocumentError("Translation blob exceeds the 64 MiB safety limit.")
    identity = Path(path)
    try:
        parsed = parse_bytes(identity, raw, encoding)
    except Exception as exc:
        raise GitSyncDocumentError(str(exc)) from exc
    entries = tuple(parsed.entries)
    keys = [entry.key for entry in entries]
    if len(keys) != len(set(keys)):
        raise GitSyncDocumentError("Duplicate translation keys are unsupported.")

    comments: dict[str, tuple[str, ...]] = {}
    if not is_json_translation(identity):
        resolved_encoding, _bom_len = _resolve_encoding(encoding, raw)
        try:
            text = _decode_text(raw, resolved_encoding)
        except UnicodeError as exc:
            raise GitSyncDocumentError(str(exc)) from exc
        comments = leading_comments_by_key(
            text,
            prefixes=normalize_comment_prefixes(comment_prefixes),
        )
    rows = tuple(
        GitSourceRow(
            key=entry.key,
            value=entry.value,
            index=index,
            leading_comments=comments.get(entry.key, ()),
        )
        for index, entry in enumerate(entries)
    )
    return GitSourceDocument(path=path, rows=rows)


def _changed_order_keys(
    base_rows: tuple[GitSourceRow, ...],
    head_rows: tuple[GitSourceRow, ...],
) -> set[str]:
    base_keys = {row.key for row in base_rows}
    head_keys = {row.key for row in head_rows}
    common = base_keys & head_keys
    base_order = [row.key for row in base_rows if row.key in common]
    head_order = [row.key for row in head_rows if row.key in common]
    if base_order == head_order:
        return set()
    base_positions = {key: index for index, key in enumerate(base_order)}
    head_positions = {key: index for index, key in enumerate(head_order)}
    return {key for key in common if base_positions.get(key) != head_positions.get(key)}


def classify_documents(
    base: GitSourceDocument | None,
    head: GitSourceDocument | None,
) -> tuple[GitKeyDelta, ...]:
    """Classify value, comment, membership, and relative-order changes."""
    base_rows = base.rows if base is not None else ()
    head_rows = head.rows if head is not None else ()
    base_by_key = {row.key: row for row in base_rows}
    head_by_key = {row.key: row for row in head_rows}
    reordered = _changed_order_keys(base_rows, head_rows)
    ordered_keys = [row.key for row in head_rows]
    ordered_keys.extend(row.key for row in base_rows if row.key not in head_by_key)
    out: list[GitKeyDelta] = []
    for key in ordered_keys:
        base_row = base_by_key.get(key)
        head_row = head_by_key.get(key)
        kinds: list[GitKeyChangeKind] = []
        if base_row is None:
            kinds.append("added")
        elif head_row is None:
            kinds.append("removed")
        else:
            if base_row.value != head_row.value:
                kinds.append("modified")
            if base_row.leading_comments != head_row.leading_comments:
                kinds.append("comments")
            if key in reordered:
                kinds.append("reordered")
        if not kinds:
            continue
        out.append(
            GitKeyDelta(
                key=key,
                kinds=tuple(kinds),
                base_value=base_row.value if base_row is not None else None,
                head_value=head_row.value if head_row is not None else None,
                base_index=base_row.index if base_row is not None else None,
                head_index=head_row.index if head_row is not None else None,
                base_comments=(
                    base_row.leading_comments if base_row is not None else ()
                ),
                head_comments=(
                    head_row.leading_comments if head_row is not None else ()
                ),
            )
        )
    return tuple(out)


def _documents_for_change(
    project_root: Path,
    inspection: GitSyncInspection,
    change: GitFileChange,
    *,
    encoding: str,
    comment_prefixes: tuple[str, ...],
) -> tuple[GitSourceDocument | None, GitSourceDocument | None]:
    base_path = change.previous_path if change.kind == "renamed" else change.path
    base_raw = (
        None
        if change.kind == "added"
        else read_blob(
            project_root,
            commit=inspection.baseline,
            project_path=base_path or change.path,
        )
    )
    head_raw = (
        None
        if change.kind == "deleted"
        else read_blob(
            project_root,
            commit=inspection.head,
            project_path=change.path,
        )
    )
    base = (
        parse_source_document(
            path=base_path or change.path,
            raw=base_raw,
            encoding=encoding,
            comment_prefixes=comment_prefixes,
        )
        if base_raw is not None
        else None
    )
    head = (
        parse_source_document(
            path=change.path,
            raw=head_raw,
            encoding=encoding,
            comment_prefixes=comment_prefixes,
        )
        if head_raw is not None
        else None
    )
    return base, head


def build_change_set(
    project_root: Path,
    inspection: GitSyncInspection,
    *,
    en_encoding: str,
    comment_prefixes: tuple[str, ...] = ("--",),
) -> GitSyncChangeSet:
    """Read and classify every committed EN blob in an inspection range."""
    files: list[GitFileDelta] = []
    for change in inspection.changes:
        try:
            base, head = _documents_for_change(
                project_root,
                inspection,
                change,
                encoding=en_encoding,
                comment_prefixes=comment_prefixes,
            )
            keys = classify_documents(base, head)
            error = None
        except Exception as exc:
            keys = ()
            error = str(exc) or type(exc).__name__
        files.append(
            GitFileDelta(
                kind=change.kind,
                path=change.path,
                previous_path=change.previous_path,
                keys=keys,
                error=error,
            )
        )
    return GitSyncChangeSet(
        baseline=inspection.baseline,
        head=inspection.head,
        files=tuple(files),
        dirty_paths=inspection.dirty_paths,
        unsupported_paths=inspection.unsupported_paths,
    )


def load_target_document(
    root: Path,
    path: Path,
    *,
    encoding: str,
    comment_prefixes: tuple[str, ...] = ("--",),
) -> GitTargetDocument:
    """Load one target original plus its current draft/status cache overlay."""
    raw = path.read_bytes()
    if len(raw) > MAX_SYNC_BLOB_BYTES:
        raise GitSyncDocumentError("Translation file exceeds the 64 MiB safety limit.")
    try:
        parsed = parse_bytes(path, raw, encoding)
    except Exception as exc:
        raise GitSyncDocumentError(str(exc)) from exc
    entries = tuple(parsed.entries)
    keys = [entry.key for entry in entries]
    if len(keys) != len(set(keys)):
        raise GitSyncDocumentError("Duplicate target translation keys are unsupported.")

    comments: dict[str, tuple[str, ...]] = {}
    if not is_json_translation(path):
        resolved_encoding, _bom_len = _resolve_encoding(encoding, raw)
        text = _decode_text(raw, resolved_encoding)
        comments = leading_comments_by_key(
            text,
            prefixes=normalize_comment_prefixes(comment_prefixes),
        )
    cached = read_status_cache(root, path)
    hash_bits = getattr(cached, "hash_bits", 64)
    mask = 0xFFFF if hash_bits == 16 else 0xFFFFFFFFFFFFFFFF
    rows: list[GitTargetRow] = []
    for index, entry in enumerate(entries):
        digest = entry.key_hash
        if digest is None:
            digest = int(xxhash.xxh64(entry.key.encode("utf-8")).intdigest())
        record = cached.get(int(digest) & mask)
        rows.append(
            GitTargetRow(
                key=entry.key,
                value=(
                    record.value
                    if record is not None and record.value is not None
                    else entry.value
                ),
                file_value=entry.value,
                status=record.status if record is not None else entry.status,
                index=index,
                leading_comments=comments.get(entry.key, ()),
                has_draft=record is not None and record.value is not None,
            )
        )
    return GitTargetDocument(path=path, rows=tuple(rows))


def _locale_suffix_tokens(locale: str) -> tuple[str, ...]:
    raw = str(locale).strip()
    underscore = raw.replace(" ", "_")
    return (raw,) if underscore == raw else (raw, underscore)


def _target_path_for_source(
    root: Path,
    meta: LocaleMeta,
    source_path: str,
) -> Path:
    source = Path(source_path)
    if len(source.parts) < 2 or source.parts[0] != "EN":
        raise GitSyncDocumentError(f"Unsafe source path: {source_path!r}")
    rel = Path(*source.parts[1:])
    direct = meta.path / rel
    if direct.exists():
        return direct
    stem = rel.stem
    for source_token in _locale_suffix_tokens("EN"):
        suffix = f"_{source_token}"
        if not stem.endswith(suffix):
            continue
        prefix = stem[: -len(suffix)]
        for target_token in _locale_suffix_tokens(meta.code):
            candidate = meta.path / rel.with_name(
                f"{prefix}_{target_token}{rel.suffix}"
            )
            if candidate.exists():
                return candidate
    with_path = root / meta.code / rel
    return with_path


def _item_id(
    *,
    baseline: str,
    head: str,
    locale: str,
    target_path: str,
    key: str,
    kinds: Sequence[str],
) -> str:
    identity = "\0".join(
        (baseline, head, locale, target_path, key, *tuple(str(kind) for kind in kinds))
    )
    digest = hashlib.blake2b(identity.encode("utf-8"), digest_size=12).hexdigest()
    return f"{locale}:{digest}"


def _relative_path(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _file_conflict_item(
    *,
    change_set: GitSyncChangeSet,
    locale: str,
    source_path: str,
    target_path: str,
    kind: str,
    reason: str,
) -> GitSyncPlanItem:
    kinds = (kind,)
    return GitSyncPlanItem(
        item_id=_item_id(
            baseline=change_set.baseline,
            head=change_set.head,
            locale=locale,
            target_path=target_path,
            key="",
            kinds=kinds,
        ),
        locale=locale,
        source_path=source_path,
        target_path=target_path,
        key="",
        kinds=kinds,
        base_source=None,
        head_source=None,
        target_value=None,
        target_file_value=None,
        target_status=None,
        default_decision="conflict",
        can_apply=False,
        conflict_reason=reason,
    )


def _add_plan_item(items: list[GitSyncPlanItem], item: GitSyncPlanItem) -> None:
    if len(items) >= MAX_SYNC_PLAN_ITEMS:
        raise GitSyncDocumentError(
            f"Synchronization preview exceeds {MAX_SYNC_PLAN_ITEMS:,} items."
        )
    items.append(item)


def _comment_policy(
    delta: GitKeyDelta,
    target_comments: tuple[str, ...],
) -> tuple[GitSyncCommentDecision, str | None]:
    if "comments" not in delta.kinds:
        return "none", None
    if target_comments == delta.head_comments:
        return "none", None
    if target_comments == delta.base_comments:
        return "use_en", None
    return (
        "choose",
        "Target comments differ from both the baseline and current English comments.",
    )


def _plan_key_item(
    *,
    change_set: GitSyncChangeSet,
    file_delta: GitFileDelta,
    locale: str,
    target_path: str,
    delta: GitKeyDelta,
    target_row: GitTargetRow | None,
) -> GitSyncPlanItem:
    kinds = tuple(str(kind) for kind in delta.kinds)
    decision: GitSyncDecision = "apply"
    can_apply = True
    conflict_reason: str | None = None
    comment_decision: GitSyncCommentDecision = "none"
    propose_for_review = False

    if "added" in delta.kinds:
        if target_row is not None:
            kinds = (*kinds, "already_present")
            decision = "ignore"
        elif delta.head_comments:
            comment_decision = "use_en"
    elif "removed" in delta.kinds:
        if target_row is None:
            decision = "ignore"
    elif target_row is None:
        decision = "conflict"
        can_apply = False
        conflict_reason = "The changed English key is missing from the target file."
    else:
        comment_decision, conflict_reason = _comment_policy(
            delta,
            target_row.leading_comments,
        )
        if comment_decision == "choose":
            decision = "conflict"
        propose_for_review = "modified" in delta.kinds
        if (
            delta.kinds == ("comments",)
            and target_row.leading_comments == delta.head_comments
        ):
            decision = "ignore"

    return GitSyncPlanItem(
        item_id=_item_id(
            baseline=change_set.baseline,
            head=change_set.head,
            locale=locale,
            target_path=target_path,
            key=delta.key,
            kinds=kinds,
        ),
        locale=locale,
        source_path=file_delta.path,
        target_path=target_path,
        key=delta.key,
        kinds=kinds,
        base_source=delta.base_value,
        head_source=delta.head_value,
        target_value=target_row.value if target_row is not None else None,
        target_file_value=(target_row.file_value if target_row is not None else None),
        target_status=target_row.status if target_row is not None else None,
        base_comments=delta.base_comments,
        head_comments=delta.head_comments,
        target_comments=(target_row.leading_comments if target_row is not None else ()),
        default_decision=decision,
        comment_decision=comment_decision,
        propose_for_review=propose_for_review,
        can_apply=can_apply,
        conflict_reason=conflict_reason,
    )


def build_merge_plan(
    root: Path,
    change_set: GitSyncChangeSet,
    *,
    locales: Mapping[str, LocaleMeta],
    selected_locales: Sequence[str],
    comment_prefixes: tuple[str, ...] = ("--",),
) -> GitSyncMergePlan:
    """Build a deterministic cache-only synchronization preview per target locale."""
    items: list[GitSyncPlanItem] = []
    locale_codes = sorted(
        {
            str(code).strip()
            for code in selected_locales
            if str(code).strip() and str(code).strip() != "EN"
        }
    )
    for file_delta in change_set.files:
        for locale in locale_codes:
            meta = locales.get(locale)
            if meta is None:
                continue
            source_for_target = (
                file_delta.previous_path
                if file_delta.kind == "deleted" and file_delta.previous_path
                else file_delta.path
            )
            target = _target_path_for_source(root, meta, source_for_target)
            target_rel = _relative_path(root, target)
            if file_delta.error:
                _add_plan_item(
                    items,
                    _file_conflict_item(
                        change_set=change_set,
                        locale=locale,
                        source_path=file_delta.path,
                        target_path=target_rel,
                        kind="file_unreadable",
                        reason=file_delta.error,
                    ),
                )
                continue
            if file_delta.kind == "renamed" and file_delta.previous_path:
                previous_target = _target_path_for_source(
                    root,
                    meta,
                    file_delta.previous_path,
                )
                if not target.exists() and previous_target.exists():
                    _add_plan_item(
                        items,
                        _file_conflict_item(
                            change_set=change_set,
                            locale=locale,
                            source_path=file_delta.path,
                            target_path=_relative_path(root, previous_target),
                            kind="file_renamed",
                            reason=(
                                "The English file was renamed; rename or create the target "
                                "file explicitly before applying key changes."
                            ),
                        ),
                    )
                    continue
            if not target.exists():
                if file_delta.kind == "deleted":
                    continue
                _add_plan_item(
                    items,
                    _file_conflict_item(
                        change_set=change_set,
                        locale=locale,
                        source_path=file_delta.path,
                        target_path=target_rel,
                        kind="file_missing",
                        reason="No corresponding target locale file exists.",
                    ),
                )
                continue
            try:
                target_document = load_target_document(
                    root,
                    target,
                    encoding=meta.charset,
                    comment_prefixes=comment_prefixes,
                )
            except Exception as exc:
                _add_plan_item(
                    items,
                    _file_conflict_item(
                        change_set=change_set,
                        locale=locale,
                        source_path=file_delta.path,
                        target_path=target_rel,
                        kind="target_unreadable",
                        reason=str(exc) or type(exc).__name__,
                    ),
                )
                continue
            target_by_key = {row.key: row for row in target_document.rows}
            for delta in file_delta.keys:
                _add_plan_item(
                    items,
                    _plan_key_item(
                        change_set=change_set,
                        file_delta=file_delta,
                        locale=locale,
                        target_path=target_rel,
                        delta=delta,
                        target_row=target_by_key.get(delta.key),
                    ),
                )
    return GitSyncMergePlan(
        baseline=change_set.baseline,
        head=change_set.head,
        items=tuple(items),
        dirty_paths=change_set.dirty_paths,
        unsupported_paths=change_set.unsupported_paths,
    )


def resolve_merge_plan(
    plan: GitSyncMergePlan,
    choices: Mapping[str, GitSyncItemChoice] | None = None,
) -> GitSyncResolvedPlan:
    """Validate preview choices without mutating cache, state, Git, or originals."""
    supplied = dict(choices or {})
    known = {item.item_id for item in plan.items}
    unknown = sorted(set(supplied) - known)
    if unknown:
        raise ValueError(f"Unknown Git synchronization item: {unknown[0]}")
    normalized: list[GitSyncItemChoice] = []
    unresolved: list[str] = []
    for item in plan.items:
        choice = supplied.get(item.item_id)
        if choice is None:
            choice = GitSyncItemChoice(
                item_id=item.item_id,
                decision=item.default_decision,
                comment_decision=item.comment_decision,
                mark_for_review=item.propose_for_review,
            )
        if choice.item_id != item.item_id:
            raise ValueError("Git synchronization choice identity mismatch.")
        comment_choice = choice.comment_decision
        decision = choice.decision
        if decision == "apply" and not item.can_apply:
            decision = "conflict"
        if decision == "apply" and item.comment_decision == "choose":
            if comment_choice not in {"use_en", "keep_locale"}:
                decision = "conflict"
        elif item.comment_decision != "choose":
            comment_choice = item.comment_decision
        mark_for_review = bool(choice.mark_for_review and item.propose_for_review)
        normalized_choice = GitSyncItemChoice(
            item_id=item.item_id,
            decision=decision,
            comment_decision=comment_choice,
            mark_for_review=mark_for_review,
        )
        normalized.append(normalized_choice)
        if decision == "conflict":
            unresolved.append(item.item_id)
    return GitSyncResolvedPlan(
        plan=plan,
        choices=tuple(normalized),
        unresolved_item_ids=tuple(unresolved),
        advance_baseline=not unresolved,
    )


__all__ = [
    "MAX_SYNC_PLAN_ITEMS",
    "GitFileDelta",
    "GitKeyDelta",
    "GitSourceDocument",
    "GitSourceRow",
    "GitSyncItemChoice",
    "GitSyncChangeSet",
    "GitSyncDocumentError",
    "GitSyncMergePlan",
    "GitSyncPlanItem",
    "GitSyncResolvedPlan",
    "GitTargetDocument",
    "GitTargetRow",
    "build_change_set",
    "build_merge_plan",
    "classify_documents",
    "load_target_document",
    "parse_source_document",
    "resolve_merge_plan",
]
