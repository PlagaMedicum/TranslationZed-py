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
    qtbot.waitUntil(
        lambda: (
            win.table.currentIndex().isValid() and win.table.currentIndex().row() == 1
        ),
        timeout=1000,
    )


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


def test_search_pool_cycles_all_files_before_repeating(qtbot, tmp_path: Path):
    dst = tmp_path / "proj"
    dst.mkdir()
    for loc in ("EN", "BE"):
        (dst / loc).mkdir()
        (dst / loc / "language.txt").write_text(
            f"text = {loc},\ncharset = UTF-8,\n", encoding="utf-8"
        )
    for name in ("a.txt", "b.txt", "c.txt"):
        (dst / "BE" / name).write_text(f'UI_KEY = "Needle {name}"\n')
    win = MainWindow(str(dst), selected_locales=["BE"])
    qtbot.addWidget(win)
    ix = win.fs_model.index_for_path(dst / "BE" / "b.txt")
    win._file_chosen(ix)
    model = win.table.model()
    assert model is not None
    win.table.setCurrentIndex(model.index(0, 2))
    win._search_scope = "POOL"
    win.search_edit.setText("Needle")

    win._search_next()
    qtbot.waitUntil(
        lambda: win._current_pf and win._current_pf.path == dst / "BE" / "c.txt",
        timeout=1000,
    )
    win._search_next()
    qtbot.waitUntil(
        lambda: win._current_pf and win._current_pf.path == dst / "BE" / "a.txt",
        timeout=1000,
    )
    win._search_next()
    qtbot.waitUntil(
        lambda: win._current_pf and win._current_pf.path == dst / "BE" / "b.txt",
        timeout=1000,
    )


def test_search_case_toggle_controls_literal_matching(qtbot, tmp_path: Path):
    dst = tmp_path / "proj"
    dst.mkdir()
    for loc in ("EN", "BE"):
        (dst / loc).mkdir()
        (dst / loc / "language.txt").write_text(
            f"text = {loc},\ncharset = UTF-8,\n", encoding="utf-8"
        )
    (dst / "BE" / "ui.txt").write_text('UI_KEY = "Alpha"\n')
    win = MainWindow(str(dst), selected_locales=["BE"])
    qtbot.addWidget(win)
    ix = win.fs_model.index_for_path(dst / "BE" / "ui.txt")
    win._file_chosen(ix)
    win.search_mode.setCurrentIndex(2)
    win.search_edit.setText("alpha")

    win.search_case_btn.setChecked(True)
    assert win._search_from_anchor(direction=1, anchor_row=-1, wrap=False) is False

    win.search_case_btn.setChecked(False)
    assert win._search_from_anchor(direction=1, anchor_row=-1, wrap=False) is True


def test_search_side_panel_lists_results_and_navigates(qtbot, tmp_path: Path):
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
    ix_first = win.fs_model.index_for_path(dst / "BE" / "first.txt")
    ix_second = win.fs_model.index_for_path(dst / "BE" / "second.txt")
    win._file_chosen(ix_first)
    win._search_scope = "POOL"
    win.search_edit.setText("Two")
    win._trigger_search()

    qtbot.waitUntil(lambda: win._search_results_list.count() == 1, timeout=1000)
    item = win._search_results_list.item(0)
    assert item is not None
    assert "second.txt:1" in item.text()

    win._file_chosen(ix_first)
    win._open_search_result_item(item)
    qtbot.waitUntil(
        lambda: win._current_pf and win._current_pf.path == dst / "BE" / "second.txt",
        timeout=1000,
    )
    tree_path = win.tree.currentIndex().data(Qt.UserRole)
    assert tree_path == str(dst / "BE" / "second.txt")
    assert ix_second.isValid()
