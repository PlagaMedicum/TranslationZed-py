import pytest

pytest.importorskip("PySide6")

from translationzed_py.gui import MainWindow


def test_no_locale_selected_aborts(tmp_path):
    root = tmp_path / "proj"
    (root / "EN").mkdir(parents=True)
    (root / "EN" / "language.txt").write_text("text = English\ncharset = UTF-8\n")
    (root / "EN" / "ui.txt").write_text('UI_OK = "OK"\n')
    (root / "BE").mkdir()
    (root / "BE" / "language.txt").write_text("text = Belarusian\ncharset = UTF-8\n")
    (root / "BE" / "ui.txt").write_text('UI_OK = "OK"\n')

    win = MainWindow(str(root), selected_locales=[])
    assert getattr(win, "_startup_aborted", False) is True
