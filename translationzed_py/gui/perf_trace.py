"""Lightweight runtime performance tracing utilities for GUI instrumentation."""

from __future__ import annotations

import os
import sys
import time
from contextlib import suppress
from dataclasses import dataclass

_TRACE_ENV = "TZP_PERF_TRACE"
_DEFAULT_CATEGORIES = {
    "paint",
    "row_resize",
    "startup",
    "cache_scan",
    "auto_open",
    "selection",
    "detail_sync",
    "layout",
}


def _parse_categories(value: str) -> set[str]:
    raw = value.strip().lower()
    if not raw:
        return set()
    if raw in {"1", "true", "yes", "on", "all"}:
        return set(_DEFAULT_CATEGORIES)
    parts = {part.strip() for part in raw.split(",") if part.strip()}
    if "all" in parts:
        return set(_DEFAULT_CATEGORIES)
    return {part for part in parts if part in _DEFAULT_CATEGORIES}


@dataclass
class _Bucket:
    total_ms: float = 0.0
    calls: int = 0
    items: int = 0
    max_ms: float = 0.0
    unit: str = "items"


class PerfTrace:
    """Accumulate and periodically flush categorized timing metrics."""

    def __init__(
        self, categories: set[str], *, interval_s: float = 1.0, out=None
    ) -> None:
        """Initialize trace buckets for enabled categories."""
        self.enabled = bool(categories)
        self._categories = categories
        self._interval_s = interval_s
        self._out = out or sys.stderr
        self._buckets: dict[str, _Bucket] = {}
        self._last_flush = time.monotonic()

    @classmethod
    def from_env(cls) -> PerfTrace:
        """Build a trace instance from `TZP_PERF_TRACE` environment settings."""
        return cls(_parse_categories(os.getenv(_TRACE_ENV, "")))

    def start(self, name: str) -> float | None:
        """Start timing for a category and return start timestamp when enabled."""
        if not self.enabled or name not in self._categories:
            return None
        return time.perf_counter()

    def stop(
        self, name: str, start: float | None, *, items: int = 1, unit: str = "items"
    ) -> None:
        """Stop timing for a category and record elapsed duration."""
        if start is None:
            return
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        self.record(name, elapsed_ms, items=items, unit=unit)

    def record(
        self, name: str, elapsed_ms: float, *, items: int = 1, unit: str = "items"
    ) -> None:
        """Record one measured duration sample for a named category."""
        if not self.enabled or name not in self._categories:
            return
        bucket = self._buckets.get(name)
        if bucket is None:
            bucket = _Bucket(unit=unit)
            self._buckets[name] = bucket
        if bucket.unit != unit:
            unit = bucket.unit
        bucket.total_ms += elapsed_ms
        bucket.calls += 1
        bucket.items += max(0, items)
        if elapsed_ms > bucket.max_ms:
            bucket.max_ms = elapsed_ms
        now = time.monotonic()
        if now - self._last_flush >= self._interval_s:
            self._flush(now)

    def _flush(self, now: float) -> None:
        if not self._buckets:
            self._last_flush = now
            return
        lines: list[str] = []
        for name in sorted(self._buckets):
            bucket = self._buckets[name]
            avg_call = bucket.total_ms / bucket.calls if bucket.calls else 0.0
            if bucket.items:
                avg_item = bucket.total_ms / bucket.items
                item_part = f", {avg_item:.4f}ms/{bucket.unit}"
            else:
                item_part = ""
            lines.append(
                f"perf {name}: {bucket.calls} calls, {bucket.items} {bucket.unit}, "
                f"{bucket.total_ms:.1f}ms total, {avg_call:.2f}ms/call{item_part}, "
                f"max {bucket.max_ms:.1f}ms"
            )
        self._out.write("\n".join(lines) + "\n")
        with suppress(Exception):
            self._out.flush()
        self._buckets.clear()
        self._last_flush = now


PERF_TRACE = PerfTrace.from_env()
