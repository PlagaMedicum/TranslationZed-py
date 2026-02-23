"""Integration-oriented GUI tests for EN diff markers and NEW-row insertion flow."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt

from translationzed_py.gui import MainWindow
from translationzed_py.gui import main_window as mw


@pytest.fixture(autouse=True)
def _disable_en_hash_prompt(monkeypatch):
    monkeypatch.setattr(mw.MainWindow, "_check_en_hash_cache", lambda _self: True)
    monkeypatch.setattr(mw, "_connect_system_theme_sync", lambda _callback: False)


def _make_project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    for locale in ("EN", "BE"):
        (root / locale).mkdir()
        (root / locale / "language.txt").write_text(
            f"text = {locale},\ncharset = UTF-8,\n",
            encoding="utf-8",
        )
    (root / "EN" / "ui.txt").write_text(
        'A = "Source A"\nB = "Source B"\n',
        encoding="utf-8",
    )
    (root / "BE" / "ui.txt").write_text('A = "Target A"\n', encoding="utf-8")
    return root


def _find_row_by_key(win: MainWindow, key: str) -> int:
    model = win.table.model()
    assert model is not None
    for row in range(model.rowCount()):
        if model.data(model.index(row, 0), Qt.EditRole) == key:
            return row
    return -1


def test_file_open_adds_virtual_new_rows_and_badges(qtbot, tmp_path) -> None:
    """Verify file-open renders NEW virtual rows and EN-diff key badges."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    win._prompt_write_on_exit = False
    qtbot.addWidget(win)
    ix = win.fs_model.index_for_path(root / "BE" / "ui.txt")
    win._file_chosen(ix)

    model = win.table.model()
    assert model is not None
    assert model.rowCount() == 2
    row_b = _find_row_by_key(win, "B")
    assert row_b >= 0
    assert model.data(model.index(row_b, 0), Qt.DisplayRole) == "[NEW] B"
    assert model.data(model.index(row_b, 1), Qt.EditRole) == "Source B"


def test_save_current_skip_keeps_new_drafts_pending(
    qtbot, tmp_path, monkeypatch
) -> None:
    """Verify save-skip keeps NEW row drafts pending without insertion."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    win._prompt_write_on_exit = False
    qtbot.addWidget(win)
    ix = win.fs_model.index_for_path(root / "BE" / "ui.txt")
    win._file_chosen(ix)

    model = win.table.model()
    assert model is not None
    row_b = _find_row_by_key(win, "B")
    assert row_b >= 0
    assert model.setData(model.index(row_b, 2), "Draft B", Qt.EditRole) is True
    monkeypatch.setattr(
        win,
        "_prompt_new_row_insertion_action",
        lambda **_kwargs: ("skip", None),
    )

    assert win._save_current() is True
    assert (root / "BE" / "ui.txt").read_text(encoding="utf-8") == 'A = "Target A"\n'
    assert win._current_model is not None
    assert win._current_model.has_pending_virtual_new_values() is True
    assert win._en_new_drafts_by_file[root / "BE" / "ui.txt"]["B"] == "Draft B"


def test_save_current_apply_inserts_edited_new_rows(
    qtbot, tmp_path, monkeypatch
) -> None:
    """Verify save-apply inserts edited NEW rows into locale file content."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    win._prompt_write_on_exit = False
    qtbot.addWidget(win)
    ix = win.fs_model.index_for_path(root / "BE" / "ui.txt")
    win._file_chosen(ix)

    model = win.table.model()
    assert model is not None
    row_b = _find_row_by_key(win, "B")
    assert row_b >= 0
    assert model.setData(model.index(row_b, 2), "Draft B", Qt.EditRole) is True
    monkeypatch.setattr(
        win,
        "_prompt_new_row_insertion_action",
        lambda **_kwargs: ("apply", None),
    )

    assert win._save_current() is True
    text = (root / "BE" / "ui.txt").read_text(encoding="utf-8")
    assert 'A = "Target A"' in text
    assert 'B = "Draft B"' in text
    assert win._en_new_drafts_by_file.get(root / "BE" / "ui.txt") is None
