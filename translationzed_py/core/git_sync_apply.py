"""Apply resolved Git synchronization choices without writing locale originals."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .app_config import load as _load_app_config
from .atomic_io import write_bytes_atomic, write_text_atomic
from .git_sync import inspect_state, resolve_commit, write_state
from .git_sync_service import (
    GitSyncItemChoice,
    GitSyncPlanItem,
    GitSyncResolvedPlan,
    GitTargetDocument,
    GitTargetRow,
    load_target_document,
    normalize_comment_prefixes,
)
from .model import Entry, Status
from .parse_utils import _resolve_encoding
from .project_scanner import LocaleMeta
from .status_cache import write as write_status_cache
from .translation_format import is_json_translation
from .tzp_comment_policy import parse_tzp_status_comment

PENDING_COMMENT_VERSION = 1
MAX_PENDING_COMMENT_BYTES = 8 * 1024 * 1024
MAX_PENDING_COMMENT_UPDATES = 100_000
_KEY_LINE_RE = re.compile(r"^\s*([^\s=#][^=]*)=\s*(.*)$")


class GitSyncApplyError(RuntimeError):
    """Report a synchronization effect that cannot be applied safely."""


@dataclass(frozen=True, slots=True)
class PendingGitComment:
    """Stage one user-comment replacement for the normal Save workflow."""

    target_path: str
    key: str
    expected: tuple[str, ...]
    replacement: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GitSyncApplyResult:
    """Summarize cache-only effects after the baseline advances."""

    baseline: str
    reviewed_items: int
    staged_comment_items: int


@dataclass(frozen=True, slots=True)
class _CommentBlock:
    start: int
    key_index: int
    user_comments: tuple[str, ...]
    program_lines: tuple[str, ...]


def _pending_path(root: Path) -> Path:
    cfg = _load_app_config(root)
    return root / cfg.cache_dir / "git_sync_comments.json"


def _target_path(root: Path, relative: str) -> Path:
    value = str(relative).replace("\\", "/")
    pure = PurePosixPath(value)
    if (
        not value
        or pure.is_absolute()
        or ".." in pure.parts
        or len(pure.parts) < 2
        or any(ord(char) < 32 or 0xD800 <= ord(char) <= 0xDFFF for char in value)
    ):
        raise GitSyncApplyError(f"Unsafe target path: {relative!r}")
    project = root.resolve()
    target = project.joinpath(*pure.parts).resolve()
    if project not in target.parents:
        raise GitSyncApplyError(f"Target path escapes the project: {relative!r}")
    return target


def _comment_lines(value: object, *, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(line, str) for line in value):
        raise GitSyncApplyError(f"Pending comment {field} must be a string list.")
    lines = tuple(value)
    if any("\n" in line or "\r" in line for line in lines):
        raise GitSyncApplyError(f"Pending comment {field} contains a line break.")
    return lines


def read_pending_comments(root: Path) -> tuple[PendingGitComment, ...]:
    """Read and validate staged comment replacements without mutating them."""
    path = _pending_path(root)
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return ()
    except OSError as exc:
        raise GitSyncApplyError(f"Cannot read staged Git comments: {exc}") from exc
    if len(raw) > MAX_PENDING_COMMENT_BYTES:
        raise GitSyncApplyError("Staged Git comments exceed the 8 MiB safety limit.")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise GitSyncApplyError("Staged Git comments are malformed.") from exc
    if (
        not isinstance(payload, dict)
        or payload.get("version") != PENDING_COMMENT_VERSION
    ):
        raise GitSyncApplyError("Staged Git comments use an unsupported format.")
    rows = payload.get("updates")
    if not isinstance(rows, list) or len(rows) > MAX_PENDING_COMMENT_UPDATES:
        raise GitSyncApplyError("Staged Git comment entries are invalid or excessive.")
    updates: list[PendingGitComment] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise GitSyncApplyError("Staged Git comment entry is malformed.")
        target_path = str(row.get("target_path") or "")
        key = str(row.get("key") or "")
        _target_path(root, target_path)
        if not key or "\0" in key:
            raise GitSyncApplyError("Staged Git comment key is invalid.")
        identity = (target_path, key)
        if identity in seen:
            raise GitSyncApplyError("Staged Git comments contain a duplicate key.")
        seen.add(identity)
        updates.append(
            PendingGitComment(
                target_path=target_path,
                key=key,
                expected=_comment_lines(row.get("expected"), field="expected"),
                replacement=_comment_lines(row.get("replacement"), field="replacement"),
            )
        )
    return tuple(sorted(updates, key=lambda item: (item.target_path, item.key)))


def _write_pending_comments(
    root: Path, updates: Mapping[tuple[str, str], PendingGitComment]
) -> None:
    path = _pending_path(root)
    if not updates:
        path.unlink(missing_ok=True)
        return
    rows = [
        {
            "expected": list(item.expected),
            "key": item.key,
            "replacement": list(item.replacement),
            "target_path": item.target_path,
        }
        for item in sorted(
            updates.values(), key=lambda value: (value.target_path, value.key)
        )
    ]
    payload = json.dumps(
        {"updates": rows, "version": PENDING_COMMENT_VERSION},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    if len(payload.encode("utf-8")) > MAX_PENDING_COMMENT_BYTES:
        raise GitSyncApplyError("Staged Git comments exceed the 8 MiB safety limit.")
    write_text_atomic(path, payload + "\n")


def _choice_map(
    resolved: GitSyncResolvedPlan,
) -> tuple[dict[str, GitSyncPlanItem], dict[str, GitSyncItemChoice]]:
    if resolved.unresolved_item_ids or not resolved.advance_baseline:
        raise GitSyncApplyError("Resolve or ignore every synchronization item first.")
    items = {item.item_id: item for item in resolved.plan.items}
    choices = {choice.item_id: choice for choice in resolved.choices}
    if (
        len(items) != len(resolved.plan.items)
        or len(choices) != len(resolved.choices)
        or set(choices) != set(items)
    ):
        raise GitSyncApplyError("Synchronization choices do not match the preview.")
    if any(choice.decision not in {"apply", "ignore"} for choice in choices.values()):
        raise GitSyncApplyError("Synchronization choices still contain a conflict.")
    return items, choices


def _validate_baseline(root: Path, resolved: GitSyncResolvedPlan) -> None:
    state = inspect_state(root)
    if state.state is None:
        raise GitSyncApplyError(
            f"Synchronization baseline is unavailable ({state.problem or 'unknown'})."
        )
    if state.state.baseline != resolved.plan.baseline:
        raise GitSyncApplyError(
            "Synchronization baseline changed; rebuild the preview."
        )
    if resolve_commit(root, "HEAD") != resolved.plan.head:
        raise GitSyncApplyError(
            "Local HEAD changed; rebuild the synchronization preview."
        )


def _validate_target_item(
    item: GitSyncPlanItem,
    current: GitTargetRow | None,
    *,
    allow_reviewed: bool,
) -> None:
    if item.target_file_value is None:
        if current is not None:
            raise GitSyncApplyError(
                f"{item.target_path}:{item.key} changed after the preview."
            )
        return
    expected_statuses = {item.target_status}
    if allow_reviewed:
        expected_statuses.add(Status.FOR_REVIEW)
    if current is None or (
        current.file_value != item.target_file_value
        or current.value != item.target_value
        or current.status not in expected_statuses
        or current.leading_comments != item.target_comments
    ):
        raise GitSyncApplyError(
            f"{item.target_path}:{item.key} changed after the preview."
        )


def _write_review_cache(
    root: Path, document: GitTargetDocument, review_keys: set[str]
) -> None:
    entries = [
        Entry(
            row.key,
            row.value,
            Status.FOR_REVIEW if row.key in review_keys else row.status,
            (0, 0),
            (len(row.value),),
            (),
        )
        for row in document.rows
    ]
    draft_keys = {row.key for row in document.rows if row.has_draft}
    write_status_cache(
        root,
        document.path,
        entries,
        changed_keys=draft_keys,
        original_values={
            row.key: row.file_value for row in document.rows if row.has_draft
        },
    )


def apply_resolved_plan(
    root: Path,
    resolved: GitSyncResolvedPlan,
    *,
    locales: Mapping[str, LocaleMeta],
    comment_prefixes: tuple[str, ...] = ("--",),
) -> GitSyncApplyResult:
    """Apply cache-only choices, then atomically advance the saved local baseline."""
    items, choices = _choice_map(resolved)
    _validate_baseline(root, resolved)
    pending = {
        (item.target_path, item.key): item for item in read_pending_comments(root)
    }
    original_pending = dict(pending)
    documents: dict[str, GitTargetDocument] = {}
    review_keys: dict[str, set[str]] = {}
    staged_comments = 0
    for item_id, item in items.items():
        choice = choices[item_id]
        if choice.decision == "ignore":
            continue
        if not item.can_apply or not item.key:
            raise GitSyncApplyError("An unappliable synchronization item was selected.")
        meta = locales.get(item.locale)
        if meta is None:
            raise GitSyncApplyError(f"Locale {item.locale!r} is no longer available.")
        path = _target_path(root, item.target_path)
        if meta.path.resolve() not in path.parents:
            raise GitSyncApplyError(f"Target path is outside locale {item.locale!r}.")
        document = documents.get(item.target_path)
        if document is None:
            try:
                document = load_target_document(
                    root,
                    path,
                    encoding=meta.charset,
                    comment_prefixes=comment_prefixes,
                )
            except Exception as exc:
                raise GitSyncApplyError(
                    f"Cannot refresh {item.target_path}: {exc}"
                ) from exc
            documents[item.target_path] = document
        current = next((row for row in document.rows if row.key == item.key), None)
        _validate_target_item(item, current, allow_reviewed=choice.mark_for_review)
        if choice.mark_for_review:
            review_keys.setdefault(item.target_path, set()).add(item.key)
        identity = (item.target_path, item.key)
        if "comments" in item.kinds and item.target_file_value is not None:
            if choice.comment_decision == "use_en":
                pending[identity] = PendingGitComment(
                    target_path=item.target_path,
                    key=item.key,
                    expected=item.target_comments,
                    replacement=item.head_comments,
                )
                staged_comments += 1
            elif choice.comment_decision == "keep_locale":
                pending.pop(identity, None)

    if pending != original_pending:
        _write_pending_comments(root, pending)
    for target_path in sorted(review_keys):
        _write_review_cache(root, documents[target_path], review_keys[target_path])
    state = inspect_state(root).state
    if state is None or state.baseline != resolved.plan.baseline:
        raise GitSyncApplyError("Synchronization baseline changed before completion.")
    written = write_state(root, baseline=resolved.plan.head)
    return GitSyncApplyResult(
        baseline=written.baseline,
        reviewed_items=sum(len(keys) for keys in review_keys.values()),
        staged_comment_items=staged_comments,
    )


def _line_body(line: str) -> str:
    if line.endswith("\r\n"):
        return line[:-2]
    if line.endswith(("\n", "\r")):
        return line[:-1]
    return line


def _line_ending(line: str) -> str:
    if line.endswith("\r\n"):
        return "\r\n"
    if line.endswith("\n"):
        return "\n"
    if line.endswith("\r"):
        return "\r"
    return ""


def _comment_blocks(
    lines: list[str], prefixes: tuple[str, ...]
) -> dict[str, _CommentBlock]:
    blocks: dict[str, _CommentBlock] = {}
    for key_index, line in enumerate(lines):
        match = _KEY_LINE_RE.match(_line_body(line))
        if not match:
            continue
        key = match.group(1).strip()
        if not key or key in blocks:
            raise GitSyncApplyError(
                "Target comments contain an ambiguous translation key."
            )
        start = key_index
        while start > 0:
            body = _line_body(lines[start - 1])
            stripped = body.lstrip()
            if not stripped or not any(
                stripped.startswith(prefix) for prefix in prefixes
            ):
                break
            start -= 1
        user: list[str] = []
        program: list[str] = []
        for comment_line in lines[start:key_index]:
            body = _line_body(comment_line)
            if parse_tzp_status_comment(body) is None:
                user.append(body)
            else:
                program.append(comment_line)
        blocks[key] = _CommentBlock(start, key_index, tuple(user), tuple(program))
    return blocks


def _rewrite_comments(
    raw: bytes,
    *,
    encoding: str,
    updates: tuple[PendingGitComment, ...],
    comment_prefixes: tuple[str, ...],
) -> bytes:
    resolved_encoding, bom_len = _resolve_encoding(encoding, raw)
    body = raw[bom_len:]
    try:
        text = body.decode(resolved_encoding, errors="strict")
    except UnicodeError as exc:
        raise GitSyncApplyError(f"Cannot decode staged comment file: {exc}") from exc
    if text.encode(resolved_encoding, errors="strict") != body:
        raise GitSyncApplyError(
            "Staged comment file does not round-trip in its locale encoding."
        )
    lines = text.splitlines(keepends=True)
    prefixes = normalize_comment_prefixes(comment_prefixes)
    blocks = _comment_blocks(lines, prefixes)
    edits: list[tuple[int, int, tuple[str, ...]]] = []
    for update in updates:
        block = blocks.get(update.key)
        if block is None:
            raise GitSyncApplyError(f"Comment target key {update.key!r} is missing.")
        if block.user_comments == update.replacement:
            continue
        if block.user_comments != update.expected:
            raise GitSyncApplyError(
                f"Comments for {update.key!r} changed after synchronization."
            )
        candidates = [*lines[block.start : block.key_index + 1], *lines]
        newline = next(
            (_line_ending(line) for line in candidates if _line_ending(line)), "\n"
        )
        replacement = (
            *(comment + newline for comment in update.replacement),
            *block.program_lines,
        )
        edits.append((block.start, block.key_index, replacement))
    for start, end, replacement in sorted(edits, reverse=True):
        lines[start:end] = replacement
    merged = "".join(lines).encode(resolved_encoding, errors="strict")
    return raw[:bom_len] + merged


def _updates_for_path(root: Path, path: Path) -> tuple[PendingGitComment, ...]:
    project = root.resolve()
    target = path.resolve()
    if project not in target.parents:
        raise GitSyncApplyError("Comment target is outside the project.")
    relative = target.relative_to(project).as_posix()
    return tuple(
        item for item in read_pending_comments(root) if item.target_path == relative
    )


def pending_comment_paths(root: Path) -> tuple[Path, ...]:
    """Return target files that still have staged Git comment replacements."""
    return tuple(
        sorted(
            {
                _target_path(root, item.target_path)
                for item in read_pending_comments(root)
            }
        )
    )


def preflight_pending_comments(
    root: Path,
    path: Path,
    *,
    encoding: str,
    comment_prefixes: tuple[str, ...] = ("--",),
) -> int:
    """Validate staged comments before normal Save writes any original bytes."""
    updates = _updates_for_path(root, path)
    if not updates:
        return 0
    if is_json_translation(path):
        raise GitSyncApplyError(
            "JSON translation files cannot contain staged comments."
        )
    _rewrite_comments(
        path.read_bytes(),
        encoding=encoding,
        updates=updates,
        comment_prefixes=comment_prefixes,
    )
    return len(updates)


def apply_pending_comments(
    root: Path,
    path: Path,
    *,
    encoding: str,
    comment_prefixes: tuple[str, ...] = ("--",),
) -> int:
    """Apply staged comments atomically during Save and clear completed records."""
    updates = _updates_for_path(root, path)
    if not updates:
        return 0
    if is_json_translation(path):
        raise GitSyncApplyError(
            "JSON translation files cannot contain staged comments."
        )
    raw = path.read_bytes()
    merged = _rewrite_comments(
        raw,
        encoding=encoding,
        updates=updates,
        comment_prefixes=comment_prefixes,
    )
    if merged != raw:
        write_bytes_atomic(path, merged)
    completed = {(item.target_path, item.key) for item in updates}
    remaining = {
        (item.target_path, item.key): item
        for item in read_pending_comments(root)
        if (item.target_path, item.key) not in completed
    }
    _write_pending_comments(root, remaining)
    return len(updates)


__all__ = [
    "GitSyncApplyError",
    "GitSyncApplyResult",
    "PendingGitComment",
    "apply_pending_comments",
    "apply_resolved_plan",
    "pending_comment_paths",
    "preflight_pending_comments",
    "read_pending_comments",
]
