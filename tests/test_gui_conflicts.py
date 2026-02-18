"""Test module for gui conflicts."""

from pathlib import Path

import pytest
import xxhash

pytest.importorskip("PySide6")

from translationzed_py.core.model import Entry, Status
from translationzed_py.core.parser import parse
from translationzed_py.core.status_cache import read as read_cache
from translationzed_py.core.status_cache import write
from translationzed_py.gui import MainWindow
from translationzed_py.gui import main_window as mw


def _hash_key(key: str) -> int:
    return int(xxhash.xxh64(key.encode("utf-8")).intdigest()) & 0xFFFFFFFFFFFFFFFF


def _make_conflict_project(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "proj"
    (root / "EN").mkdir(parents=True)
    (root / "BE").mkdir(parents=True)
    (root / "EN" / "language.txt").write_text(
        "text = English,\ncharset = UTF-8,\n", encoding="utf-8"
    )
    (root / "BE" / "language.txt").write_text(
        "text = Belarusian,\ncharset = UTF-8,\n", encoding="utf-8"
    )
    (root / "EN" / "ui.txt").write_text(
        'HELLO = "Hello"\nBYE = "Bye"\n',
        encoding="utf-8",
    )

    # Current file values differ from cached originals to force conflicts.
    path = root / "BE" / "ui.txt"
    path.write_text(
        'HELLO = "Привет!!"\nBYE = "Пока..."\n',
        encoding="utf-8",
    )

    pf = parse(path, encoding="utf-8")
    entries: list[Entry] = []
    for e in pf.entries:
        if e.key == "HELLO":
            value = "Здравствуйте"
            status = Status.FOR_REVIEW
        elif e.key == "BYE":
            value = "До свидания"
            status = Status.TRANSLATED
        else:
            value = e.value
            status = e.status
        entries.append(Entry(e.key, value, status, e.span, e.segments, e.gaps, e.raw))

    write(
        root,
        path,
        entries,
        changed_keys={"HELLO", "BYE"},
        original_values={"HELLO": "Привет", "BYE": "Пока"},
    )
    return root, path


def test_conflict_drop_cache(tmp_path, qtbot, monkeypatch):
    """Verify conflict drop cache."""
    root, path = _make_conflict_project(tmp_path)

    class FakeDialog:
        def __init__(self, *_args, **_kwargs):
            self._choice = "drop_cache"

        def exec(self):
            return None

        def choice(self):
            return self._choice

    monkeypatch.setattr(mw, "ConflictChoiceDialog", FakeDialog)

    win = MainWindow(str(root), selected_locales=["BE"])
    win._prompt_write_on_exit = False
    qtbot.addWidget(win)
    ix = win.fs_model.index_for_path(path)
    win._conflict_notified.add(path)
    win._file_chosen(ix)
    assert win._has_conflicts(path)

    win._prompt_conflicts(path)
    cache = read_cache(root, path)
    hello = cache[_hash_key("HELLO")]
    assert hello.value is None
    assert hello.original is None


def test_conflict_drop_original(tmp_path, qtbot, monkeypatch):
    """Verify conflict drop original."""
    root, path = _make_conflict_project(tmp_path)

    class FakeDialog:
        def __init__(self, *_args, **_kwargs):
            self._choice = "drop_original"

        def exec(self):
            return None

        def choice(self):
            return self._choice

    monkeypatch.setattr(mw, "ConflictChoiceDialog", FakeDialog)

    win = MainWindow(str(root), selected_locales=["BE"])
    win._prompt_write_on_exit = False
    qtbot.addWidget(win)
    ix = win.fs_model.index_for_path(path)
    win._conflict_notified.add(path)
    win._file_chosen(ix)
    assert win._has_conflicts(path)

    win._prompt_conflicts(path)
    cache = read_cache(root, path)
    hello = cache[_hash_key("HELLO")]
    assert hello.value == "Здравствуйте"
    assert hello.original == "Привет!!"


def test_conflict_merge_resolutions(tmp_path, qtbot, monkeypatch):
    """Verify conflict merge resolutions."""
    root, path = _make_conflict_project(tmp_path)

    class FakeChoiceDialog:
        def __init__(self, *_args, **_kwargs):
            self._choice = "merge"

        def exec(self):
            return None

        def choice(self):
            return self._choice

    monkeypatch.setattr(mw, "ConflictChoiceDialog", FakeChoiceDialog)
    monkeypatch.setattr(
        mw.MainWindow,
        "_run_merge_ui",
        lambda _self, _path, _rows: {
            "HELLO": ("Здравствуйте", "cache"),
            "BYE": ("Пока...", "original"),
        },
    )

    win = MainWindow(str(root), selected_locales=["BE"])
    win._prompt_write_on_exit = False
    qtbot.addWidget(win)
    ix = win.fs_model.index_for_path(path)
    win._conflict_notified.add(path)
    win._file_chosen(ix)
    assert win._has_conflicts(path)

    win._prompt_conflicts(path)
    cache = read_cache(root, path)
    hello = cache[_hash_key("HELLO")]
    bye = cache[_hash_key("BYE")]
    assert hello.value == "Здравствуйте"
    assert hello.original == "Привет!!"
    assert bye.value is None
    assert bye.status == Status.FOR_REVIEW
