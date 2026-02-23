"""EN-driven insertion planning for missing locale keys."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

_KEY_LINE_RE = re.compile(r"^\s*([^\s=#][^=]*)=\s*(.*)$")


@dataclass(frozen=True, slots=True)
class ENKeyContext:
    """Represent one EN key line context used for insertion planning."""

    key: str
    line_index: int
    leading_comments: tuple[str, ...]
    trailing_comments: tuple[str, ...]
    line_prefix: str


@dataclass(frozen=True, slots=True)
class ENInsertItem:
    """Represent one missing-key insertion item."""

    key: str
    value: str
    anchor_key: str | None
    snippet_lines: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ENInsertPlan:
    """Represent ordered insertion plan and preview snippets."""

    items: tuple[ENInsertItem, ...]


def _is_comment_line(line: str, prefixes: tuple[str, ...]) -> bool:
    stripped = line.lstrip()
    return any(stripped.startswith(prefix) for prefix in prefixes)


def _parse_key_contexts(
    en_text: str,
    *,
    comment_prefixes: tuple[str, ...],
) -> tuple[ENKeyContext, ...]:
    lines = en_text.splitlines()
    contexts: list[ENKeyContext] = []
    for idx, line in enumerate(lines):
        match = _KEY_LINE_RE.match(line)
        if not match:
            continue
        key = match.group(1).strip()
        if not key:
            continue
        prefix = line.split("=", 1)[0].rstrip()
        leading: list[str] = []
        pos = idx - 1
        while pos >= 0:
            prev = lines[pos]
            if not prev.strip():
                break
            if not _is_comment_line(prev, comment_prefixes):
                break
            leading.append(prev)
            pos -= 1
        leading.reverse()
        trailing: list[str] = []
        pos = idx + 1
        while pos < len(lines):
            nxt = lines[pos]
            if not nxt.strip():
                break
            if _KEY_LINE_RE.match(nxt):
                break
            if not _is_comment_line(nxt, comment_prefixes):
                break
            trailing.append(nxt)
            pos += 1
        contexts.append(
            ENKeyContext(
                key=key,
                line_index=idx,
                leading_comments=tuple(leading),
                trailing_comments=tuple(trailing),
                line_prefix=prefix,
            )
        )
    return tuple(contexts)


def _parse_keys(text: str) -> tuple[str, ...]:
    keys: list[str] = []
    for line in text.splitlines():
        match = _KEY_LINE_RE.match(line)
        if not match:
            continue
        key = match.group(1).strip()
        if key:
            keys.append(key)
    return tuple(keys)


def _escape_literal(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


def _build_key_line(prefix: str, key: str, value: str) -> str:
    normalized_prefix = prefix if prefix else key
    return f'{normalized_prefix} = "{_escape_literal(value)}"'


def build_insert_plan(
    *,
    en_text: str,
    locale_text: str,
    edited_new_values: Mapping[str, str],
    comment_prefixes: Iterable[str] = ("#", "--"),
) -> ENInsertPlan:
    """Build deterministic insertion plan for edited NEW keys."""
    prefixes = tuple(
        str(prefix).strip() for prefix in comment_prefixes if str(prefix).strip()
    )
    active_prefixes = prefixes or ("#", "--")
    contexts = _parse_key_contexts(en_text, comment_prefixes=active_prefixes)
    if not contexts:
        return ENInsertPlan(items=())
    locale_keys = set(_parse_keys(locale_text))
    edited_keys = set(edited_new_values)
    ordered_contexts = [
        ctx for ctx in contexts if ctx.key in edited_keys and ctx.key not in locale_keys
    ]
    if not ordered_contexts:
        return ENInsertPlan(items=())

    en_order = [ctx.key for ctx in contexts]
    inserted_set = {ctx.key for ctx in ordered_contexts}
    items: list[ENInsertItem] = []
    last_emitted_comment_block: tuple[str, ...] = ()
    for ctx in ordered_contexts:
        key_pos = en_order.index(ctx.key)
        anchor_key: str | None = None
        for prev_key in reversed(en_order[:key_pos]):
            if prev_key in locale_keys or prev_key in inserted_set:
                anchor_key = prev_key
                break

        snippet_lines: list[str] = []
        if ctx.leading_comments and ctx.leading_comments != last_emitted_comment_block:
            snippet_lines.extend(ctx.leading_comments)
        snippet_lines.append(
            _build_key_line(ctx.line_prefix, ctx.key, str(edited_new_values[ctx.key]))
        )
        if ctx.trailing_comments:
            snippet_lines.extend(ctx.trailing_comments)
            last_emitted_comment_block = ctx.trailing_comments
        else:
            last_emitted_comment_block = ()
        items.append(
            ENInsertItem(
                key=ctx.key,
                value=str(edited_new_values[ctx.key]),
                anchor_key=anchor_key,
                snippet_lines=tuple(snippet_lines),
            )
        )
    return ENInsertPlan(items=tuple(items))


def apply_insert_plan(
    *,
    locale_text: str,
    plan: ENInsertPlan,
    edited_snippets: Mapping[str, str] | None = None,
) -> str:
    """Apply insertion plan to locale text and return merged text."""
    if not plan.items:
        return locale_text
    lines = locale_text.splitlines()
    if not lines:
        lines = []
    for item in plan.items:
        item_lines = (
            tuple((edited_snippets or {}).get(item.key, "").splitlines())
            if edited_snippets and item.key in edited_snippets
            else item.snippet_lines
        )
        if not item_lines:
            continue
        insert_idx = len(lines)
        if item.anchor_key is not None:
            for idx, line in enumerate(lines):
                match = _KEY_LINE_RE.match(line)
                if match and match.group(1).strip() == item.anchor_key:
                    insert_idx = idx + 1
                    break
        lines[insert_idx:insert_idx] = list(item_lines)
    merged = "\n".join(lines).rstrip("\n")
    return merged + "\n"
