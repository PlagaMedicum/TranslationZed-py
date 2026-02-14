import re
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from translationzed_py.core import preferences
from translationzed_py.core.tm_store import TMMatch
from translationzed_py.gui import MainWindow
from translationzed_py.gui import main_window as mw
from translationzed_py.gui.preferences_dialog import PreferencesDialog


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


def _register_imported_tm(
    win: MainWindow,
    path: Path,
    *,
    source_locale_raw: str = "",
    target_locale_raw: str = "",
    segment_count: int = 1,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("tmx", encoding="utf-8")
    assert win._ensure_tm_store()
    win._test_mode = False
    stat = path.stat()
    win._tm_store.upsert_import_file(
        tm_path=str(path),
        tm_name=path.stem,
        source_locale="EN",
        target_locale="BE",
        source_locale_raw=source_locale_raw,
        target_locale_raw=target_locale_raw,
        segment_count=segment_count,
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


def test_theme_mode_persists_to_settings_env(tmp_path, qtbot, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    win._apply_theme_mode("DARK", persist=True)
    saved = preferences.load(None)
    extras = dict(saved.get("__extras__", {}))
    assert extras.get("UI_THEME_MODE") == "DARK"

    win._apply_theme_mode("SYSTEM", persist=True)
    saved = preferences.load(None)
    extras = dict(saved.get("__extras__", {}))
    assert "UI_THEME_MODE" not in extras


def test_apply_theme_mode_clears_delegate_visual_caches(tmp_path, qtbot, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    calls: list[str] = []

    monkeypatch.setattr(
        win._source_delegate,
        "clear_visual_cache",
        lambda: calls.append("source"),
    )
    monkeypatch.setattr(
        win._value_delegate,
        "clear_visual_cache",
        lambda: calls.append("value"),
    )

    win._apply_theme_mode("LIGHT", persist=False)
    assert sorted(calls) == ["source", "value"]


def test_system_theme_change_reapplies_only_for_system_mode(
    tmp_path, qtbot, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    calls: list[tuple[str, bool]] = []

    def _capture(mode, *, persist):
        calls.append((str(mode), bool(persist)))

    monkeypatch.setattr(win, "_apply_theme_mode", _capture)
    win._theme_mode = "DARK"
    win._on_system_color_scheme_changed()
    assert calls == []

    win._theme_mode = "SYSTEM"
    win._on_system_color_scheme_changed()
    assert calls == [("SYSTEM", False)]


def test_tm_panel_includes_imported_matches(tmp_path, qtbot, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root = _make_project(tmp_path)
    (root / "EN" / "ui.txt").write_text('UI_KEY = "Hello world"\n', encoding="utf-8")
    (root / "BE" / "ui.txt").write_text('UI_KEY = ""\n', encoding="utf-8")
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    assert win._ensure_tm_store()
    win._test_mode = False

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


def test_tm_panel_shows_cross_locale_variants_in_session_order(
    tmp_path, qtbot, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    root = tmp_path / "proj"
    for loc in ("EN", "BE", "RU", "KO"):
        (root / loc).mkdir(parents=True, exist_ok=True)
        (root / loc / "language.txt").write_text(
            f"text = {loc},\ncharset = UTF-8,\n",
            encoding="utf-8",
        )
    (root / "EN" / "ui.txt").write_text('UI_KEY = "Drop one"\n', encoding="utf-8")
    (root / "BE" / "ui.txt").write_text('UI_KEY = "Скінуць шт."\n', encoding="utf-8")
    (root / "RU" / "ui.txt").write_text('UI_KEY = "Сбросить шт."\n', encoding="utf-8")
    (root / "KO" / "ui.txt").write_text('UI_KEY = "하나 버리기"\n', encoding="utf-8")

    win = MainWindow(str(root), selected_locales=["BE", "RU", "KO"])
    qtbot.addWidget(win)
    assert win._ensure_tm_store()
    ix = win.fs_model.index_for_path(root / "BE" / "ui.txt")
    win._file_chosen(ix)
    model = win.table.model()
    win.table.setCurrentIndex(model.index(0, 2))
    win._left_stack.setCurrentIndex(1)
    win._update_tm_suggestions()

    assert win._tm_variants_list.count() == 2
    assert win._tm_variants_list.item(0).text().startswith("RU ·")
    assert win._tm_variants_list.item(1).text().startswith("KO ·")


def test_tm_bootstrap_rebuild_runs_even_when_store_has_entries(
    tmp_path, qtbot, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    root = _make_project(tmp_path)
    (root / "EN" / "ui.txt").write_text('UI_KEY = "Drop one"\n', encoding="utf-8")
    (root / "BE" / "ui.txt").write_text('UI_KEY = "Скінуць шт."\n', encoding="utf-8")
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    assert win._ensure_tm_store()
    win._test_mode = False

    # Simulate stale/incomplete TM DB state from a previous session.
    win._tm_store.upsert_project_entries(
        [("UI_KEY", "Drop one", "Скінуць шт.")],
        source_locale="EN",
        target_locale="BE",
        file_path=str(root / "BE" / "ui.txt"),
    )

    called: list[tuple[list[str], bool, bool]] = []

    def _capture_start(locales: list[str], *, interactive: bool, force: bool) -> None:
        called.append((list(locales), interactive, force))

    monkeypatch.setattr(win, "_start_tm_rebuild", _capture_start)
    win._maybe_bootstrap_tm()

    assert called == [(["BE"], False, False)]


def test_rebuild_tm_selected_initializes_tm_store(tmp_path, qtbot, monkeypatch):
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    called: list[str] = []

    def _ensure() -> bool:
        called.append("ensure")
        win._tm_store = object()  # type: ignore[assignment]
        return True

    rebuild_calls: list[tuple[list[str], bool, bool]] = []

    def _start(locales, *, interactive: bool, force: bool) -> None:
        rebuild_calls.append((list(locales), interactive, force))

    monkeypatch.setattr(win, "_ensure_tm_store", _ensure)
    monkeypatch.setattr(win, "_start_tm_rebuild", _start)
    win._rebuild_tm_selected()

    assert called == ["ensure"]
    assert rebuild_calls == [(["BE"], True, True)]


def test_apply_preferences_runs_tm_actions_from_tm_tab(tmp_path, qtbot, monkeypatch):
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    monkeypatch.setattr(win, "_apply_tm_preferences_actions", lambda _values: None)
    monkeypatch.setattr(win, "_persist_preferences", lambda: None)
    called: list[str] = []
    monkeypatch.setattr(win, "_resolve_pending_tmx", lambda: called.append("resolve"))
    monkeypatch.setattr(win, "_export_tmx", lambda: called.append("export"))
    monkeypatch.setattr(win, "_rebuild_tm_selected", lambda: called.append("rebuild"))
    monkeypatch.setattr(
        win, "_show_tm_diagnostics", lambda: called.append("diagnostics")
    )

    win._apply_preferences(
        {
            "prompt_write_on_exit": True,
            "wrap_text": win._wrap_text_user,
            "large_text_optimizations": win._large_text_optimizations,
            "visual_highlight": win._visual_highlight,
            "visual_whitespace": win._visual_whitespace,
            "default_root": win._default_root,
            "tm_import_dir": win._tm_import_dir,
            "search_scope": win._search_scope,
            "replace_scope": win._replace_scope,
            "tm_resolve_pending": True,
            "tm_export_tmx": True,
            "tm_rebuild": True,
            "tm_show_diagnostics": True,
        }
    )
    assert called == ["resolve", "export", "rebuild", "diagnostics"]


def test_preferences_tm_action_buttons_set_flags(tmp_path, qtbot):
    root = _make_project(tmp_path)
    dialog = PreferencesDialog(
        {"tm_import_dir": str(root / ".tzp" / "tms"), "theme_mode": "DARK"},
        tm_files=[],
    )
    qtbot.addWidget(dialog)

    dialog._request_tm_resolve_pending()
    values = dialog.values()
    assert values["theme_mode"] == "DARK"
    assert values["tm_resolve_pending"] is True
    assert values["tm_export_tmx"] is False
    assert values["tm_rebuild"] is False
    assert values["tm_show_diagnostics"] is False


def test_preferences_tm_diagnostics_button_sets_flag(tmp_path, qtbot):
    root = _make_project(tmp_path)
    dialog = PreferencesDialog(
        {"tm_import_dir": str(root / ".tzp" / "tms")}, tm_files=[]
    )
    qtbot.addWidget(dialog)

    dialog._request_tm_diagnostics()
    values = dialog.values()
    assert values["tm_show_diagnostics"] is True
    assert values["tm_resolve_pending"] is False


def test_tm_diagnostics_uses_copyable_report(tmp_path, qtbot, monkeypatch):
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    captured: list[tuple[str, str]] = []
    monkeypatch.setattr(
        win,
        "_show_copyable_report",
        lambda title, text: captured.append((title, text)),
    )

    win._show_tm_diagnostics()

    assert captured
    title, text = captured[0]
    assert title == "TM diagnostics"
    assert "TM DB:" in text
    assert "Policy:" in text


def test_tm_diagnostics_reports_match_density_and_origin_counts(
    tmp_path, qtbot, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    root = _make_project(tmp_path)
    (root / "EN" / "ui.txt").write_text('UI_KEY = "Drop all"\n', encoding="utf-8")
    (root / "BE" / "ui.txt").write_text('UI_KEY = ""\n', encoding="utf-8")
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    assert win._ensure_tm_store()
    win._test_mode = False

    tm_path = root / ".tzp" / "tms" / "diag_import.tmx"
    _register_imported_tm(win, tm_path)
    win._tm_store.insert_import_pairs(
        [("Drop one", "Скінуць шт.")],
        source_locale="EN",
        target_locale="BE",
        tm_name="diag_import",
        tm_path=str(tm_path),
    )
    win._tm_store.upsert_project_entries(
        [
            ("k1", "Drop all", "Пакінуць усё"),
            ("k2", "Drop one", "Скінуць шт."),
            ("k3", "Drop-all", "Пакід. усё"),
        ],
        source_locale="EN",
        target_locale="BE",
        file_path=str(root / "BE" / "ui.txt"),
        updated_at=1,
    )

    win._tm_score_spin.setValue(5)
    ix = win.fs_model.index_for_path(root / "BE" / "ui.txt")
    win._file_chosen(ix)
    model = win.table.model()
    win.table.setCurrentIndex(model.index(0, 2))

    captured: list[tuple[str, str]] = []
    monkeypatch.setattr(
        win,
        "_show_copyable_report",
        lambda title, text: captured.append((title, text)),
    )

    win._show_tm_diagnostics()

    assert captured
    title, text = captured[0]
    assert title == "TM diagnostics"
    assert "Policy: min=5%" in text
    assert "Matches: visible=" in text
    assert "recall_density=" in text

    match_line = next(
        line for line in text.splitlines() if line.startswith("Matches: visible=")
    )

    def _read_int(metric: str) -> int:
        m = re.search(rf"{metric}=(\d+)", match_line)
        assert m is not None
        return int(m.group(1))

    visible = _read_int("visible")
    project = _read_int("project")
    imported = _read_int("import")
    unique_sources = _read_int("unique_sources")
    assert visible >= 3
    assert project >= 1
    assert imported >= 1
    assert unique_sources >= 2


def test_preferences_tm_tab_shows_format_and_storage_description(tmp_path, qtbot):
    root = _make_project(tmp_path)
    dialog = PreferencesDialog(
        {"tm_import_dir": str(root / ".tzp" / "tms")}, tm_files=[]
    )
    qtbot.addWidget(dialog)

    text = dialog._tm_formats_label.text()
    assert "Supported now" in text
    assert "Planned later" in text
    assert "TMX" in text
    assert ".tzp/config/tm.sqlite" in text
    assert ".tzp/tms" in text


def test_preferences_tm_resolve_button_enables_for_pending_items(tmp_path, qtbot):
    root = _make_project(tmp_path)
    dialog_empty = PreferencesDialog(
        {"tm_import_dir": str(root / ".tzp" / "tms")},
        tm_files=[],
    )
    qtbot.addWidget(dialog_empty)
    assert dialog_empty._tm_resolve_btn is not None
    assert dialog_empty._tm_resolve_btn.isEnabled() is False

    dialog_pending = PreferencesDialog(
        {"tm_import_dir": str(root / ".tzp" / "tms")},
        tm_files=[
            {
                "tm_path": str(root / ".tzp" / "tms" / "pending.tmx"),
                "tm_name": "pending",
                "source_locale": "EN",
                "target_locale": "BE",
                "source_locale_raw": "",
                "target_locale_raw": "",
                "segment_count": 0,
                "enabled": True,
                "status": "pending",
                "note": "unmapped",
            }
        ],
    )
    qtbot.addWidget(dialog_pending)
    assert dialog_pending._tm_resolve_btn is not None
    assert dialog_pending._tm_resolve_btn.isEnabled() is True


def test_preferences_tm_list_shows_segment_count_and_zero_warning(
    tmp_path, qtbot, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    tm_path = root / ".tzp" / "tms" / "sample_meta.tmx"
    _register_imported_tm(
        win,
        tm_path,
        source_locale_raw="en-US",
        target_locale_raw="be-BY",
        segment_count=0,
    )
    tm_files = [
        {
            "tm_path": rec.tm_path,
            "tm_name": rec.tm_name,
            "source_locale": rec.source_locale,
            "target_locale": rec.target_locale,
            "source_locale_raw": rec.source_locale_raw,
            "target_locale_raw": rec.target_locale_raw,
            "segment_count": rec.segment_count,
            "enabled": rec.enabled,
            "status": rec.status,
            "note": rec.note,
        }
        for rec in win._tm_store.list_import_files()
    ]
    dialog = PreferencesDialog(
        {"tm_import_dir": str(root / ".tzp" / "tms")}, tm_files=tm_files
    )
    qtbot.addWidget(dialog)

    assert dialog._tm_list.count() == 1
    text = dialog._tm_list.item(0).text()
    assert "0 seg" in text
    assert "{en-US->be-BY}" in text
    assert "WARNING: 0 segments" in text
