"""Strict, lossless editing support for flat B42 translation JSON objects."""

from __future__ import annotations

import codecs
import json
from collections.abc import Mapping
from pathlib import Path

from .atomic_io import write_bytes_atomic
from .lazy_entries import EntryMeta, LazyEntries
from .model import Entry, ParsedFile, Status
from .parse_utils import _hash_key_u64

MAX_JSON_FILE_BYTES = 64 * 1024 * 1024
_JSON_WHITESPACE = frozenset(b" \t\r\n")


class TranslationJSONError(ValueError):
    """Report malformed or unsupported B42 translation JSON safely."""


def _at(message: str, offset: int) -> TranslationJSONError:
    return TranslationJSONError(f"{message} (byte {offset}).")


def _skip_whitespace(raw: bytes, offset: int) -> int:
    while offset < len(raw) and raw[offset] in _JSON_WHITESPACE:
        offset += 1
    return offset


def _scan_string(raw: bytes, start: int) -> int:
    if start >= len(raw) or raw[start] != ord('"'):
        raise _at("Expected a JSON string", start)
    offset = start + 1
    while offset < len(raw):
        current = raw[offset]
        if current == ord('"'):
            return offset + 1
        if current == ord("\\"):
            offset += 2
            continue
        offset += 1
    raise _at("Unterminated JSON string", start)


def _decode_literal(literal: str) -> str:
    try:
        value = json.loads(literal)
    except json.JSONDecodeError as exc:
        raise TranslationJSONError(
            f"Invalid JSON string literal at character {exc.pos}: {exc.msg}."
        ) from exc
    if not isinstance(value, str):
        raise TranslationJSONError("Translation keys and values must be JSON strings.")
    if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
        raise TranslationJSONError("JSON strings must not contain unpaired surrogates.")
    return value


def _decode_literal_bytes(raw: bytes, start: int, end: int) -> str:
    try:
        literal = raw[start:end].decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise _at("Translation JSON must be valid UTF-8", start + exc.start) from exc
    return _decode_literal(literal)


def _parse_entries(raw: bytes, *, lazy: bool) -> list[Entry] | LazyEntries:
    offset = _skip_whitespace(raw, 0)
    if offset >= len(raw) or raw[offset] != ord("{"):
        raise _at("B42 translation JSON must be a top-level object", offset)
    offset = _skip_whitespace(raw, offset + 1)
    entries: list[Entry] = []
    metas: list[EntryMeta] = []
    seen: set[str] = set()
    if offset < len(raw) and raw[offset] == ord("}"):
        offset = _skip_whitespace(raw, offset + 1)
        if offset != len(raw):
            raise _at("Unexpected content after the top-level object", offset)
        return (
            LazyEntries(raw, "utf-8", [], literal_decoder=_decode_literal)
            if lazy
            else []
        )

    while True:
        if offset >= len(raw) or raw[offset] != ord('"'):
            raise _at("Translation object keys must be JSON strings", offset)
        key_start = offset
        key_end = _scan_string(raw, key_start)
        key = _decode_literal_bytes(raw, key_start, key_end)
        if key in seen:
            raise _at(f"Duplicate translation key {key!r} is unsupported", key_start)
        seen.add(key)

        offset = _skip_whitespace(raw, key_end)
        if offset >= len(raw) or raw[offset] != ord(":"):
            raise _at("Expected ':' after translation key", offset)
        offset = _skip_whitespace(raw, offset + 1)
        if offset >= len(raw) or raw[offset] != ord('"'):
            raise _at("Translation object values must be JSON strings", offset)
        value_start = offset
        value_end = _scan_string(raw, value_start)
        value = _decode_literal_bytes(raw, value_start, value_end)
        key_hash = _hash_key_u64(key)
        if lazy:
            metas.append(
                EntryMeta(
                    key,
                    Status.UNTOUCHED,
                    (value_start, value_end),
                    (len(value),),
                    (),
                    False,
                    ((value_start, value_end),),
                    key_hash,
                )
            )
        else:
            entries.append(
                Entry(
                    key,
                    value,
                    Status.UNTOUCHED,
                    (value_start, value_end),
                    (len(value),),
                    (),
                    False,
                    key_hash,
                )
            )

        offset = _skip_whitespace(raw, value_end)
        if offset >= len(raw):
            raise _at("Unterminated top-level translation object", offset)
        delimiter = raw[offset]
        if delimiter == ord("}"):
            offset = _skip_whitespace(raw, offset + 1)
            if offset != len(raw):
                raise _at("Unexpected content after the top-level object", offset)
            break
        if delimiter != ord(","):
            raise _at("Expected ',' or '}' after translation value", offset)
        offset = _skip_whitespace(raw, offset + 1)
        if offset < len(raw) and raw[offset] == ord("}"):
            raise _at("Trailing commas are not valid translation JSON", offset)

    if lazy:
        return LazyEntries(
            raw,
            "utf-8",
            metas,
            literal_decoder=_decode_literal,
        )
    return entries


def parse(path: Path, *, lazy: bool = False) -> ParsedFile:
    """Parse one confirmed B42 flat string-map JSON file without writing it."""
    raw = path.read_bytes()
    if len(raw) > MAX_JSON_FILE_BYTES:
        limit_mib = MAX_JSON_FILE_BYTES // (1024 * 1024)
        raise TranslationJSONError(
            f"Translation JSON exceeds the {limit_mib} MiB safety limit."
        )
    if raw.startswith(codecs.BOM_UTF8):
        raise TranslationJSONError(
            "UTF-8 BOM is unsupported by the confirmed B42 translation format."
        )
    try:
        raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise _at("Translation JSON must be valid UTF-8", exc.start) from exc
    return ParsedFile(path, _parse_entries(raw, lazy=lazy), raw)


def _encode_literal(key: str, value: str) -> bytes:
    if not isinstance(value, str):
        raise TranslationJSONError(f"Translation value for {key!r} must be a string.")
    try:
        return json.dumps(value, ensure_ascii=False).encode("utf-8")
    except UnicodeEncodeError as exc:
        raise TranslationJSONError(
            f"Translation value for {key!r} contains invalid Unicode."
        ) from exc


def save(pf: ParsedFile, new_entries: Mapping[str, str]) -> None:
    """Atomically replace only edited JSON value literals and refresh spans."""
    buf = bytearray(pf.raw_bytes())
    original_raw = bytes(buf)
    replacements: list[tuple[int, int, bytes]] = []
    changed: dict[int, tuple[str, int]] = {}
    for index, entry in enumerate(pf.entries):
        if entry.key not in new_entries:
            continue
        new_value = new_entries[entry.key]
        on_disk = _decode_literal_bytes(original_raw, entry.span[0], entry.span[1])
        if new_value == on_disk:
            continue
        literal = _encode_literal(entry.key, new_value)
        replacements.append((entry.span[0], entry.span[1], literal))
        changed[index] = (new_value, len(literal))

    if not replacements:
        pf.dirty = False
        return
    for start, end, literal in sorted(replacements, reverse=True):
        buf[start:end] = literal
    write_bytes_atomic(pf.path, bytes(buf))

    shift = 0
    refreshed: list[Entry] = []
    for index, entry in enumerate(pf.entries):
        start, end = entry.span
        new_start = start + shift
        if index in changed:
            value, literal_size = changed[index]
            new_end = new_start + literal_size
            shift += literal_size - (end - start)
            refreshed.append(
                Entry(
                    entry.key,
                    value,
                    entry.status,
                    (new_start, new_end),
                    (len(value),),
                    (),
                    False,
                    entry.key_hash,
                )
            )
        else:
            refreshed.append(
                Entry(
                    entry.key,
                    entry.value,
                    entry.status,
                    (new_start, end + shift),
                    entry.segments,
                    entry.gaps,
                    entry.raw,
                    entry.key_hash,
                )
            )
    pf.entries = refreshed
    pf._raw = buf
    pf.dirty = False
