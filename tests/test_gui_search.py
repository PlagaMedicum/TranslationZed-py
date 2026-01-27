from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from translationzed_py.gui import MainWindow


def test_search_selects_first_match(qtbot, tmp_path: Path):
    dst = tmp_path / "proj"
    dst.mkdir()
    for loc in ("EN", "BE"):
        (dst / loc).mkdir()
    (dst / "EN" / "ui.txt").write_text('UI_ALPHA = "Alpha"\nUI_BETA = "Beta"\n')
    (dst / "BE" / "ui.txt").write_text('UI_ALPHA = "Alfa"\nUI_BETA = "Beto"\n')
    win = MainWindow(str(dst), selected_locales=["BE"])
    qtbot.addWidget(win)
    ix = win.fs_model.index_for_path(dst / "BE" / "ui.txt")
    win._file_chosen(ix)
    win.search_edit.setText("beta")
    qtbot.waitUntil(lambda: len(win._search_matches) == 1, timeout=1000)
    current = win.table.currentIndex()
    assert current.isValid()
    assert current.row() == 1
