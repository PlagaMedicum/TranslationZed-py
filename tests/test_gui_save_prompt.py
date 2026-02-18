"""Test module for gui save prompt."""

from dataclasses import replace
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from translationzed_py.core import parse
from translationzed_py.core.status_cache import read as read_cache
from translationzed_py.core.status_cache import write as write_cache
from translationzed_py.gui import MainWindow
from translationzed_py.gui import main_window as mw


def _make_project(tmp_path: Path) -> tuple[Path, Path, Path]:
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
    ui_path = root / "BE" / "ui.txt"
    ui_path.write_text('UI_YES = "Так"\n', encoding="utf-8")
    menu_path = root / "BE" / "menu.txt"
    menu_path.write_text('UI_MENU = "Меню"\n', encoding="utf-8")
    return root, ui_path, menu_path


def _edit_value(win: MainWindow, path: Path) -> None:
    ix = win.fs_model.index_for_path(path)
    win._file_chosen(ix)
    model = win.table.model()
    model.setData(model.index(0, 2), "Да")


def _cache_draft_value(root: Path, path: Path, value: str) -> None:
    pf = parse(path, encoding="utf-8")
    first = pf.entries[0]
    changed = replace(first, value=value)
    write_cache(root, path, [changed], changed_keys={first.key})


def test_prompt_cache_only_keeps_original(tmp_path, qtbot, monkeypatch):
    """Verify prompt cache only keeps original."""
    root, path, _menu = _make_project(tmp_path)
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
    """Verify prompt write updates original."""
    root, path, _menu = _make_project(tmp_path)
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


def test_prompt_write_can_deselect_files(tmp_path, qtbot, monkeypatch):
    """Verify prompt write can deselect files."""
    root, ui_path, menu_path = _make_project(tmp_path)
    _cache_draft_value(root, menu_path, "Супер меню")

    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    _edit_value(win, ui_path)

    captured_files: list[str] = []
    selected_rel = menu_path.relative_to(root).as_posix()

    class FakeDialog:
        def __init__(self, files, *_args, **_kwargs):
            nonlocal captured_files
            captured_files = list(files)
            self._choice = "write"

        def exec(self):
            return None

        def choice(self):
            return self._choice

        def selected_files(self):
            return [selected_rel]

    monkeypatch.setattr(mw, "SaveFilesDialog", FakeDialog)
    win._request_write_original()

    assert ui_path.relative_to(root).as_posix() in captured_files
    assert selected_rel in captured_files
    assert ui_path.read_text(encoding="utf-8") == 'UI_YES = "Так"\n'
    assert menu_path.read_text(encoding="utf-8") == 'UI_MENU = "Супер меню"\n'


def test_prompt_write_is_blocked_during_open_flow(tmp_path, qtbot, monkeypatch):
    """Verify prompt write is blocked during open flow."""
    root, path, _menu = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    _edit_value(win, path)
    win._open_flow_depth = 1

    class FakeDialog:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError(
                "SaveFilesDialog should not open while read-flow guard is active"
            )

    monkeypatch.setattr(mw, "SaveFilesDialog", FakeDialog)
    win._request_write_original()
    assert path.read_text(encoding="utf-8") == 'UI_YES = "Так"\n'
