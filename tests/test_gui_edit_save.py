"""Test module for gui edit save."""

import pytest

pytest.importorskip("PySide6")

from translationzed_py.gui import MainWindow


def test_edit_and_save(qtbot, tmp_path):
    # copy fixture
    """Verify edit and save."""
    dst = tmp_path / "proj"
    dst.mkdir()
    for loc in ("EN", "BE"):
        (dst / loc).mkdir()
        (dst / loc / "language.txt").write_text(
            f"text = {loc},\ncharset = UTF-8,\n", encoding="utf-8"
        )
        (dst / loc / "ui.txt").write_text('UI_YES = "Yes"\n')
    win = MainWindow(str(dst), selected_locales=["BE"])
    qtbot.addWidget(win)
    # select BE/ui.txt
    ix = win.fs_model.index_for_path(dst / "BE" / "ui.txt")
    win._file_chosen(ix)
    assert win.table.model().rowCount() == 1
    win = MainWindow(str(dst), selected_locales=["BE"])
    qtbot.addWidget(win)
    ix = win.fs_model.index_for_path(dst / "BE" / "ui.txt")
    win._file_chosen(ix)

    model = win.table.model()
    model.setData(model.index(0, 2), "Yes-edited")  # edit the value

    win._save_current()
    assert (dst / "BE" / "ui.txt").read_text() == 'UI_YES = "Yes-edited"\n'
