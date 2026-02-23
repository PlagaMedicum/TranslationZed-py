"""Tests for status-bar translation/proofread progress indicators."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt

from translationzed_py.core.model import Status
from translationzed_py.gui import MainWindow


def _make_project(root: Path) -> None:
    for locale in ("EN", "BE"):
        (root / locale).mkdir()
        (root / locale / "language.txt").write_text(
            f"text = {locale},\ncharset = UTF-8,\n",
            encoding="utf-8",
        )
    (root / "EN" / "a.txt").write_text('A1 = "One"\nA2 = "Two"\n', encoding="utf-8")
    (root / "EN" / "b.txt").write_text(
        'B1 = "Three"\nB2 = "Four"\n', encoding="utf-8"
    )
    (root / "BE" / "a.txt").write_text(
        'A1 = "Adzin"\nA2 = "Dva"\n', encoding="utf-8"
    )
    (root / "BE" / "b.txt").write_text(
        'B1 = "Try"\nB2 = "Chatyry"\n', encoding="utf-8"
    )


def test_status_bar_shows_file_and_locale_progress(qtbot, tmp_path: Path) -> None:
    """Verify status bar shows current-file and locale translation/proofread progress."""
    root = tmp_path / "proj"
    root.mkdir()
    _make_project(root)

    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    ix_a = win.fs_model.index_for_path(root / "BE" / "a.txt")
    win._file_chosen(ix_a)
    model_a = win.table.model()
    assert model_a is not None
    assert model_a.setData(model_a.index(0, 3), Status.TRANSLATED, Qt.EditRole)
    assert model_a.setData(model_a.index(1, 3), Status.PROOFREAD, Qt.EditRole)
    assert win._write_cache_current() is True

    ix_b = win.fs_model.index_for_path(root / "BE" / "b.txt")
    win._file_chosen(ix_b)
    win._update_status_bar()
    message = win.statusBar().currentMessage()
    assert "Progress File T:0% P:0%" in message
    assert "Locale T:50% P:25%" in message


def test_status_bar_progress_updates_live_for_current_file(
    qtbot, tmp_path: Path
) -> None:
    """Verify progress percentages update when status changes in current file."""
    root = tmp_path / "proj"
    root.mkdir()
    _make_project(root)

    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    ix_a = win.fs_model.index_for_path(root / "BE" / "a.txt")
    win._file_chosen(ix_a)
    model_a = win.table.model()
    assert model_a is not None
    assert model_a.setData(model_a.index(0, 3), Status.TRANSLATED, Qt.EditRole)
    assert model_a.setData(model_a.index(1, 3), Status.PROOFREAD, Qt.EditRole)
    assert win._write_cache_current() is True

    ix_b = win.fs_model.index_for_path(root / "BE" / "b.txt")
    win._file_chosen(ix_b)
    model_b = win.table.model()
    assert model_b is not None
    assert model_b.setData(model_b.index(0, 3), Status.TRANSLATED, Qt.EditRole)
    win._update_status_bar()

    message = win.statusBar().currentMessage()
    assert "Progress File T:50% P:0%" in message
    assert "Locale T:75% P:25%" in message
