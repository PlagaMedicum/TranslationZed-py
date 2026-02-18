"""Model module."""

from __future__ import annotations

import enum
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class EntrySequence(Protocol):
    """Describe mutable sequence operations required by parsed entries."""

    def __len__(self) -> int:
        """Return the number of entries."""
        ...

    def __getitem__(self, index: int) -> Entry:
        """Return an entry at the given index."""
        ...

    def __setitem__(self, index: int, entry: Entry) -> None:
        """Set an entry at the given index."""
        ...

    def __iter__(self) -> Iterator[Entry]:
        """Iterate over entries in sequence order."""
        ...


class Status(enum.IntEnum):
    """Represent Status."""

    UNTOUCHED = 0
    FOR_REVIEW = 1
    TRANSLATED = 2
    PROOFREAD = 3  # spec §5.3 :contentReference[oaicite:1]{index=1}

    def label(self) -> str:
        """Execute label."""
        return self.name.replace("_", " ").title()


STATUS_ORDER = (
    Status.UNTOUCHED,
    Status.FOR_REVIEW,
    Status.TRANSLATED,
    Status.PROOFREAD,
)


@dataclass(frozen=True, slots=True)
class Entry:
    """Represent Entry."""

    key: str
    value: str
    status: Status
    span: tuple[int, int]  # byte offsets in raw file
    segments: tuple[int, ...]  # unescaped segment lengths
    gaps: tuple[bytes, ...]  # raw bytes between string literals
    raw: bool = False  # plain-text entry (no quoted literal in file)
    key_hash: int | None = None  # precomputed xxhash64 of key


class ParsedFile:
    """Represent ParsedFile."""

    def __init__(self, path: Path, entries: EntrySequence, raw: bytes) -> None:
        """Initialize the instance."""
        self.path = path
        self.entries = entries
        self._raw = bytearray(raw)
        self.dirty = False

    # read-only helpers
    def get_entry(self, key: str) -> Entry | None:
        """Return entry."""
        return next((e for e in self.entries if e.key == key), None)

    def raw_bytes(self) -> bytes:  # round-trip tests will use this
        """Execute raw bytes."""
        return bytes(self._raw)
