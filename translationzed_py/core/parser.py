from __future__ import annotations

import ast
import enum
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:  # forward-refs for mypy, no runtime cycle
    from .model import Entry, ParsedFile, Status


# ── helper --------------------------------------------------------------------
_STATUS_MAP: dict[str, Status] = {}  # populated on first parse()


def _unescape(raw: str) -> str:
    """Turn `He said \\\"hi\\\"` → `He said "hi"`."""
    return cast(str, ast.literal_eval(f'"{raw}"'))


# ── Token meta ────────────────────────────────────────────────────────────────
class Kind(enum.IntEnum):
    COMMENT = 0  # -- Up to newline
    KEY = 1
    EQUAL = 2
    STRING = 3
    CONCAT = 4  #  ..
    NEWLINE = 5
    TRIVIA = 6  #  space / tab


@dataclass(slots=True, frozen=True)
class Tok:
    kind: Kind
    span: tuple[int, int]  # byte offsets
    text: str


# ── Regex table (spec §5.2) ───────────────────────────────────────────────────
_PATTERNS = [
    (Kind.TRIVIA, rb"[ \t]+"),
    (Kind.NEWLINE, rb"\r?\n"),
    (Kind.COMMENT, rb"--[^\n]*"),  # spec §5.2 :contentReference[oaicite:3]{index=3}
    (Kind.KEY, rb"[A-Za-z0-9_]+"),  # mixed-case identifiers
    (Kind.EQUAL, rb"="),
    (Kind.CONCAT, rb"\.\."),
    (Kind.STRING, rb'"(?:\\.|[^"])*"'),  # back-slash escapes
]
_TOKEN_RE = re.compile(
    b"|".join(rf"(?P<{k.name}>{p.decode()})".encode() for k, p in _PATTERNS),
    re.DOTALL,
)


# ── The generator the test asked about ────────────────────────────────────────
def _tokenise(data: bytes) -> Iterable[Tok]:
    pos = 0
    while pos < len(data):
        m = _TOKEN_RE.match(data, pos)
        if not m:
            raise SyntaxError(f"Unknown byte sequence at {pos}")

        group = m.lastgroup
        assert group is not None  # narrow the type for mypy
        kind = Kind[group]  # now str, not str|None

        span = (m.start(), m.end())
        yield Tok(kind, span, m.group().decode("utf-8", "replace"))
        pos = m.end()


# ── parse() placeholder – we’ll flesh this out next ───────────────────────────
def parse(path: Path, encoding: str = "utf-8") -> ParsedFile:  # noqa: F821
    """Read *path*, tokenise, and build a read-only ParsedFile object."""
    # local import avoids an import cycle
    from .model import Entry, ParsedFile, Status

    global _STATUS_MAP
    if not _STATUS_MAP:  # fill once
        _STATUS_MAP = {
            "TRANSLATED": Status.TRANSLATED,
            "PROOFREAD": Status.PROOFREAD,
        }

    raw = path.read_bytes()
    toks = list(_tokenise(raw))

    entries: list[Entry] = []
    i = 0
    while i < len(toks):
        #  KEY … = …
        if toks[i].kind is Kind.KEY:
            key_tok = toks[i]
            # skip trivia, expect '='
            j = i + 1
            while j < len(toks) and toks[j].kind is Kind.TRIVIA:
                j += 1
            if j >= len(toks) or toks[j].kind is not Kind.EQUAL:
                i += 1
                continue
            j += 1  # after '='
            # gather one or more STRING [TRIVIA] CONCAT [TRIVIA] STRING …
            parts: list[str] = []
            span_start = key_tok.span[0]
            while j < len(toks):
                if toks[j].kind is Kind.STRING:
                    parts.append(_unescape(toks[j].text[1:-1]))
                    span_end = toks[j].span[1]
                    j += 1
                elif toks[j].kind in (Kind.TRIVIA, Kind.CONCAT):
                    j += 1
                else:
                    break
            value = "".join(parts)
            # find comment on the same line
            status = Status.UNTOUCHED
            k = j
            while k < len(toks) and toks[k].kind is not Kind.NEWLINE:
                if toks[k].kind is Kind.COMMENT:
                    tag = toks[k].text[2:].strip().upper()
                    status = _STATUS_MAP.get(tag, Status.UNTOUCHED)
                    span_end = toks[k].span[1]
                    break
                k += 1
            entries.append(Entry(key_tok.text, value, status, (span_start, span_end)))
            # fast-forward to newline to continue loop
            while j < len(toks) and toks[j].kind is not Kind.NEWLINE:
                j += 1
            i = j
        i += 1

    return ParsedFile(path, entries, raw)
