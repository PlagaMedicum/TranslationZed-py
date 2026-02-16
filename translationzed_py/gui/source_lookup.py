from __future__ import annotations

from collections.abc import Mapping, Sequence

from translationzed_py.core import Entry


class SourceLookup(Mapping[str, str]):
    __slots__ = ("_by_row", "_keys", "_by_key")

    def __init__(
        self,
        *,
        by_row: Sequence[str] | None = None,
        keys: list[str] | None = None,
        by_key: dict[str, str] | None = None,
    ) -> None:
        self._by_row = by_row
        self._keys = keys
        self._by_key = by_key

    @property
    def by_row(self) -> Sequence[str] | None:
        return self._by_row

    def _ensure_by_key(self) -> dict[str, str]:
        if self._by_key is None:
            if self._by_row is None or self._keys is None:
                self._by_key = {}
            else:
                by_key: dict[str, str] = {}
                limit = min(len(self._keys), len(self._by_row))
                for idx in range(limit):
                    by_key[self._keys[idx]] = self._by_row[idx]
                self._by_key = by_key
        return self._by_key

    def get(self, key: str, default: str = "") -> str:
        return self._ensure_by_key().get(key, default)

    def __getitem__(self, key: str) -> str:
        return self.get(key, "")

    def __iter__(self):
        return iter(self._ensure_by_key())

    def __len__(self) -> int:
        return len(self._ensure_by_key())


class LazySourceRows:
    __slots__ = ("_entries",)

    def __init__(self, entries: Sequence[Entry]) -> None:
        self._entries = entries

    def __len__(self) -> int:
        return len(self._entries)

    def __getitem__(self, idx):
        if isinstance(idx, slice):
            start, stop, step = idx.indices(len(self._entries))
            return [self._entries[i].value for i in range(start, stop, step)]
        return self._entries[idx].value

    def length_at(self, idx: int) -> int:
        entries = self._entries
        if hasattr(entries, "meta_at"):
            try:
                meta = entries.meta_at(idx)
                if meta.segments:
                    return sum(meta.segments)
            except Exception:
                return 0
            return 0
        value = entries[idx].value
        return len(value) if value else 0

    def preview_at(self, idx: int, limit: int) -> str:
        entries = self._entries
        if hasattr(entries, "preview_at"):
            try:
                return entries.preview_at(idx, limit)
            except Exception:
                return ""
        value = entries[idx].value
        if not value:
            return ""
        if limit <= 0:
            return ""
        return value[:limit]
