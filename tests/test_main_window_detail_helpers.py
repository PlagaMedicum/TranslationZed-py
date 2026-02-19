"""Test module for main-window detail editor helper branches."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt

from translationzed_py.gui import MainWindow
from translationzed_py.gui import main_window as mw


def _make_project(tmp_path: Path) -> Path:
    """Create a minimal two-locale project for detail-editor tests."""
    root = tmp_path / "proj"
    root.mkdir()
    for locale, text in (
        ("EN", "English"),
        ("BE", "Belarusian"),
    ):
        (root / locale).mkdir()
        (root / locale / "language.txt").write_text(
            f"text = {text},\ncharset = UTF-8,\n",
            encoding="utf-8",
        )
    (root / "EN" / "ui.txt").write_text('UI_OK = "OK"\n', encoding="utf-8")
    (root / "BE" / "ui.txt").write_text('UI_OK = "Добра"\n', encoding="utf-8")
    return root


def _open_window_with_current_file(qtbot, tmp_path: Path) -> tuple[MainWindow, Path]:
    """Return an initialized main window with the current file selected."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    win.show()
    index = win.fs_model.index_for_path(root / "BE" / "ui.txt")
    win._file_chosen(index)
    win._detail_panel.setVisible(True)
    model = win.table.model()
    assert model is not None
    win.table.setCurrentIndex(model.index(0, 2))
    return win, root


def test_load_pending_detail_text_covers_guards_and_success(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    """Verify pending-detail loader handles guard clauses and normal load."""
    win, _root = _open_window_with_current_file(qtbot, tmp_path)
    assert win._current_model is not None
    model = win.table.model()
    assert model is not None

    win._detail_source.setPlainText("source-sentinel")
    win._detail_translation.setPlainText("value-sentinel")
    win._detail_pending_row = None
    win._detail_pending_active = False
    win._load_pending_detail_text()
    assert win._detail_source.toPlainText() == "source-sentinel"
    assert win._detail_translation.toPlainText() == "value-sentinel"

    win._detail_pending_row = 0
    win._detail_pending_active = True

    win._detail_panel.setVisible(False)
    win._load_pending_detail_text()
    assert win._detail_pending_row == 0
    assert win._detail_pending_active is True

    win._detail_panel.setVisible(True)
    saved_model = win._current_model
    win._current_model = None
    win._load_pending_detail_text()
    assert win._detail_pending_row == 0
    assert win._detail_pending_active is True
    win._current_model = saved_model

    monkeypatch.setattr(win.table, "currentIndex", lambda: model.index(-1, -1))
    win._load_pending_detail_text()
    assert win._detail_pending_row == 0
    assert win._detail_pending_active is True

    monkeypatch.setattr(win.table, "currentIndex", lambda: model.index(0, 2))
    win.table.setCurrentIndex(model.index(0, 2))
    expected_source = str(win._current_model.index(0, 1).data(Qt.EditRole) or "")
    expected_value = str(win._current_model.index(0, 2).data(Qt.EditRole) or "")
    win._detail_translation.setReadOnly(True)
    win._detail_source.setPlaceholderText("pending-source")
    win._detail_translation.setPlaceholderText("pending-value")
    win._detail_source.setPlainText("")
    win._detail_translation.setPlainText("")
    win._load_pending_detail_text()

    assert win._detail_source.toPlainText() == expected_source
    assert win._detail_translation.toPlainText() == expected_value
    assert win._detail_translation.isReadOnly() is False
    assert win._detail_source.placeholderText() == ""
    assert win._detail_translation.placeholderText() == ""
    assert win._detail_pending_row is None
    assert win._detail_pending_active is False
    assert win._detail_dirty is False


def test_set_detail_pending_covers_model_and_no_model_paths(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    """Verify set-detail-pending captures lengths, placeholders, and focus trigger."""
    win, _root = _open_window_with_current_file(qtbot, tmp_path)

    char_calls: list[tuple[int | None, int | None]] = []
    load_calls: list[str] = []
    monkeypatch.setattr(win, "_set_detail_char_counts", lambda s, t: char_calls.append((s, t)))
    monkeypatch.setattr(win, "_load_pending_detail_text", lambda: load_calls.append("load"))
    monkeypatch.setattr(win._detail_source, "hasFocus", lambda: False, raising=False)
    monkeypatch.setattr(win._detail_translation, "hasFocus", lambda: False, raising=False)

    win._set_detail_pending(0)
    assert win._detail_pending_row == 0
    assert win._detail_pending_active is True
    assert win._detail_syncing is False
    assert win._detail_dirty is False
    assert win._detail_translation.isReadOnly() is True
    assert win._detail_source.placeholderText() == "Large text. Click to load full source."
    assert (
        win._detail_translation.placeholderText()
        == "Large text. Click to load full translation."
    )
    assert win._detail_source.toPlainText() == ""
    assert win._detail_translation.toPlainText() == ""
    assert load_calls == []
    assert char_calls[-1][0] is not None
    assert char_calls[-1][1] is not None

    monkeypatch.setattr(win._detail_source, "hasFocus", lambda: True, raising=False)
    win._set_detail_pending(0)
    assert load_calls == ["load"]

    win._current_model = None
    monkeypatch.setattr(win._detail_source, "hasFocus", lambda: False, raising=False)
    monkeypatch.setattr(win._detail_translation, "hasFocus", lambda: False, raising=False)
    win._set_detail_pending(0)
    assert char_calls[-1] == (None, None)


def test_commit_detail_translation_covers_pending_and_invalid_index_paths(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    """Verify commit-detail exits for pending rows and clears dirty on invalid index."""
    win, _root = _open_window_with_current_file(qtbot, tmp_path)
    assert win._current_model is not None

    win._detail_dirty = True
    win._detail_pending_row = 0
    win._commit_detail_translation()
    assert win._detail_dirty is True

    model = win.table.model()
    assert model is not None
    win._detail_pending_row = None
    win._detail_dirty = True
    monkeypatch.setattr(win.table, "currentIndex", lambda: model.index(-1, -1))
    win._commit_detail_translation()
    assert win._detail_dirty is False


def test_sync_detail_editors_uses_pending_mode_for_large_rows(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    """Verify sync-detail delegates to pending-mode when lazy threshold is reached."""
    win, _root = _open_window_with_current_file(qtbot, tmp_path)
    assert win._current_model is not None
    win._large_text_optimizations = True

    pending_calls: list[int] = []
    monkeypatch.setattr(mw, "_DETAIL_LAZY_THRESHOLD", 1)
    monkeypatch.setattr(win, "_set_detail_pending", lambda row: pending_calls.append(row))

    win._sync_detail_editors()
    assert pending_calls == [0]
