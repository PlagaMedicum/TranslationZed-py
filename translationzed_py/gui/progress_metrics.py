"""Helpers for canonical translation/proofread progress calculations."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from translationzed_py.core.model import Status


@dataclass(frozen=True, slots=True)
class StatusProgress:
    """Store canonical status distribution for one file/locale scope."""

    untouched: int = 0
    for_review: int = 0
    translated: int = 0
    proofread: int = 0

    @property
    def total(self) -> int:
        """Return total number of entries in the distribution."""
        return max(0, self.untouched) + max(0, self.for_review) + max(
            0, self.translated
        ) + max(0, self.proofread)

    def as_tuple(self) -> tuple[int, int, int, int]:
        """Return normalized tuple payload for Qt item roles."""
        return (
            max(0, int(self.untouched)),
            max(0, int(self.for_review)),
            max(0, int(self.translated)),
            max(0, int(self.proofread)),
        )

    @classmethod
    def from_tuple(cls, values: tuple[int, int, int, int] | None) -> StatusProgress:
        """Build a normalized progress object from tuple payload."""
        if not values:
            return cls()
        untouched, for_review, translated, proofread = values
        return cls(
            untouched=max(0, int(untouched)),
            for_review=max(0, int(for_review)),
            translated=max(0, int(translated)),
            proofread=max(0, int(proofread)),
        )


def from_statuses(statuses: Iterable[Status]) -> StatusProgress:
    """Build progress distribution from canonical entry statuses."""
    untouched = 0
    for_review = 0
    translated = 0
    proofread = 0
    for status in statuses:
        if status == Status.PROOFREAD:
            proofread += 1
            continue
        if status == Status.TRANSLATED:
            translated += 1
            continue
        if status == Status.FOR_REVIEW:
            for_review += 1
            continue
        untouched += 1
    return StatusProgress(
        untouched=untouched,
        for_review=for_review,
        translated=translated,
        proofread=proofread,
    )


def percent(value: int, total: int) -> int:
    """Return rounded percent in range 0..100."""
    normalized_total = max(0, int(total))
    if normalized_total <= 0:
        return 0
    return int(round((max(0, int(value)) * 100) / normalized_total))


def translated_percent(progress: StatusProgress) -> int:
    """Return translated-only percent (proofread excluded)."""
    return percent(progress.translated, progress.total)


def proofread_percent(progress: StatusProgress) -> int:
    """Return proofread percent."""
    return percent(progress.proofread, progress.total)

