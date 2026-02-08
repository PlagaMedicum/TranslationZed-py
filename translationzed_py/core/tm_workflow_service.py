from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Literal

from .tm_query import (
    TMQueryKey,
    TMQueryPolicy,
    current_key_from_lookup,
    filter_matches,
    has_enabled_origins,
    make_cache_key,
)
from .tm_store import TMMatch


@dataclass(frozen=True, slots=True)
class TMPendingBatch:
    file_key: str
    target_locale: str
    rows: tuple[tuple[str, str, str], ...]


@dataclass(frozen=True, slots=True)
class TMQueryPlan:
    mode: Literal["disabled", "no_lookup", "cached", "query"]
    message: str
    cache_key: TMQueryKey | None = None
    matches: list[TMMatch] | None = None


@dataclass(slots=True)
class TMWorkflowService:
    cache_limit: int = 128
    _cache: OrderedDict[TMQueryKey, list[TMMatch]] = field(
        init=False,
        repr=False,
        default_factory=OrderedDict,
    )
    _pending: dict[str, dict[str, tuple[str, str, str]]] = field(
        init=False,
        repr=False,
        default_factory=dict,
    )

    def clear_cache(self) -> None:
        self._cache.clear()

    def queue_updates(self, path: str, rows: Iterable[tuple[str, str, str]]) -> None:
        self._cache.clear()
        bucket = self._pending.setdefault(path, {})
        for key, source_text, value_text in rows:
            bucket[key] = (key, source_text, value_text)

    def pending_batches(
        self,
        *,
        locale_for_path: Callable[[str], str | None],
        paths: Iterable[str] | None = None,
    ) -> list[TMPendingBatch]:
        wanted = None if paths is None else set(paths)
        batches: list[TMPendingBatch] = []
        for file_key, by_key in self._pending.items():
            if wanted is not None and file_key not in wanted:
                continue
            if not by_key:
                continue
            locale = locale_for_path(file_key)
            if not locale:
                continue
            batches.append(
                TMPendingBatch(
                    file_key=file_key,
                    target_locale=locale,
                    rows=tuple(by_key.values()),
                )
            )
        return batches

    def mark_batch_flushed(self, file_key: str) -> None:
        self._pending.pop(file_key, None)

    def plan_query(
        self,
        *,
        lookup: tuple[str, str] | None,
        policy: TMQueryPolicy,
    ) -> TMQueryPlan:
        if not has_enabled_origins(policy):
            return TMQueryPlan(mode="disabled", message="No TM origins enabled.")
        if lookup is None:
            return TMQueryPlan(
                mode="no_lookup", message="Select a row to see TM suggestions."
            )
        source_text, locale = lookup
        cache_key = make_cache_key(
            source_text,
            target_locale=locale,
            policy=policy,
        )
        matches = self._cache.get(cache_key)
        if matches is not None:
            return TMQueryPlan(
                mode="cached",
                message="TM suggestions",
                cache_key=cache_key,
                matches=matches,
            )
        return TMQueryPlan(
            mode="query",
            message="Searching TM...",
            cache_key=cache_key,
            matches=None,
        )

    def accept_query_result(
        self,
        *,
        cache_key: TMQueryKey,
        matches: list[TMMatch],
        lookup: tuple[str, str] | None,
        policy: TMQueryPolicy,
    ) -> bool:
        self._cache[cache_key] = matches
        while len(self._cache) > self.cache_limit:
            self._cache.popitem(last=False)
        current_key = current_key_from_lookup(lookup, policy=policy)
        return current_key == cache_key

    def filter_matches(
        self, matches: list[TMMatch], *, policy: TMQueryPolicy
    ) -> list[TMMatch]:
        return filter_matches(matches, policy=policy)
