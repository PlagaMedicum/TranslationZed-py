from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from translationzed_py.core import preferences
from translationzed_py.core.tm_store import TMMatch
from translationzed_py.gui import MainWindow
from translationzed_py.gui import main_window as mw


def _make_project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    for loc in ("EN", "BE"):
        (root / loc).mkdir(parents=True, exist_ok=True)
        (root / loc / "language.txt").write_text(
            f"text = {loc},\ncharset = UTF-8,\n",
            encoding="utf-8",
        )
        (root / loc / "ui.txt").write_text('UI_KEY = "v"\n', encoding="utf-8")
    return root


def _register_imported_tm(win: MainWindow, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("tmx", encoding="utf-8")
    assert win._ensure_tm_store()
    stat = path.stat()
    win._tm_store.upsert_import_file(
        tm_path=str(path),
        tm_name=path.stem,
        source_locale="EN",
        target_locale="BE",
        mtime_ns=stat.st_mtime_ns,
        file_size=stat.st_size,
        enabled=True,
        status="ready",
    )


def test_tm_preferences_delete_cancel_keeps_file(tmp_path, qtbot, monkeypatch):
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    tm_path = root / ".tzp" / "tms" / "sample.tmx"
    _register_imported_tm(win, tm_path)

    monkeypatch.setattr(
        mw.QMessageBox,
        "exec",
        lambda _self: int(QMessageBox.StandardButton.Cancel),
    )
    win._apply_tm_preferences_actions({"tm_remove_paths": [str(tm_path)]})

    assert tm_path.exists()
    assert any(rec.tm_path == str(tm_path) for rec in win._tm_store.list_import_files())


def test_tm_preferences_delete_confirm_removes_file(tmp_path, qtbot, monkeypatch):
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    tm_path = root / ".tzp" / "tms" / "sample.tmx"
    _register_imported_tm(win, tm_path)

    monkeypatch.setattr(
        mw.QMessageBox,
        "exec",
        lambda _self: int(QMessageBox.StandardButton.Yes),
    )
    win._apply_tm_preferences_actions({"tm_remove_paths": [str(tm_path)]})

    assert not tm_path.exists()
    assert all(rec.tm_path != str(tm_path) for rec in win._tm_store.list_import_files())


def test_tm_min_score_spin_allows_five_and_changes_filter(tmp_path, qtbot, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    monkeypatch.setattr(win, "_persist_preferences", lambda: None)

    assert win._tm_score_spin.minimum() == 5
    assert win._tm_score_spin.maximum() == 100
    assert win._tm_min_score == 50

    matches = [
        TMMatch(
            source_text="s low",
            target_text="t low",
            score=10,
            origin="project",
            tm_name=None,
            tm_path=None,
            file_path=None,
            key=None,
            updated_at=1,
        ),
        TMMatch(
            source_text="s high",
            target_text="t high",
            score=90,
            origin="project",
            tm_name=None,
            tm_path=None,
            file_path=None,
            key=None,
            updated_at=1,
        ),
    ]

    win._show_tm_matches(matches)
    assert win._tm_list.count() == 1

    win._tm_score_spin.setValue(5)
    assert win._tm_min_score == 5
    assert win._prefs_extras["TM_MIN_SCORE"] == "5"

    win._show_tm_matches(matches)
    assert win._tm_list.count() == 2


def test_tm_min_score_persists_to_settings_env(tmp_path, qtbot, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    win._tm_score_spin.setValue(5)

    saved = preferences.load(None)
    extras = dict(saved.get("__extras__", {}))
    assert extras.get("TM_MIN_SCORE") == "5"


def test_tm_panel_includes_imported_matches(tmp_path, qtbot, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root = _make_project(tmp_path)
    (root / "EN" / "ui.txt").write_text('UI_KEY = "Hello world"\n', encoding="utf-8")
    (root / "BE" / "ui.txt").write_text('UI_KEY = ""\n', encoding="utf-8")
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    assert win._ensure_tm_store()

    tm_path = root / ".tzp" / "tms" / "sample_import.tmx"
    tm_path.parent.mkdir(parents=True, exist_ok=True)
    tm_path.write_text("tmx", encoding="utf-8")
    win._tm_store.insert_import_pairs(
        [("Hello world", "Hello from import")],
        source_locale="EN",
        target_locale="BE",
        tm_name="sample_import",
        tm_path=str(tm_path),
    )
    stat = tm_path.stat()
    win._tm_store.upsert_import_file(
        tm_path=str(tm_path),
        tm_name="sample_import",
        source_locale="EN",
        target_locale="BE",
        mtime_ns=stat.st_mtime_ns,
        file_size=stat.st_size,
        enabled=True,
        status="ready",
    )

    ix = win.fs_model.index_for_path(root / "BE" / "ui.txt")
    win._file_chosen(ix)
    model = win.table.model()
    win.table.setCurrentIndex(model.index(0, 2))
    lookup = win._current_tm_lookup()
    assert lookup is not None
    source_text, target_locale = lookup
    matches = win._tm_store.query(
        source_text,
        source_locale=win._tm_source_locale,
        target_locale=target_locale,
        limit=12,
        min_score=win._tm_min_score,
        origins=("project", "import"),
    )
    win._show_tm_matches(matches)
    assert win._tm_list.count() > 0
    origins = []
    for i in range(win._tm_list.count()):
        item = win._tm_list.item(i)
        match = item.data(Qt.UserRole)
        if isinstance(match, TMMatch):
            origins.append(match.origin)
    assert "import" in origins
