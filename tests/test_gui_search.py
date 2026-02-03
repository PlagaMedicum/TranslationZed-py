from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt

from translationzed_py.gui import MainWindow


def test_search_selects_first_match(qtbot, tmp_path: Path):
    dst = tmp_path / "proj"
    dst.mkdir()
    for loc in ("EN", "BE"):
        (dst / loc).mkdir()
        (dst / loc / "language.txt").write_text(
            f"text = {loc},\ncharset = UTF-8,\n", encoding="utf-8"
        )
    (dst / "EN" / "ui.txt").write_text('UI_ALPHA = "Alpha"\nUI_BETA = "Beta"\n')
    (dst / "BE" / "ui.txt").write_text('UI_ALPHA = "Alfa"\nUI_BETA = "Beto"\n')
    win = MainWindow(str(dst), selected_locales=["BE"])
    qtbot.addWidget(win)
    ix = win.fs_model.index_for_path(dst / "BE" / "ui.txt")
    win._file_chosen(ix)
    win.search_edit.setText("beto")
    win._trigger_search()
    qtbot.waitUntil(lambda: len(win._search_matches) == 1, timeout=1000)
    current = win.table.currentIndex()
    assert current.isValid()
    assert current.row() == 1


def test_search_moves_to_other_file(qtbot, tmp_path: Path):
    dst = tmp_path / "proj"
    dst.mkdir()
    for loc in ("EN", "BE"):
        (dst / loc).mkdir()
        (dst / loc / "language.txt").write_text(
            f"text = {loc},\ncharset = UTF-8,\n", encoding="utf-8"
        )
    (dst / "BE" / "first.txt").write_text('UI_FIRST = "One"\n')
    (dst / "BE" / "second.txt").write_text('UI_SECOND = "Two"\n')
    win = MainWindow(str(dst), selected_locales=["BE"])
    qtbot.addWidget(win)
    ix = win.fs_model.index_for_path(dst / "BE" / "first.txt")
    win._file_chosen(ix)
    win._search_scope = "POOL"
    win.search_edit.setText("Two")
    win._trigger_search()
    qtbot.waitUntil(lambda: bool(win._search_matches), timeout=1000)
    win._search_next()
    qtbot.waitUntil(
        lambda: win._current_pf and win._current_pf.path == dst / "BE" / "second.txt",
        timeout=1000,
    )
    tree_path = win.tree.currentIndex().data(Qt.UserRole)
    assert tree_path == str(dst / "BE" / "second.txt")
    current = win.table.currentIndex()
    assert current.isValid()
    assert current.row() == 0
