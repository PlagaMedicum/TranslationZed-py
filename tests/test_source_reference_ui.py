"""Test module for source reference ui."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QComboBox

from translationzed_py.gui.source_reference_ui import (
    available_source_reference_locales,
    sync_source_reference_combo,
)


def test_available_source_reference_locales_merges_selected_and_project_order() -> None:
    """Verify expected behavior."""
    locales = available_source_reference_locales(
        ["be"],
        all_locales=["EN", "RU", "BE", "KO"],
    )
    assert locales == ["EN", "BE", "RU", "KO"]


def test_sync_source_reference_combo_resolves_mode_from_project_locales(qtbot) -> None:
    """Verify sync source reference combo resolves mode from project locales."""
    combo = QComboBox()
    qtbot.addWidget(combo)
    resolved = sync_source_reference_combo(
        combo,
        current_mode="RU",
        selected_locales=["BE"],
        all_locales=["EN", "BE", "RU"],
    )
    assert resolved == "RU"
    assert [combo.itemData(i) for i in range(combo.count())] == ["EN", "BE", "RU"]


def test_sync_source_reference_combo_honors_fallback_order(qtbot) -> None:
    """Verify sync source reference combo honors fallback order."""
    combo = QComboBox()
    qtbot.addWidget(combo)
    resolved = sync_source_reference_combo(
        combo,
        current_mode="RU",
        selected_locales=["BE"],
        all_locales=["EN", "BE"],
        fallback_default="BE",
        fallback_secondary="EN",
    )
    assert resolved == "BE"
