from __future__ import annotations

import enum
from dataclasses import dataclass
from pathlib import Path


class Status(enum.IntEnum):
    UNTOUCHED = 0
    TRANSLATED = 1
    PROOFREAD = 2  # spec §5.3 :contentReference[oaicite:1]{index=1}


@dataclass(frozen=True, slots=True)
class Entry:
    key: str
    value: str
    status: Status
    span: tuple[int, int]  # byte offsets in raw file
    segments: tuple[int, ...]  # unescaped segment lengths
    gaps: tuple[bytes, ...]  # raw bytes between string literals
    raw: bool = False  # plain-text entry (no quoted literal in file)


class ParsedFile:
    def __init__(self, path: Path, entries: list[Entry], raw: bytes) -> None:
        self.path = path
        self.entries = entries
        self._raw = bytearray(raw)
        self.dirty = False

    # read-only helpers
    def get_entry(self, key: str) -> Entry | None:
        return next((e for e in self.entries if e.key == key), None)

    def raw_bytes(self) -> bytes:  # round-trip tests will use this
        return bytes(self._raw)
