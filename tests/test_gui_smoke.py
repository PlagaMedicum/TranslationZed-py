from pathlib import Path
from translationzed_py.gui import MainWindow, get_app

def test_table_fills(qtbot, tmp_path: Path):
    # copy fixture
    src = Path(__file__).parent / "fixtures" / "simple"
    dst = tmp_path / "proj"; dst.mkdir()
    for loc in ("EN", "BE"):
        (dst / loc).mkdir()
        (dst / loc / "ui.txt").write_text('UI_YES = "Yes"\n')
    win = MainWindow(str(dst))
    qtbot.addWidget(win)
    # select EN/ui.txt
    ix = win.fs_model.index(str(dst / "EN" / "ui.txt"))
    win._on_file_selected(ix)
    assert win.table.model().rowCount() == 1
