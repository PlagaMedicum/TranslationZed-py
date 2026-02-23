"""Unit tests for progress metric semantics."""

from __future__ import annotations

from translationzed_py.core.model import Status
from translationzed_py.gui.progress_metrics import (
    StatusProgress,
    from_statuses,
    proofread_percent,
    translated_percent,
)


def test_translated_excludes_proofread_in_percent_semantics() -> None:
    """Verify translated percent counts translated-only entries."""
    progress = from_statuses(
        [
            Status.UNTOUCHED,
            Status.FOR_REVIEW,
            Status.TRANSLATED,
            Status.PROOFREAD,
        ]
    )
    assert translated_percent(progress) == 25
    assert proofread_percent(progress) == 25


def test_status_progress_roundtrip_tuple_normalization() -> None:
    """Verify tuple payload normalization keeps non-negative values."""
    progress = StatusProgress.from_tuple((-1, 2, 3, 4))
    assert progress.as_tuple() == (0, 2, 3, 4)
    assert progress.total == 9

