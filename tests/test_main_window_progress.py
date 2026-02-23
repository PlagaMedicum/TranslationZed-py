"""Tests for sidebar/tree progress indicators and progress semantics."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt

from translationzed_py.core.model import Status
from translationzed_py.gui import MainWindow
from translationzed_py.gui.fs_model import TREE_PROGRESS_COUNTS_ROLE


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


def test_progress_strip_and_tree_payloads_update_for_file_and_locale(
    qtbot, tmp_path: Path
) -> None:
    """Verify progress strip/tree payloads reflect file + locale status distribution."""
    root = tmp_path / "proj"
    root.mkdir()
    _make_project(root)

    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    win._post_locale_timer.stop()

    ix_a = win.fs_model.index_for_path(root / "BE" / "a.txt")
    win._file_chosen(ix_a)
    model_a = win.table.model()
    assert model_a is not None
    assert model_a.setData(model_a.index(0, 3), Status.TRANSLATED, Qt.EditRole)
    assert model_a.setData(model_a.index(1, 3), Status.PROOFREAD, Qt.EditRole)
    assert win._write_cache_current() is True

    ix_b = win.fs_model.index_for_path(root / "BE" / "b.txt")
    win._file_chosen(ix_b)
    assert win._current_pf is not None
    assert win._current_pf.path == root / "BE" / "b.txt"
    current_model = win.table.model()
    assert current_model is not None
    assert current_model.canonical_status_counts() == (2, 0, 0, 0)
    win._refresh_progress_ui()
    qtbot.waitUntil(
        lambda: "BE" in getattr(win, "_progress_locale_progress_cache", {}),
        timeout=3000,
    )

    assert win._progress_file_row.percent_label.text() == "T:0% P:0%"
    assert win._progress_locale_row.percent_label.text() == "T:25% P:25%"

    locale_index = win.fs_model.index(0, 0)
    locale_counts = locale_index.data(TREE_PROGRESS_COUNTS_ROLE)
    assert locale_counts == (2, 0, 1, 1)
    file_counts = ix_b.data(TREE_PROGRESS_COUNTS_ROLE)
    assert file_counts == (2, 0, 0, 0)


def test_progress_uses_canonical_counts_under_filter_and_sort(
    qtbot, tmp_path: Path
) -> None:
    """Verify progress ignores view filter/sort and uses canonical status counts."""
    root = tmp_path / "proj"
    root.mkdir()
    _make_project(root)

    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    win._post_locale_timer.stop()

    ix_a = win.fs_model.index_for_path(root / "BE" / "a.txt")
    win._file_chosen(ix_a)
    model = win.table.model()
    assert model is not None

    assert model.setData(model.index(0, 3), Status.TRANSLATED, Qt.EditRole)
    assert model.setData(model.index(1, 3), Status.PROOFREAD, Qt.EditRole)
    model.set_status_filter({Status.UNTOUCHED})
    model.set_status_sort_enabled(True)
    win._refresh_progress_ui()

    assert win._progress_file_row.percent_label.text() == "T:50% P:50%"


def test_status_bar_and_empty_state_defaults(qtbot, tmp_path: Path) -> None:
    """Verify no-file-open placeholder and default status text contract."""
    root = tmp_path / "proj"
    root.mkdir()
    _make_project(root)

    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    win._post_locale_timer.stop()

    assert win._right_stack.currentWidget() is win._empty_table_placeholder
    assert win.statusBar().currentMessage() == "Ready to edit"

    ix_a = win.fs_model.index_for_path(root / "BE" / "a.txt")
    win._file_chosen(ix_a)
    assert win._right_stack.currentWidget() is win._table_container
