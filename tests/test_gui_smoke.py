from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from translationzed_py.gui import MainWindow


def test_table_fills(qtbot, tmp_path: Path):
    # copy fixture
    dst = tmp_path / "proj"
    dst.mkdir()
    for loc in ("EN", "BE"):
        (dst / loc).mkdir()
        (dst / loc / "ui.txt").write_text('UI_YES = "Yes"\n')
    win = MainWindow(str(dst), selected_locales=["BE"])
    qtbot.addWidget(win)
    # select BE/ui.txt
    ix = win.fs_model.index_for_path(dst / "BE" / "ui.txt")
    win._file_chosen(ix)
    assert win.table.model().rowCount() == 1
