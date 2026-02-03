from __future__ import annotations

import codecs
import enum
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal, overload

if TYPE_CHECKING:  # forward-refs for mypy, no runtime cycle
    from .model import Entry, ParsedFile, Status

from translationzed_py.core.lazy_entries import EntryMeta, LazyEntries
from translationzed_py.core.parse_utils import (
    _decode_text,
    _resolve_encoding,
    _unescape,
)

# ── helper --------------------------------------------------------------------
_STATUS_MAP: dict[str, Status] = {}  # populated on first parse()


# ── Token meta ────────────────────────────────────────────────────────────────
class Kind(enum.IntEnum):
    COMMENT = 0  # -- Up to newline
    KEY = 1
    EQUAL = 2
    STRING = 3
    CONCAT = 4  #  ..
    NEWLINE = 5
    TRIVIA = 6  #  space / tab
    BRACE = 7  # { }
    COMMA = 8  # ,


@dataclass(slots=True, frozen=True)
class Tok:
    kind: Kind
    span: tuple[int, int]  # byte offsets
    text: str


# ── Regex table (spec §5.2) ───────────────────────────────────────────────────
# PZ files include Lua tables, line comments, and occasional block comments.
# The key regex accepts headers followed by "=" or "{" (e.g., `DynamicRadio_BE {`).
_PATTERNS = [
    (Kind.TRIVIA, r"[ \t]+"),
    (Kind.COMMENT, r"--[^\n]*|//[^\n]*|/\*.*?\*/"),
    (Kind.NEWLINE, r"\r?\n"),
    (Kind.KEY, r"[^\s=\"\.][^=\r\n]*?(?=\s*(?:=|{))"),
    (Kind.EQUAL, r"="),
    (Kind.CONCAT, r"\.\."),
    (Kind.BRACE, r"[{}]"),
    (Kind.COMMA, r","),
]
_TOKEN_RE = re.compile(
    "|".join(rf"(?P<{k.name}>{p})" for k, p in _PATTERNS),
    re.DOTALL,
)


def _build_offset_map(text: str, encoding: str) -> list[int]:
    encoder = codecs.getincrementalencoder(encoding)()
    offsets = [0]
    total = 0
    for ch in text:
        total += len(encoder.encode(ch))
        offsets.append(total)
    return offsets


def _read_string_token(text: str, pos: int) -> int:
    i = pos + 1
    while i < len(text):
        ch = text[i]
        if ch in {"\r", "\n"}:
            return i
        if ch == "\\":
            i += 2
            continue
        if ch == '"':
            if i + 1 < len(text) and text[i + 1] == '"':
                j = i + 2
                if j >= len(text) or text[j] in {",", "}", "\r", "\n"}:
                    i += 2
                    return i
                i += 2
                continue
            # Close a string only if the next non-space token is a delimiter
            # and there's no more non-comment text after it.
            j = i + 1
            while j < len(text) and text[j] in {" ", "\t"}:
                j += 1
            if j >= len(text):
                i += 1
                return i
            if text[j] in {",", "}", "\r", "\n"}:
                k = j + 1
                while k < len(text) and text[k] in {" ", "\t"}:
                    k += 1
                if k >= len(text) or text[k] in {"\r", "\n"}:
                    i += 1
                    return i
                if (
                    text.startswith("--", k)
                    or text.startswith("//", k)
                    or text.startswith("/*", k)
                ):
                    i += 1
                    return i
                i += 1
                continue
            if text[j] == "." and j + 1 < len(text) and text[j + 1] == ".":
                k = j + 2
                while k < len(text) and text[k] in {" ", "\t"}:
                    k += 1
                if k < len(text) and text[k] == '"':
                    i += 1
                    return i
                i += 1
                continue
            if text[j] == "-" and j + 1 < len(text) and text[j + 1] == "-":
                i += 1
                return i
            if text[j] == "/" and j + 1 < len(text) and text[j + 1] in {"/", "*"}:
                i += 1
                return i
            i += 1
            continue
        i += 1
    return i


# ── The generator the test asked about ────────────────────────────────────────
def _tokenise(data: bytes, *, encoding: str = "utf-8") -> Iterable[Tok]:
    enc_for_text, bom_len = _resolve_encoding(encoding, data)
    text = _decode_text(data, enc_for_text)
    offsets = _build_offset_map(text, enc_for_text)
    expected_len = len(data) - bom_len
    if offsets[-1] != expected_len:
        raise ValueError(
            f"Encoding length mismatch: expected {expected_len}, got {offsets[-1]}"
        )

    pos = 0
    last_sig: Kind | None = None
    while pos < len(text):
        if text[pos] == '"':
            end = _read_string_token(text, pos)
            span = (offsets[pos] + bom_len, offsets[end] + bom_len)
            yield Tok(Kind.STRING, span, text[pos:end])
            pos = end
            last_sig = Kind.STRING
            continue
        m = _TOKEN_RE.match(text, pos)
        if not m:
            # Salvage malformed lines like:
            #   KEY = bare text (missing opening quote)
            # Used by some PZ files (e.g., Recorded_Media_*).
            if last_sig is Kind.EQUAL:
                end = pos
                while end < len(text):
                    if text[end] in {"\r", "\n"}:
                        break
                    if text[end] == ",":
                        break
                    if (
                        text.startswith("--", end)
                        or text.startswith("//", end)
                        or text.startswith("/*", end)
                    ):
                        break
                    end += 1
                span = (offsets[pos] + bom_len, offsets[end] + bom_len)
                yield Tok(Kind.STRING, span, text[pos:end])
                pos = end
                last_sig = Kind.STRING
                continue
            line = text.count("\n", 0, pos) + 1
            col = pos - text.rfind("\n", 0, pos)
            ch = text[pos] if pos < len(text) else ""
            codepoint = f"U+{ord(ch):04X}" if ch else "EOF"
            snippet_chunk = text[pos : pos + 40]
            snippet = snippet_chunk.splitlines()[0] if snippet_chunk else ""
            raise SyntaxError(
                "Unknown sequence at "
                f"{pos} (line {line}, col {col}, char {codepoint}). "
                f"Snippet: {snippet!r}"
            )

        group = m.lastgroup
        assert group is not None  # narrow the type for mypy
        kind = Kind[group]  # now str, not str|None

        span = (
            offsets[m.start()] + bom_len,
            offsets[m.end()] + bom_len,
        )
        yield Tok(kind, span, m.group())
        pos = m.end()
        if kind is Kind.NEWLINE:
            last_sig = None
        elif kind is not Kind.TRIVIA:
            last_sig = kind


# ── parse() placeholder – we’ll flesh this out next ───────────────────────────
def _segment_text(raw_text: str) -> str:
    if raw_text.startswith('"'):
        if raw_text.endswith('"'):
            return _unescape(raw_text[1:-1])
        return _unescape(raw_text[1:])
    return raw_text.rstrip()


@overload
def _parse_entries_stream(
    raw: bytes,
    *,
    encoding: str,
    lazy_values: Literal[False],
) -> tuple[list[Entry], bool]: ...


@overload
def _parse_entries_stream(
    raw: bytes,
    *,
    encoding: str,
    lazy_values: Literal[True],
) -> tuple[list[EntryMeta], bool]: ...


def _parse_entries_stream(
    raw: bytes,
    *,
    encoding: str,
    lazy_values: bool,
) -> tuple[list[Entry] | list[EntryMeta], bool]:
    # local import avoids an import cycle
    from .model import Entry, Status

    entries_meta: list[EntryMeta] | None = None
    entries_eager: list[Entry] | None = None
    if lazy_values:
        entries_meta = []
    else:
        entries_eager = []
    current_key: Tok | None = None
    collecting = False
    seg_lens: list[int] = []
    seg_spans: list[tuple[int, int]] = []
    span_start: int | None = None
    span_end: int | None = None
    status = Status.UNTOUCHED
    parts: list[str] = []
    saw_equal = False

    def _finalize_entry() -> None:
        nonlocal current_key, collecting, seg_lens, seg_spans, span_start, span_end, status, parts
        if not (collecting and current_key and seg_spans and span_start is not None):
            current_key = None
            collecting = False
            seg_lens = []
            seg_spans = []
            span_start = None
            span_end = None
            status = Status.UNTOUCHED
            parts = []
            return
        key_text = current_key.text.strip()
        if not key_text:
            current_key = None
            collecting = False
            seg_lens = []
            seg_spans = []
            span_start = None
            span_end = None
            status = Status.UNTOUCHED
            parts = []
            return
        gaps: list[bytes] = []
        for prev, nxt in zip(seg_spans, seg_spans[1:], strict=False):
            gaps.append(raw[prev[1] : nxt[0]])
        if lazy_values:
            assert entries_meta is not None
            entries_meta.append(
                EntryMeta(
                    key_text,
                    status,
                    (span_start, span_end or span_start),
                    tuple(seg_lens) if seg_lens else (0,),
                    tuple(gaps),
                    False,
                    tuple(seg_spans),
                )
            )
        else:
            value = "".join(parts)
            assert entries_eager is not None
            entries_eager.append(
                Entry(
                    key_text,
                    value,
                    status,
                    (span_start, span_end or span_start),
                    tuple(seg_lens) if seg_lens else (len(value),),
                    tuple(gaps),
                )
            )
        current_key = None
        collecting = False
        seg_lens = []
        seg_spans = []
        span_start = None
        span_end = None
        status = Status.UNTOUCHED
        parts = []

    for tok in _tokenise(raw, encoding=encoding):
        if tok.kind is Kind.KEY and not collecting:
            current_key = tok
            continue
        if tok.kind is Kind.EQUAL:
            saw_equal = True
            if current_key is None:
                continue
            collecting = True
            seg_lens = []
            seg_spans = []
            span_start = None
            span_end = None
            status = Status.UNTOUCHED
            parts = []
            continue
        if collecting and tok.kind is Kind.STRING:
            seg_text = _segment_text(tok.text)
            seg_lens.append(len(seg_text))
            seg_spans.append(tok.span)
            if span_start is None:
                span_start = tok.span[0]
            span_end = tok.span[1]
            if not lazy_values:
                parts.append(seg_text)
            continue
        if collecting and tok.kind is Kind.COMMENT and seg_spans:
            tag = tok.text[2:].strip().upper()
            status = _STATUS_MAP.get(tag, Status.UNTOUCHED)
            continue
        if tok.kind is Kind.NEWLINE:
            _finalize_entry()
            continue

    _finalize_entry()
    if lazy_values:
        return (entries_meta or []), saw_equal
    return (entries_eager or []), saw_equal


def parse(path: Path, encoding: str = "utf-8") -> ParsedFile:  # noqa: F821
    """Read *path*, tokenise, and build a ParsedFile with stable spans."""
    # local import avoids an import cycle
    from .model import Entry, ParsedFile, Status

    global _STATUS_MAP
    if not _STATUS_MAP:  # fill once
        _STATUS_MAP = {
            "TRANSLATED": Status.TRANSLATED,
            "PROOFREAD": Status.PROOFREAD,
            "FOR REVIEW": Status.FOR_REVIEW,
            "FOR_REVIEW": Status.FOR_REVIEW,
        }

    raw = path.read_bytes()
    resolved_encoding, _ = _resolve_encoding(encoding, raw)
    if b"=" not in raw or path.name.startswith("News_"):
        text = _decode_text(raw, resolved_encoding)
        return ParsedFile(
            path,
            [
                Entry(
                    path.name,
                    text,
                    Status.UNTOUCHED,
                    (0, len(raw)),
                    (len(text),),
                    (),
                    True,
                )
            ],
            raw,
        )

    entries, saw_equal = _parse_entries_stream(
        raw,
        encoding=encoding,
        lazy_values=False,
    )

    if not entries:
        if not saw_equal:
            text = _decode_text(raw, resolved_encoding)
            return ParsedFile(
                path,
                [
                    Entry(
                        path.name,
                        text,
                        Status.UNTOUCHED,
                        (0, len(raw)),
                        (len(text),),
                        (),
                        True,
                    )
                ],
                raw,
            )
        raise ValueError("Unsupported file format (no translatable entries found).")

    return ParsedFile(path, entries, raw)


def parse_lazy(path: Path, encoding: str = "utf-8") -> ParsedFile:  # noqa: F821
    """Read *path* and build a ParsedFile with lazy entry values."""
    from .model import ParsedFile, Status

    global _STATUS_MAP
    if not _STATUS_MAP:  # fill once
        _STATUS_MAP = {
            "TRANSLATED": Status.TRANSLATED,
            "PROOFREAD": Status.PROOFREAD,
            "FOR REVIEW": Status.FOR_REVIEW,
            "FOR_REVIEW": Status.FOR_REVIEW,
        }

    raw = path.read_bytes()
    resolved_encoding, _ = _resolve_encoding(encoding, raw)
    if b"=" not in raw or path.name.startswith("News_"):
        text = _decode_text(raw, resolved_encoding)
        meta = EntryMeta(
            path.name,
            Status.UNTOUCHED,
            (0, len(raw)),
            (len(text),),
            (),
            True,
            ((0, len(raw)),),
        )
        return ParsedFile(path, LazyEntries(raw, encoding, [meta]), raw)

    entries, saw_equal = _parse_entries_stream(
        raw,
        encoding=encoding,
        lazy_values=True,
    )

    if not entries:
        if not saw_equal:
            text = _decode_text(raw, resolved_encoding)
            meta = EntryMeta(
                path.name,
                Status.UNTOUCHED,
                (0, len(raw)),
                (len(text),),
                (),
                True,
                ((0, len(raw)),),
            )
            return ParsedFile(path, LazyEntries(raw, encoding, [meta]), raw)
        raise ValueError("Unsupported file format (no translatable entries found).")

    return ParsedFile(path, LazyEntries(raw, encoding, list(entries)), raw)
