from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from translationzed_py.gui import MainWindow


def _make_project(tmp_path: Path, locale: str, encoding: str, value: str) -> Path:
    root = tmp_path / "proj"
    (root / "EN").mkdir(parents=True)
    (root / locale).mkdir(parents=True)
    (root / "EN" / "language.txt").write_text(
        "text = English,\ncharset = UTF-8,\n", encoding="utf-8"
    )
    (root / locale / "language.txt").write_text(
        f"text = {locale},\ncharset = {encoding},\n", encoding="utf-8"
    )
    (root / "EN" / "ui.txt").write_text('UI_OK = "OK"\n', encoding="utf-8")
    path = root / locale / "ui.txt"
    path.write_text(f'UI_OK = "{value}"\n', encoding=encoding)
    return root


def test_gui_save_preserves_cp1251(tmp_path, qtbot):
    root = _make_project(tmp_path, "RU", "CP1251", "Тест")
    path = root / "RU" / "ui.txt"
    win = MainWindow(str(root), selected_locales=["RU"])
    qtbot.addWidget(win)
    ix = win.fs_model.index_for_path(path)
    win._file_chosen(ix)
    model = win.table.model()
    model.setData(model.index(0, 2), "Привет")
    win._save_current()
    data = path.read_bytes()
    assert data[:2] != b"\xff\xfe"
    assert data.decode("cp1251").replace("\r\n", "\n") == 'UI_OK = "Привет"\n'


def test_gui_save_preserves_utf16(tmp_path, qtbot):
    root = _make_project(tmp_path, "KO", "UTF-16", "테스트")
    path = root / "KO" / "ui.txt"
    win = MainWindow(str(root), selected_locales=["KO"])
    qtbot.addWidget(win)
    ix = win.fs_model.index_for_path(path)
    win._file_chosen(ix)
    model = win.table.model()
    model.setData(model.index(0, 2), "테스트2")
    win._save_current()
    data = path.read_bytes()
    assert data[:2] in {b"\xff\xfe", b"\xfe\xff"}
    assert data.decode("utf-16").replace("\r\n", "\n") == 'UI_OK = "테스트2"\n'
