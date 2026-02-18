"""Test module for GUI dialog coverage."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QCheckBox

from translationzed_py.core.project_scanner import LocaleMeta
from translationzed_py.gui.dialogs import (
    AboutDialog,
    ConflictChoiceDialog,
    LocaleChooserDialog,
    ReplaceFilesDialog,
    SaveFilesDialog,
    TmLanguageDialog,
)


def _checkbox_texts(dialog: LocaleChooserDialog) -> list[str]:
    """Return checkbox labels from chooser layout order."""
    labels: list[str] = []
    for idx in range(dialog._list_layout.count()):
        widget = dialog._list_layout.itemAt(idx).widget()
        if isinstance(widget, QCheckBox):
            labels.append(widget.text())
    return labels


def test_locale_chooser_selected_codes_and_rebuild_order(qtbot, tmp_path: Path) -> None:
    """Verify chooser selection and checked-first reorder behavior."""
    locales = [
        LocaleMeta("RU", tmp_path / "RU", "Russian", "utf-8"),
        LocaleMeta("EN", tmp_path / "EN", "English", "utf-8"),
        LocaleMeta("BE", tmp_path / "BE", "Belarusian", "utf-8"),
    ]
    dialog = LocaleChooserDialog(locales, preselected=["RU"])
    qtbot.addWidget(dialog)

    assert set(dialog.selected_codes()) == {"RU"}
    assert _checkbox_texts(dialog)[0].startswith("RU")

    dialog._boxes["BE"].setChecked(True)
    assert set(dialog.selected_codes()) == {"BE", "RU"}
    assert _checkbox_texts(dialog)[0].startswith("BE")


def test_save_files_dialog_toggle_selection_and_choice(qtbot) -> None:
    """Verify save dialog tracks checkboxes and selected action."""
    dialog = SaveFilesDialog(["a.txt", "b.txt"])
    qtbot.addWidget(dialog)

    assert dialog.choice() == "cancel"
    assert dialog.selected_files() == ["a.txt", "b.txt"]

    dialog._select_none()
    assert dialog.selected_files() == []

    dialog._select_all()
    assert dialog.selected_files() == ["a.txt", "b.txt"]

    dialog._set_choice("cache")
    assert dialog.choice() == "cache"


def test_tm_language_dialog_defaults_and_skip_all_flow(qtbot) -> None:
    """Verify TM language dialog applies defaults and skip-all behavior."""
    dialog = TmLanguageDialog(
        ["EN", "BE"],
        default_source="EN",
        default_target="BE",
        allow_skip_all=True,
    )
    qtbot.addWidget(dialog)

    assert dialog.source_locale() == "EN"
    assert dialog.target_locale() == "BE"
    assert dialog.skip_all_requested() is False

    dialog._skip_all_now()
    assert dialog.skip_all_requested() is True


def test_replace_files_dialog_renders_items_and_confirms(qtbot) -> None:
    """Verify replace-all dialog renders file rows and confirm state."""
    dialog = ReplaceFilesDialog([("one.txt", 3), "two.txt"], "locale")
    qtbot.addWidget(dialog)

    assert dialog.confirmed() is False
    dialog._confirm()
    assert dialog.confirmed() is True


def test_conflict_choice_dialog_close_guard_and_choice(qtbot) -> None:
    """Verify conflict dialog blocks close without explicit choice."""
    dialog = ConflictChoiceDialog("ui.txt", 2)
    qtbot.addWidget(dialog)

    class _Event:
        """Minimal close event stub with ignore tracking."""

        def __init__(self) -> None:
            self.ignored = False

        def ignore(self) -> None:
            """Mark event as ignored."""
            self.ignored = True

    event = _Event()
    dialog.closeEvent(event)
    assert event.ignored is True

    dialog.reject()
    assert dialog.choice() is None

    dialog._set_choice("merge")
    assert dialog.choice() == "merge"


def test_about_dialog_falls_back_when_license_read_fails(qtbot, monkeypatch) -> None:
    """Verify About dialog shows fallback text when license file read fails."""

    def _raise_read_text(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise OSError("read failed")

    monkeypatch.setattr(Path, "read_text", _raise_read_text)
    dialog = AboutDialog()
    qtbot.addWidget(dialog)

    assert dialog._license_text.toPlainText() == "License text not available."
