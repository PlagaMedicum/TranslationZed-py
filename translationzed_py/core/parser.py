from __future__ import annotations

import codecs
import enum
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # forward-refs for mypy, no runtime cycle
    from .model import Entry, ParsedFile, Status


# ── helper --------------------------------------------------------------------
_STATUS_MAP: dict[str, Status] = {}  # populated on first parse()


def _unescape(raw: str) -> str:
    """Unescape only escaped quotes/backslashes; keep other escapes literal."""
    if "\\" not in raw:
        if '""' not in raw:
            return raw
    out: list[str] = []
    i = 0
    while i < len(raw):
        ch = raw[i]
        if ch == "\\" and i + 1 < len(raw):
            nxt = raw[i + 1]
            if nxt in {'"', "\\"}:
                out.append(nxt)
                i += 2
                continue
        if ch == '"' and i + 1 < len(raw) and raw[i + 1] == '"':
            out.append('"')
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


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
_PATTERNS = [
    (Kind.TRIVIA, r"[ \t]+"),
    (Kind.NEWLINE, r"\r?\n"),
    (Kind.COMMENT, r"--[^\n]*"),
    (Kind.KEY, r"[^\s=\"\.][^=\r\n]*?(?=\s*=)"),
    (Kind.EQUAL, r"="),
    (Kind.CONCAT, r"\.\."),
    (Kind.BRACE, r"[{}]"),
    (Kind.COMMA, r","),
]
_TOKEN_RE = re.compile(
    "|".join(rf"(?P<{k.name}>{p})" for k, p in _PATTERNS),
    re.DOTALL,
)


def _encoding_for_offsets(encoding: str, raw: bytes) -> tuple[str, int]:
    enc = encoding.lower().replace("_", "-")
    if enc in {"utf-8", "utf8"}:
        if raw.startswith(codecs.BOM_UTF8):
            return "utf-8", 3
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


def _decode_text(data: bytes, encoding: str) -> str:
    text = data.decode(encoding, errors="replace")
    if text.startswith("\ufeff"):
        return text[1:]
    return text


def _read_string_token(text: str, pos: int) -> int:
    i = pos + 1
    while i < len(text):
        ch = text[i]
        if ch == "\\":
            i += 2
            continue
        if ch == '"':
            if i == pos + 1:
                i += 1
                continue
            if i + 1 < len(text) and text[i + 1] == '"':
                j = i + 2
                if j >= len(text) or text[j] in {",", "}", "\r", "\n"}:
                    i += 2
                    return i
                i += 2
                continue
            i += 1
            return i
        i += 1
    raise SyntaxError("Unterminated string literal")


# ── The generator the test asked about ────────────────────────────────────────
def _tokenise(data: bytes, *, encoding: str = "utf-8") -> Iterable[Tok]:
    text = _decode_text(data, encoding)
    enc_for_map, bom_len = _encoding_for_offsets(encoding, data)
    offsets = _build_offset_map(text, enc_for_map)
    expected_len = len(data) - bom_len
    if offsets[-1] != expected_len:
        raise ValueError(
            f"Encoding length mismatch: expected {expected_len}, got {offsets[-1]}"
        )

    pos = 0
    while pos < len(text):
        if text[pos] == '"':
            end = _read_string_token(text, pos)
            span = (offsets[pos] + bom_len, offsets[end] + bom_len)
            yield Tok(Kind.STRING, span, text[pos:end])
            pos = end
            continue
        m = _TOKEN_RE.match(text, pos)
        if not m:
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
    if b"=" not in raw:
        text = _decode_text(raw, encoding)
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
    if path.name.startswith("News_"):
        text = _decode_text(raw, encoding)
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
    toks = list(_tokenise(raw, encoding=encoding))
    saw_equal = any(tok.kind is Kind.EQUAL for tok in toks)

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
            seg_lens: list[int] = []
            seg_spans: list[tuple[int, int]] = []
            span_start: int | None = None
            span_end: int | None = None
            while j < len(toks):
                if toks[j].kind is Kind.STRING:
                    seg_text = _unescape(toks[j].text[1:-1])
                    parts.append(seg_text)
                    seg_lens.append(len(seg_text))
                    seg_spans.append(toks[j].span)
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
            gaps: list[bytes] = []
            for prev, nxt in zip(seg_spans, seg_spans[1:]):
                gaps.append(raw[prev[1] : nxt[0]])
            key_text = key_tok.text.strip()
            if not key_text:
                i += 1
                continue
            entries.append(
                Entry(
                    key_text,
                    value,
                    status,
                    (span_start, span_end),
                    tuple(seg_lens) if seg_lens else (len(value),),
                    tuple(gaps),
                )
            )
            # fast-forward to newline to continue loop
            while j < len(toks) and toks[j].kind is not Kind.NEWLINE:
                j += 1
            i = j
        i += 1

    if not entries:
        if not saw_equal:
            text = _decode_text(raw, encoding)
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
