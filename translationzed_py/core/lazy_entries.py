from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from translationzed_py.core.model import Entry, Status
from translationzed_py.core.parse_utils import (
    _decode_text,
    _resolve_encoding,
    _unescape,
)


@dataclass(frozen=True, slots=True)
class EntryMeta:
    key: str
    status: Status
    span: tuple[int, int]
    segments: tuple[int, ...]
    gaps: tuple[bytes, ...]
    raw: bool
    seg_spans: tuple[tuple[int, int], ...]


class LazyEntries:
    def __init__(self, raw: bytes, encoding: str, metas: list[EntryMeta]) -> None:
        self._raw = raw
        self._encoding, _bom_len = _resolve_encoding(encoding, raw)
        self._metas = metas
        self._value_cache: dict[int, str] = {}
        self._overrides: dict[int, Entry] = {}

    def __len__(self) -> int:
        return len(self._metas)

    def __getitem__(self, index: int) -> Entry:
        return self._entry_at(index, cache_value=True)

    def __setitem__(self, index: int, entry: Entry) -> None:
        self._overrides[index] = entry
        self._value_cache[index] = entry.value

    def __iter__(self) -> Iterator[Entry]:
        for idx in range(len(self._metas)):
            yield self._entry_at(idx, cache_value=False)

    def prefetch(self, start: int, end: int) -> None:
        if not self._metas:
            return
        lo = max(0, start)
        hi = min(len(self._metas) - 1, end)
        for idx in range(lo, hi + 1):
            if idx in self._overrides or idx in self._value_cache:
                continue
            meta = self._metas[idx]
            self._value_cache[idx] = self._value_for_meta(meta)

    def _entry_at(self, index: int, *, cache_value: bool) -> Entry:
        if index in self._overrides:
            return self._overrides[index]
        meta = self._metas[index]
        if cache_value:
            value = self._value_cache.get(index)
            if value is None:
                value = self._value_for_meta(meta)
                self._value_cache[index] = value
        else:
            value = self._value_for_meta(meta)
        return Entry(
            meta.key,
            value,
            meta.status,
            meta.span,
            meta.segments,
            meta.gaps,
            meta.raw,
        )

    def _value_for_meta(self, meta: EntryMeta) -> str:
        if meta.raw:
            return _decode_text(self._raw, self._encoding)
        parts: list[str] = []
        for start, end in meta.seg_spans:
            raw_slice = self._raw[start:end]
            text = raw_slice.decode(self._encoding, errors="replace")
            if start == 0 and text.startswith("\ufeff"):
                text = text[1:]
            if text.startswith('"'):
                inner = text[1:-1] if text.endswith('"') else text[1:]
                parts.append(_unescape(inner))
            else:
                parts.append(text.rstrip())
        return "".join(parts)
