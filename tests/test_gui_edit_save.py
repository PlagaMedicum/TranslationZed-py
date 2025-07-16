from translationzed_py.gui import MainWindow


def test_edit_and_save(qtbot, tmp_path):
    # copy fixture
    dst = tmp_path / "proj"
    dst.mkdir()
    for loc in ("EN", "BE"):
        (dst / loc).mkdir()
        (dst / loc / "ui.txt").write_text('UI_YES = "Yes"\n')
    win = MainWindow(str(dst))
    qtbot.addWidget(win)
    # select EN/ui.txt
    ix = win.fs_model.index_for_path(dst / "EN" / "ui.txt")
    win._file_chosen(ix)
    assert win.table.model().rowCount() == 1
    win = MainWindow(str(dst))
    qtbot.addWidget(win)
    ix = win.fs_model.index_for_path(dst / "EN" / "ui.txt")
    win._file_chosen(ix)

    model = win.table.model()
    model.setData(model.index(0, 1), "Yes-edited")  # edit the value

    win._save_current()
    assert (dst / "EN" / "ui.txt").read_text().endswith('"Yes-edited"\n')
