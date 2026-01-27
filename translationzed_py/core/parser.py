from __future__ import annotations

import ast
import codecs
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
    (Kind.TRIVIA, r"[ \t]+"),
    (Kind.NEWLINE, r"\r?\n"),
    (Kind.COMMENT, r"--[^\n]*"),
    (Kind.KEY, r"[A-Za-z0-9_]+"),
    (Kind.EQUAL, r"="),
    (Kind.CONCAT, r"\.\."),
    (Kind.STRING, r'"(?:\\.|[^"])*"'),  # back-slash escapes
]
_TOKEN_RE = re.compile(
    "|".join(rf"(?P<{k.name}>{p})" for k, p in _PATTERNS),
    re.DOTALL,
)


def _encoding_for_offsets(encoding: str, raw: bytes) -> tuple[str, int]:
    enc = encoding.lower().replace("_", "-")
    if enc in {"utf-16", "utf16"}:
        if raw.startswith(b"\xff\xfe"):
            return "utf-16-le", 2
        if raw.startswith(b"\xfe\xff"):
            return "utf-16-be", 2
        return "utf-16-le", 0
    return encoding, 0


def _build_offset_map(text: str, encoding: str) -> list[int]:
    encoder = codecs.getincrementalencoder(encoding)()
    offsets = [0]
    total = 0
    for ch in text:
        total += len(encoder.encode(ch))
        offsets.append(total)
    return offsets


# ── The generator the test asked about ────────────────────────────────────────
def _tokenise(data: bytes, *, encoding: str = "utf-8") -> Iterable[Tok]:
    text = data.decode(encoding)
    enc_for_map, bom_len = _encoding_for_offsets(encoding, data)
    offsets = _build_offset_map(text, enc_for_map)
    expected_len = len(data) - bom_len
    if offsets[-1] != expected_len:
        raise ValueError(
            f"Encoding length mismatch: expected {expected_len}, got {offsets[-1]}"
        )

    pos = 0
    while pos < len(text):
        m = _TOKEN_RE.match(text, pos)
        if not m:
            raise SyntaxError(f"Unknown sequence at {pos}")

        group = m.lastgroup
        assert group is not None  # narrow the type for mypy
        kind = Kind[group]  # now str, not str|None

        span = (
            offsets[m.start()] + bom_len,
            offsets[m.end()] + bom_len,
        )
        yield Tok(kind, span, m.group())
        pos = m.end()


# ── parse() placeholder – we’ll flesh this out next ───────────────────────────
def parse(path: Path, encoding: str = "utf-8") -> ParsedFile:  # noqa: F821
    """Read *path*, tokenise, and build a ParsedFile with stable spans."""
    # local import avoids an import cycle
    from .model import Entry, ParsedFile, Status

    global _STATUS_MAP
    if not _STATUS_MAP:  # fill once
        _STATUS_MAP = {
            "TRANSLATED": Status.TRANSLATED,
            "PROOFREAD": Status.PROOFREAD,
        }

    raw = path.read_bytes()
    toks = list(_tokenise(raw, encoding=encoding))

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
            span_start: int | None = None
            span_end: int | None = None
            while j < len(toks):
                if toks[j].kind is Kind.STRING:
                    parts.append(_unescape(toks[j].text[1:-1]))
                    if span_start is None:
                        span_start = toks[j].span[0]
                    span_end = toks[j].span[1]
                    j += 1
                elif toks[j].kind in (Kind.TRIVIA, Kind.CONCAT):
                    j += 1
                else:
                    break
            # TODO: preserve original concat/whitespace tokens for loss-less edits.
            if span_start is None or span_end is None:
                i += 1
                continue
            value = "".join(parts)
            # find comment on the same line
            status = Status.UNTOUCHED
            k = j
            while k < len(toks) and toks[k].kind is not Kind.NEWLINE:
                if toks[k].kind is Kind.COMMENT:
                    tag = toks[k].text[2:].strip().upper()
                    status = _STATUS_MAP.get(tag, Status.UNTOUCHED)
                    break
                k += 1
            entries.append(Entry(key_tok.text, value, status, (span_start, span_end)))
            # fast-forward to newline to continue loop
            while j < len(toks) and toks[j].kind is not Kind.NEWLINE:
                j += 1
            i = j
        i += 1

    return ParsedFile(path, entries, raw)
