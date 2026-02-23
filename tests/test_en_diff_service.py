"""Test module for EN diff classification helpers."""

from __future__ import annotations

from translationzed_py.core import en_diff_service
from translationzed_py.core.en_diff_snapshot import hash_key, hash_text


def test_classify_file_reports_new_removed_and_modified() -> None:
    """Verify classifier reports all diff groups deterministically."""
    en_values = {"A": "one", "B": "two", "C": "three"}
    locale_values = {"B": "dua", "D": "extra"}
    snapshot_rows = {
        hash_key("B"): hash_text("OLD_TWO"),
    }
    result = en_diff_service.classify_file(
        en_values=en_values,
        locale_values=locale_values,
        snapshot_rows=snapshot_rows,
    )
    assert result.new_keys == ("A", "C")
    assert result.removed_keys == ("D",)
    assert result.modified_keys == ("B",)


def test_classify_file_ignores_modified_when_snapshot_missing() -> None:
    """Verify modified markers are not emitted without baseline snapshot."""
    en_values = {"A": "one"}
    locale_values = {"A": "uno"}
    result = en_diff_service.classify_file(
        en_values=en_values,
        locale_values=locale_values,
        snapshot_rows={},
    )
    assert result.new_keys == ()
    assert result.removed_keys == ()
    assert result.modified_keys == ()


def test_classify_file_preserves_en_order_for_new_keys() -> None:
    """Verify NEW keys follow EN declaration order."""
    en_values = {"K2": "2", "K1": "1", "K3": "3"}
    locale_values = {"K2": "x"}
    result = en_diff_service.classify_file(
        en_values=en_values,
        locale_values=locale_values,
        snapshot_rows={},
    )
    assert result.new_keys == ("K1", "K3")
