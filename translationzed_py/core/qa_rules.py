"""Primitive QA rule checks for trailing fragments, newlines, and tokens."""

from __future__ import annotations

import re
from collections import Counter

TAG_TOKEN_RE = re.compile(r"<[A-Z][A-Z0-9_]*(?::[^>\r\n]+)?>")
BRACKET_TAG_TOKEN_RE = re.compile(r"\[[Ii][Mm][Gg]=[^\]\r\n]+\]")
PLACEHOLDER_TOKEN_RE = re.compile(r"%(?:\d+\$[A-Za-z]|\d+|[A-Za-z])")
ESCAPE_TOKEN_RE = re.compile(r"\\(x[0-9A-Fa-f]{2}|u[0-9A-Fa-f]{4}|[nrt\"\\\\])")
_TRAILING_RE = re.compile(r"[ \t\.,;:!?…]+$")
_NEWLINE_ESCAPE_RE = re.compile(r"(?<!\\)(?:\\\\)*\\n")
_PROTECTED_TOKEN_REGEXES = (
    TAG_TOKEN_RE,
    BRACKET_TAG_TOKEN_RE,
    PLACEHOLDER_TOKEN_RE,
    ESCAPE_TOKEN_RE,
)


def trailing_fragment(text: str) -> str:
    """Return trailing punctuation/whitespace fragment used for QA checks."""
    match = _TRAILING_RE.search(text)
    return match.group(0) if match else ""


def has_missing_trailing_fragment(source_text: str, target_text: str) -> bool:
    """Return True when source trailing fragment is not preserved in target."""
    source_tail = trailing_fragment(source_text)
    if not source_tail:
        return False
    target_tail = trailing_fragment(target_text)
    if not target_tail:
        return True
    return not target_tail.endswith(source_tail)


def newline_count(text: str) -> int:
    """Count logical newline markers in text, including escaped newline tokens."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    raw_newlines = normalized.count("\n")
    escaped_newlines = len(_NEWLINE_ESCAPE_RE.findall(normalized))
    return raw_newlines + escaped_newlines


def has_newline_mismatch(source_text: str, target_text: str) -> bool:
    """Return whether source and target newline counts differ."""
    return newline_count(source_text) != newline_count(target_text)


def same_as_source(source_text: str, target_text: str) -> bool:
    """Return whether target text is identical to source text."""
    return source_text == target_text


def extract_protected_tokens(text: str) -> tuple[str, ...]:
    """Return code-like tokens to preserve across translation."""
    spans: list[tuple[int, int, str]] = []
    for regex in _PROTECTED_TOKEN_REGEXES:
        for match in regex.finditer(text):
            spans.append((match.start(), match.end(), match.group(0)))
    spans.sort(key=lambda item: (item[0], item[1]))
    return tuple(token for _start, _end, token in spans)


def missing_protected_tokens(
    source_text: str,
    target_text: str,
) -> tuple[str, ...]:
    """Return protected tokens present in source but missing in target."""
    source_counts = Counter(extract_protected_tokens(source_text))
    target_counts = Counter(extract_protected_tokens(target_text))
    missing: list[str] = []
    for token, needed in source_counts.items():
        deficit = needed - target_counts.get(token, 0)
        if deficit > 0:
            missing.extend(token for _ in range(deficit))
    return tuple(missing)
