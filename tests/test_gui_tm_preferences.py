"""Test module for gui tm preferences."""

import re
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QListWidgetItem, QMessageBox, QSplitter

from translationzed_py.core import preferences
from translationzed_py.core.model import Status
from translationzed_py.core.tm_store import TMMatch
from translationzed_py.gui import MainWindow
from translationzed_py.gui import main_window as mw
from translationzed_py.gui.preferences_dialog import PreferencesDialog
from translationzed_py.gui.tm_preview import (
    apply_tm_preview_highlights,
    prepare_tm_preview_terms,
)


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
    """Verify tm preferences delete cancel keeps file."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE", "RU"])
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
    """Verify tm preferences delete confirm removes file."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE", "RU"])
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
    """Verify tm min score spin allows five and changes filter."""
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
    """Verify tm min score persists to settings env."""
    monkeypatch.chdir(tmp_path)
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    win._tm_score_spin.setValue(5)

    saved = preferences.load(None)
    extras = dict(saved.get("__extras__", {}))
    assert extras.get("TM_MIN_SCORE") == "5"


def test_tm_preview_term_sanitizer_drops_short_long_and_duplicates(tmp_path, qtbot):
    """Verify tm preview term sanitizer drops short long and duplicates."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    terms = ["a", "drop", "drop", "run", "x" * 120, "all"]
    assert prepare_tm_preview_terms(terms) == ["drop", "run", "all"]


def test_tm_apply_double_click_is_deferred(tmp_path, qtbot, monkeypatch):
    """Verify tm apply double click is deferred."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    calls: list[int] = []
    triggered: list[str] = []

    def _single_shot(delay: int, callback) -> None:
        calls.append(delay)
        callback()

    monkeypatch.setattr(mw.QTimer, "singleShot", staticmethod(_single_shot))
    monkeypatch.setattr(win, "_apply_tm_selection", lambda: triggered.append("apply"))

    win._on_tm_item_double_clicked(QListWidgetItem("sample"))

    assert calls == [0]
    assert triggered == ["apply"]


def test_tm_preview_highlight_skips_very_large_text(tmp_path, qtbot):
    """Verify tm preview highlight skips very large text."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    win._tm_source_preview.setPlainText("a" * 160_001)
    apply_tm_preview_highlights(win._tm_source_preview, ["aaaa"])

    assert win._tm_source_preview.extraSelections() == []


def test_theme_mode_persists_to_settings_env(tmp_path, qtbot, monkeypatch):
    """Verify theme mode persists to settings env."""
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
    """Verify apply theme mode clears delegate visual caches."""
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
    """Verify system theme change reapplies only for system mode."""
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


def test_source_reference_selector_switches_source_column(tmp_path, qtbot, monkeypatch):
    """Verify source reference selector switches source column."""
    monkeypatch.chdir(tmp_path)
    root = tmp_path / "proj"
    for loc in ("EN", "BE", "RU"):
        (root / loc).mkdir(parents=True, exist_ok=True)
        (root / loc / "language.txt").write_text(
            f"text = {loc},\ncharset = UTF-8,\n",
            encoding="utf-8",
        )
    (root / "EN" / "ui.txt").write_text('UI_KEY = "Hello"\n', encoding="utf-8")
    (root / "BE" / "ui.txt").write_text('UI_KEY = "Прывітанне"\n', encoding="utf-8")
    (root / "RU" / "ui.txt").write_text('UI_KEY = "Привет"\n', encoding="utf-8")

    win = MainWindow(str(root), selected_locales=["BE", "RU"])
    qtbot.addWidget(win)
    ix = win.fs_model.index_for_path(root / "BE" / "ui.txt")
    win._file_chosen(ix)
    model = win.table.model()
    assert model is not None
    assert model.data(model.index(0, 1), Qt.DisplayRole) == "Hello"
    assert str(model.headerData(1, Qt.Horizontal, Qt.DisplayRole)).startswith(
        "Source [EN]"
    )

    locales = [
        win.source_ref_combo.itemData(i) for i in range(win.source_ref_combo.count())
    ]
    assert locales == ["EN", "RU"]

    idx = win.source_ref_combo.findData("RU")
    assert idx >= 0
    win.source_ref_combo.setCurrentIndex(idx)
    assert model.data(model.index(0, 1), Qt.DisplayRole) == "Привет"
    assert str(model.headerData(1, Qt.Horizontal, Qt.DisplayRole)).startswith(
        "Source [RU]"
    )

    saved = preferences.load(None)
    extras = dict(saved.get("__extras__", {}))
    assert extras.get("SOURCE_REFERENCE_MODE") == "RU"


def test_source_reference_selector_shows_only_opened_locales(
    tmp_path, qtbot, monkeypatch
):
    """Verify source reference selector shows only opened locales."""
    monkeypatch.chdir(tmp_path)
    root = tmp_path / "proj"
    for loc in ("EN", "BE", "RU"):
        (root / loc).mkdir(parents=True, exist_ok=True)
        (root / loc / "language.txt").write_text(
            f"text = {loc},\ncharset = UTF-8,\n",
            encoding="utf-8",
        )
    (root / "EN" / "ui.txt").write_text('UI_KEY = "Hello"\n', encoding="utf-8")
    (root / "BE" / "ui.txt").write_text('UI_KEY = "Прывітанне"\n', encoding="utf-8")
    (root / "RU" / "ui.txt").write_text('UI_KEY = "Привет"\n', encoding="utf-8")

    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    ix = win.fs_model.index_for_path(root / "BE" / "ui.txt")
    win._file_chosen(ix)
    model = win.table.model()
    assert model is not None

    locales = [
        win.source_ref_combo.itemData(i) for i in range(win.source_ref_combo.count())
    ]
    assert locales == ["EN"]
    assert win.source_ref_combo.findData("RU") < 0


def test_source_reference_mode_applies_globally_across_files(
    tmp_path, qtbot, monkeypatch
):
    """Verify source reference mode applies globally across files."""
    monkeypatch.chdir(tmp_path)
    root = tmp_path / "proj"
    for loc in ("EN", "BE", "RU"):
        (root / loc).mkdir(parents=True, exist_ok=True)
        (root / loc / "language.txt").write_text(
            f"text = {loc},\ncharset = UTF-8,\n",
            encoding="utf-8",
        )
    (root / "EN" / "ui.txt").write_text('UI_KEY = "UI EN"\n', encoding="utf-8")
    (root / "BE" / "ui.txt").write_text('UI_KEY = "UI BE"\n', encoding="utf-8")
    (root / "RU" / "ui.txt").write_text('UI_KEY = "UI RU"\n', encoding="utf-8")
    (root / "EN" / "menu.txt").write_text('MENU_KEY = "MENU EN"\n', encoding="utf-8")
    (root / "BE" / "menu.txt").write_text('MENU_KEY = "MENU BE"\n', encoding="utf-8")
    (root / "RU" / "menu.txt").write_text('MENU_KEY = "MENU RU"\n', encoding="utf-8")

    win = MainWindow(str(root), selected_locales=["BE", "RU"])
    qtbot.addWidget(win)
    ui_idx = win.fs_model.index_for_path(root / "BE" / "ui.txt")
    menu_idx = win.fs_model.index_for_path(root / "BE" / "menu.txt")
    win._file_chosen(ui_idx)
    model = win.table.model()
    assert model is not None

    ru_idx = win.source_ref_combo.findData("RU")
    en_idx = win.source_ref_combo.findData("EN")
    assert ru_idx >= 0
    assert en_idx >= 0
    win.source_ref_combo.setCurrentIndex(ru_idx)
    assert model.data(model.index(0, 1), Qt.DisplayRole) == "UI RU"

    win._file_chosen(menu_idx)
    model = win.table.model()
    assert model is not None
    assert model.data(model.index(0, 1), Qt.DisplayRole) == "MENU RU"

    win._file_chosen(ui_idx)
    model = win.table.model()
    assert model is not None
    assert model.data(model.index(0, 1), Qt.DisplayRole) == "UI RU"

    win.source_ref_combo.setCurrentIndex(en_idx)
    win._file_chosen(menu_idx)
    model = win.table.model()
    assert model is not None
    assert model.data(model.index(0, 1), Qt.DisplayRole) == "MENU EN"


def test_source_reference_selector_falls_back_to_en_when_unavailable(
    tmp_path, qtbot, monkeypatch
):
    """Verify source reference selector falls back to en when unavailable."""
    monkeypatch.chdir(tmp_path)
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    win._source_reference_mode = "RU"
    win._sync_source_reference_mode(persist=False)

    assert win._source_reference_mode == "EN"
    locales = [
        win.source_ref_combo.itemData(i) for i in range(win.source_ref_combo.count())
    ]
    assert locales == ["EN", "BE"]


def test_source_reference_selector_target_then_en_fallback_policy(
    tmp_path, qtbot, monkeypatch
):
    """Verify source reference selector target then en fallback policy."""
    monkeypatch.chdir(tmp_path)
    root = tmp_path / "proj"
    for loc, value in (("EN", "EN SRC"), ("BE", "BE SRC")):
        (root / loc).mkdir(parents=True, exist_ok=True)
        (root / loc / "language.txt").write_text(
            f"text = {loc},\ncharset = UTF-8,\n",
            encoding="utf-8",
        )
        (root / loc / "ui.txt").write_text(
            f'UI_KEY = "{value}"\n',
            encoding="utf-8",
        )

    win = MainWindow(str(root), selected_locales=["BE", "RU"])
    qtbot.addWidget(win)
    win._source_reference_mode = "RU"
    win._source_reference_fallback_policy = "TARGET_THEN_EN"
    win._sync_source_reference_mode(persist=False)
    assert win._source_reference_mode == "BE"


def test_tm_panel_includes_imported_matches(tmp_path, qtbot, monkeypatch):
    """Verify tm panel includes imported matches."""
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


def test_tm_apply_keeps_status_and_is_single_undo_step(tmp_path, qtbot, monkeypatch):
    """Verify tm apply keeps status and is single undo step."""
    monkeypatch.chdir(tmp_path)
    root = _make_project(tmp_path)
    (root / "EN" / "ui.txt").write_text('UI_KEY = "Camera"\n', encoding="utf-8")
    (root / "BE" / "ui.txt").write_text('UI_KEY = "Камера"\n', encoding="utf-8")

    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    ix = win.fs_model.index_for_path(root / "BE" / "ui.txt")
    win._file_chosen(ix)
    model = win.table.model()
    assert model is not None

    value_index = model.index(0, 2)
    status_index = model.index(0, 3)
    model.setData(status_index, Status.TRANSLATED, Qt.EditRole)
    before_value = str(model.data(value_index, Qt.EditRole))
    before_status = model.data(status_index, Qt.EditRole)
    assert before_status == Status.TRANSLATED
    win.table.setCurrentIndex(value_index)

    win._show_tm_matches(
        [
            TMMatch(
                source_text="Camera",
                target_text="Камеры",
                score=100,
                origin="project",
                tm_name="test",
                tm_path=None,
                file_path="BE/ui.txt",
                key="UI_KEY",
                updated_at=1,
            )
        ]
    )
    assert win._tm_list.count() == 1
    win._apply_tm_selection()

    assert model.data(value_index, Qt.EditRole) == "Камеры"
    assert model.data(status_index, Qt.EditRole) == Status.TRANSLATED

    model.undo_stack.undo()
    assert model.data(value_index, Qt.EditRole) == before_value
    assert model.data(status_index, Qt.EditRole) == Status.TRANSLATED


def test_tm_panel_does_not_expose_locale_variants_ui(tmp_path, qtbot):
    """Verify compact TM panel does not include locale variants widgets."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    assert not hasattr(win, "_tm_variants_list")


def test_tm_panel_source_and_translation_previews_are_resizable(tmp_path, qtbot):
    """Verify tm panel keeps a single resizable splitter and explicit TM labels."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    assert isinstance(win._tm_content_splitter, QSplitter)
    assert win._tm_content_splitter.count() == 2
    assert not hasattr(win, "_tm_preview_splitter")
    assert win._tm_source_label.text() == "TM Source"
    assert win._tm_target_label.text() == "TM Translation"
    assert win._tm_source_preview.maximumHeight() > 1000
    assert win._tm_target_preview.maximumHeight() > 1000
    assert win._tm_list.count() == 1
    assert (
        win._tm_list.item(0).text()
        == "Select row to see Translation Memory suggestions."
    )
    tm_header_layout = win._tm_panel.layout().itemAt(0).layout()
    assert tm_header_layout is not None
    header_widgets = [
        tm_header_layout.itemAt(i).widget() for i in range(tm_header_layout.count())
    ]
    assert any(
        isinstance(widget, QLabel) and widget.text() == "Min score"
        for widget in header_widgets
    )
    prefs_index = next(
        i for i, widget in enumerate(header_widgets) if widget is win._tm_prefs_btn
    )
    rebuild_index = next(
        i
        for i, widget in enumerate(header_widgets)
        if widget is win._tm_rebuild_side_btn
    )
    assert prefs_index < rebuild_index
    assert win._tm_origin_project_cb.text() == "Project"
    assert win._tm_origin_import_cb.text() == "Import"
    assert win._tm_origin_project_cb.icon().isNull() is True
    assert win._tm_origin_import_cb.icon().isNull() is True
    assert win._tm_prefs_btn.icon().isNull() is False


def test_side_panel_preference_shortcuts_open_matching_tabs(
    tmp_path, qtbot, monkeypatch
):
    """Verify TM/Search/QA side panels expose shortcuts to corresponding prefs tabs."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    calls: list[str | None] = []
    monkeypatch.setattr(
        win,
        "_open_preferences",
        lambda *, initial_tab=None: calls.append(initial_tab),
    )

    win._tm_prefs_btn.click()
    win._search_prefs_btn.click()
    win._qa_prefs_btn.click()

    assert calls == ["tm", "search", "qa"]


def test_tm_bootstrap_rebuild_runs_even_when_store_has_entries(
    tmp_path, qtbot, monkeypatch
):
    """Verify tm bootstrap rebuild runs even when store has entries."""
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
    """Verify rebuild tm selected initializes tm store."""
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
    """Verify apply preferences runs tm actions from tm tab."""
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
    """Verify preferences tm action buttons set flags."""
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


def test_preferences_qa_tab_roundtrip_values(tmp_path, qtbot):
    """Verify preferences qa tab roundtrip values."""
    root = _make_project(tmp_path)
    dialog = PreferencesDialog(
        {
            "tm_import_dir": str(root / ".tzp" / "tms"),
            "qa_check_trailing": False,
            "qa_check_newlines": False,
            "qa_check_escapes": True,
            "qa_check_same_as_source": True,
            "qa_auto_refresh": True,
            "qa_auto_mark_for_review": True,
            "qa_auto_mark_translated_for_review": True,
            "qa_auto_mark_proofread_for_review": False,
            "lt_editor_mode": "on",
            "lt_server_url": "https://lt.example.org",
            "lt_timeout_ms": 900,
            "lt_picky_mode": True,
            "lt_locale_map": '{"EN":"en-US","BE":"be-BY"}',
            "qa_check_languagetool": True,
            "qa_languagetool_max_rows": 64,
            "qa_languagetool_automark": True,
        },
        tm_files=[],
    )
    qtbot.addWidget(dialog)

    assert dialog._qa_trailing_check.isChecked() is False
    assert dialog._qa_newlines_check.isChecked() is False
    assert dialog._qa_tokens_check.isChecked() is True
    assert dialog._qa_same_source_check.isChecked() is True
    assert dialog._qa_auto_refresh_check.isChecked() is True
    assert dialog._qa_auto_mark_check.isChecked() is True
    assert dialog._qa_auto_mark_translated_check.isChecked() is True
    assert dialog._qa_auto_mark_proofread_check.isChecked() is False
    assert dialog._lt_editor_mode_combo.currentData() == "on"
    assert dialog._lt_server_url_edit.text() == "https://lt.example.org"
    assert dialog._lt_timeout_spin.value() == 900
    assert dialog._lt_picky_check.isChecked() is True
    assert dialog._lt_locale_map_edit.toPlainText() == '{"EN":"en-US","BE":"be-BY"}'
    assert dialog._qa_lt_check.isChecked() is True
    assert dialog._qa_lt_max_rows_spin.value() == 64
    assert dialog._qa_lt_automark_check.isChecked() is True

    dialog._qa_trailing_check.setChecked(True)
    dialog._qa_newlines_check.setChecked(True)
    dialog._qa_tokens_check.setChecked(False)
    dialog._qa_same_source_check.setChecked(False)
    dialog._qa_auto_refresh_check.setChecked(False)
    dialog._qa_auto_mark_check.setChecked(False)
    dialog._qa_auto_mark_translated_check.setChecked(False)
    dialog._qa_auto_mark_proofread_check.setChecked(False)
    dialog._lt_editor_mode_combo.setCurrentIndex(
        dialog._lt_editor_mode_combo.findData("off")
    )
    dialog._lt_server_url_edit.setText("http://127.0.0.1:8081")
    dialog._lt_timeout_spin.setValue(1234)
    dialog._lt_picky_check.setChecked(False)
    dialog._lt_locale_map_edit.setPlainText('{"EN":"en-US"}')
    dialog._qa_lt_check.setChecked(False)
    dialog._qa_lt_max_rows_spin.setValue(10)
    dialog._qa_lt_automark_check.setChecked(True)

    values = dialog.values()
    assert values["qa_check_trailing"] is True
    assert values["qa_check_newlines"] is True
    assert values["qa_check_escapes"] is False
    assert values["qa_check_same_as_source"] is False
    assert values["qa_auto_refresh"] is False
    assert values["qa_auto_mark_for_review"] is False
    assert values["qa_auto_mark_translated_for_review"] is False
    assert values["qa_auto_mark_proofread_for_review"] is False
    assert values["lt_editor_mode"] == "off"
    assert values["lt_server_url"] == "http://127.0.0.1:8081"
    assert values["lt_timeout_ms"] == 1234
    assert values["lt_picky_mode"] is False
    assert values["lt_locale_map"] == '{"EN":"en-US"}'
    assert values["qa_check_languagetool"] is False
    assert values["qa_languagetool_max_rows"] == 10
    assert values["qa_languagetool_automark"] is False


def test_preferences_qa_touched_auto_mark_clears_when_base_toggle_off(tmp_path, qtbot):
    """Verify touched-row QA auto-mark checkbox is cleared when base auto-mark is disabled."""
    root = _make_project(tmp_path)
    dialog = PreferencesDialog(
        {
            "tm_import_dir": str(root / ".tzp" / "tms"),
            "qa_auto_mark_for_review": True,
            "qa_auto_mark_translated_for_review": True,
            "qa_auto_mark_proofread_for_review": True,
        },
        tm_files=[],
    )
    qtbot.addWidget(dialog)

    assert dialog._qa_auto_mark_check.isChecked() is True
    assert dialog._qa_auto_mark_translated_check.isChecked() is True
    assert dialog._qa_auto_mark_proofread_check.isChecked() is True
    dialog._qa_auto_mark_check.setChecked(False)

    assert dialog._qa_auto_mark_translated_check.isEnabled() is False
    assert dialog._qa_auto_mark_proofread_check.isEnabled() is False
    assert dialog._qa_auto_mark_translated_check.isChecked() is False
    assert dialog._qa_auto_mark_proofread_check.isChecked() is False
    values = dialog.values()
    assert values["qa_auto_mark_for_review"] is False
    assert values["qa_auto_mark_translated_for_review"] is False
    assert values["qa_auto_mark_proofread_for_review"] is False


def test_apply_preferences_updates_qa_flags_and_triggers_refresh(
    tmp_path, qtbot, monkeypatch
):
    """Verify apply preferences updates qa flags and triggers refresh."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    ix = win.fs_model.index_for_path(root / "BE" / "ui.txt")
    win._file_chosen(ix)

    monkeypatch.setattr(win, "_apply_tm_preferences_actions", lambda _values: None)
    monkeypatch.setattr(win, "_persist_preferences", lambda: None)
    refresh_calls: list[bool] = []
    monkeypatch.setattr(
        win,
        "_schedule_qa_refresh",
        lambda *, immediate=False: refresh_calls.append(bool(immediate)),
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
            "qa_check_trailing": False,
            "qa_check_newlines": False,
            "qa_check_escapes": True,
            "qa_check_same_as_source": True,
            "qa_auto_refresh": True,
            "qa_auto_mark_for_review": True,
            "qa_auto_mark_translated_for_review": True,
            "qa_auto_mark_proofread_for_review": False,
        }
    )

    assert win._qa_check_trailing is False
    assert win._qa_check_newlines is False
    assert win._qa_check_escapes is True
    assert win._qa_check_same_as_source is True
    assert win._qa_auto_refresh is True
    assert win._qa_auto_mark_for_review is True
    assert win._qa_auto_mark_translated_for_review is True
    assert win._qa_auto_mark_proofread_for_review is False
    assert refresh_calls == [True]


def test_preferences_tm_diagnostics_button_sets_flag(tmp_path, qtbot):
    """Verify preferences tm diagnostics button sets flag."""
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
    """Verify tm diagnostics uses copyable report."""
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
    """Verify tm diagnostics reports match density and origin counts."""
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
    """Verify preferences tm tab shows format and storage description."""
    root = _make_project(tmp_path)
    dialog = PreferencesDialog(
        {"tm_import_dir": str(root / ".tzp" / "tms")}, tm_files=[]
    )
    qtbot.addWidget(dialog)

    text = dialog._tm_formats_label.text()
    assert "Supported now" in text
    assert "Planned later" in text
    assert "TMX" in text
    assert "XLIFF" in text
    assert "PO" in text
    assert ".csv" in text
    assert ".mo" in text
    assert ".xml" in text
    assert ".xlsx" in text
    assert ".xlf" in text
    assert ".pot" in text
    assert ".tzp/config/tm.sqlite" in text
    assert ".tzp/tms" in text
    assert dialog._tm_zero_segment_banner is not None
    assert dialog._tm_zero_segment_banner.isHidden() is True


def test_preferences_tm_resolve_button_enables_for_pending_items(tmp_path, qtbot):
    """Verify preferences tm resolve button enables for pending items."""
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
    """Verify preferences tm list shows segment count and zero warning."""
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
    assert dialog._tm_zero_segment_banner is not None
    assert dialog._tm_zero_segment_banner.isHidden() is False
    banner_text = dialog._tm_zero_segment_banner.text()
    assert "0 segments" in banner_text
    assert "will not contribute suggestions" in banner_text
