from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from translationzed_py.core.status_cache import read as read_cache
from translationzed_py.gui import MainWindow
from translationzed_py.gui import main_window as mw


def _make_project(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "proj"
    (root / "EN").mkdir(parents=True)
    (root / "BE").mkdir(parents=True)
    (root / "EN" / "language.txt").write_text(
        "text = English,\ncharset = UTF-8,\n", encoding="utf-8"
    )
    (root / "BE" / "language.txt").write_text(
        "text = Belarusian,\ncharset = UTF-8,\n", encoding="utf-8"
    )
    (root / "EN" / "ui.txt").write_text('UI_YES = "Yes"\n', encoding="utf-8")
    path = root / "BE" / "ui.txt"
    path.write_text('UI_YES = "Так"\n', encoding="utf-8")
    return root, path


def _edit_value(win: MainWindow, path: Path) -> None:
    ix = win.fs_model.index_for_path(path)
    win._file_chosen(ix)
    model = win.table.model()
    model.setData(model.index(0, 2), "Да")


def test_prompt_cache_only_keeps_original(tmp_path, qtbot, monkeypatch):
    root, path = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    _edit_value(win, path)

    class FakeDialog:
        def __init__(self, *_args, **_kwargs):
            self._choice = "cache"

        def exec(self):
            return None

        def choice(self):
            return self._choice

    monkeypatch.setattr(mw, "SaveFilesDialog", FakeDialog)
    win._request_write_original()
    assert path.read_text(encoding="utf-8") == 'UI_YES = "Так"\n'
    cached = read_cache(root, path)
    assert any(entry.value == "Да" for entry in cached.values())


def test_prompt_write_updates_original(tmp_path, qtbot, monkeypatch):
    root, path = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    _edit_value(win, path)

    class FakeDialog:
        def __init__(self, *_args, **_kwargs):
            self._choice = "write"

        def exec(self):
            return None

        def choice(self):
            return self._choice

    monkeypatch.setattr(mw, "SaveFilesDialog", FakeDialog)
    win._request_write_original()
    assert path.read_text(encoding="utf-8") == 'UI_YES = "Да"\n'
    cached = read_cache(root, path)
    if cached:
        assert all(entry.value is None for entry in cached.values())
