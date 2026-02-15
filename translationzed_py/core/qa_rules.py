from __future__ import annotations

import re
from collections import Counter

_TAG_RE = re.compile(r"<[A-Z][A-Z0-9_]*(?::[^>\r\n]+)?>")
_BRACKET_TAG_RE = re.compile(r"\[[Ii][Mm][Gg]=[^\]\r\n]+\]")
_PLACEHOLDER_RE = re.compile(r"%(?:\d+\$[A-Za-z]|\d+|[A-Za-z])")
_ESCAPE_RE = re.compile(r"\\(x[0-9A-Fa-f]{2}|u[0-9A-Fa-f]{4}|[nrt\"\\\\])")
_TRAILING_RE = re.compile(r"[ \t\.,;:!?…]+$")
_NEWLINE_ESCAPE_RE = re.compile(r"(?<!\\)(?:\\\\)*\\n")


def trailing_fragment(text: str) -> str:
    """Return trailing punctuation/whitespace fragment used for QA checks."""
    match = _TRAILING_RE.search(text)
    return match.group(0) if match else ""


def has_missing_trailing_fragment(source_text: str, target_text: str) -> bool:
    """
    True when source ends with a trailing fragment and target does not preserve it.
    """
    source_tail = trailing_fragment(source_text)
    if not source_tail:
        return False
    target_tail = trailing_fragment(target_text)
    if not target_tail:
        return True
    return not target_tail.endswith(source_tail)


def newline_count(text: str) -> int:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    raw_newlines = normalized.count("\n")
    escaped_newlines = len(_NEWLINE_ESCAPE_RE.findall(normalized))
    return raw_newlines + escaped_newlines


def has_newline_mismatch(source_text: str, target_text: str) -> bool:
    return newline_count(source_text) != newline_count(target_text)


def same_as_source(source_text: str, target_text: str) -> bool:
    return source_text == target_text


def extract_protected_tokens(text: str) -> tuple[str, ...]:
    """
    Return code-like tokens to preserve across translation.
    """
    spans: list[tuple[int, int, str]] = []
    for regex in (_TAG_RE, _BRACKET_TAG_RE, _PLACEHOLDER_RE, _ESCAPE_RE):
        for match in regex.finditer(text):
            spans.append((match.start(), match.end(), match.group(0)))
    spans.sort(key=lambda item: (item[0], item[1]))
    return tuple(token for _start, _end, token in spans)


def missing_protected_tokens(
    source_text: str,
    target_text: str,
) -> tuple[str, ...]:
    source_counts = Counter(extract_protected_tokens(source_text))
    target_counts = Counter(extract_protected_tokens(target_text))
    missing: list[str] = []
    for token, needed in source_counts.items():
        deficit = needed - target_counts.get(token, 0)
        if deficit > 0:
            missing.extend(token for _ in range(deficit))
    return tuple(missing)
