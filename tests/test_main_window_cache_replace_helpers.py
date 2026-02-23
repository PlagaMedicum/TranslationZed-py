"""Test module for main-window cache and replace helper branches."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, QSize
from PySide6.QtGui import QResizeEvent, QShowEvent

from translationzed_py.gui import MainWindow
from translationzed_py.gui import main_window as mw


@pytest.fixture(autouse=True)
def _disable_close_prompt_for_module(monkeypatch):
    """Disable write-on-exit prompt in this module to speed widget teardown."""
    original_init = mw.MainWindow.__init__

    def _fast_apply_theme(self, mode: object, *, persist: bool = False) -> None:
        normalized = mw._normalize_theme_mode(mode, default=mw._THEME_SYSTEM)
        self._theme_mode = normalized
        if persist:
            self._prefs_extras["UI_THEME_MODE"] = normalized

    def _patched_init(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        original_check = mw.MainWindow._check_en_hash_cache
        try:
            mw.MainWindow._check_en_hash_cache = (  # type: ignore[assignment]
                lambda _self: True
            )
            original_init(self, *args, **kwargs)
        finally:
            mw.MainWindow._check_en_hash_cache = original_check  # type: ignore[assignment]
        if getattr(self, "_startup_aborted", False):
            return
        self._prompt_write_on_exit = False
        self._qa_auto_refresh = False
        self._tm_bootstrap_pending = False
        for name in (
            "_post_locale_timer",
            "_qa_refresh_timer",
            "_qa_scan_timer",
            "_tm_update_timer",
            "_tm_flush_timer",
            "_tm_query_timer",
            "_tm_rebuild_timer",
        ):
            timer = getattr(self, name, None)
            if timer is None:
                continue
            timer.stop()
            timer.setInterval(max(int(timer.interval()), 60_000))

    monkeypatch.setattr(mw, "_connect_system_theme_sync", lambda _callback: False)
    monkeypatch.setattr(mw.MainWindow, "_apply_theme_mode", _fast_apply_theme)
    monkeypatch.setattr(mw.MainWindow, "__init__", _patched_init)


def _make_project(tmp_path: Path) -> Path:
    """Create a minimal EN/BE project fixture."""
    root = tmp_path / "proj"
    root.mkdir()
    for locale, text in (
        ("EN", "English"),
        ("BE", "Belarusian"),
    ):
        (root / locale).mkdir()
        (root / locale / "language.txt").write_text(
            f"text = {text},\ncharset = UTF-8,\n",
            encoding="utf-8",
        )
    (root / "EN" / "ui.txt").write_text('UI_OK = "OK"\n', encoding="utf-8")
    (root / "BE" / "ui.txt").write_text('UI_OK = "Добра"\n', encoding="utf-8")
    return root


def test_post_locale_startup_and_migration_timer_helpers(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    """Verify post-locale scheduling/run branches and cache migration timer helpers."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    plan_false = SimpleNamespace(should_schedule=False)
    plan_true = SimpleNamespace(should_schedule=True)
    plans = [plan_false, plan_true, plan_true]
    calls: list[tuple[str, object]] = []
    delegate = win._project_session_service

    class _SpyService:
        def __getattr__(self, name: str):
            return getattr(delegate, name)

        def build_post_locale_startup_plan(
            self, *, selected_locales
        ):  # type: ignore[no-untyped-def]
            calls.append(("build", tuple(selected_locales)))
            return plans.pop(0)

        def run_post_locale_startup_tasks(
            self,
            *,
            plan,
            run_cache_scan,
            run_auto_open,
        ):  # type: ignore[no-untyped-def]
            calls.append(("run", bool(plan.should_schedule)))
            run_cache_scan()
            run_auto_open()
            return 2

    monkeypatch.setattr(win, "_project_session_service", _SpyService())
    executed: list[str] = []
    monkeypatch.setattr(win, "_mark_cached_dirty", lambda: executed.append("cache"))
    monkeypatch.setattr(win, "_auto_open_last_file", lambda: executed.append("open"))

    win._schedule_post_locale_tasks()
    assert win._pending_post_locale_plan is plan_false
    assert win._post_locale_timer.isActive() is False

    win._post_locale_timer.start(50)
    win._schedule_post_locale_tasks()
    assert win._pending_post_locale_plan is plan_true
    assert win._post_locale_timer.isActive() is True

    win._pending_post_locale_plan = None
    win._run_post_locale_tasks()
    assert executed == ["cache", "open"]

    executed.clear()
    win._pending_post_locale_plan = plan_false
    win._run_post_locale_tasks()
    assert executed == []

    assert win._migration_timer is None
    win._start_cache_migration_timer()
    assert win._migration_timer is not None
    assert win._migration_timer.isActive() is True
    timer_obj = win._migration_timer
    win._start_cache_migration_timer()
    assert win._migration_timer is timer_obj

    win._stop_cache_migration_timer()
    assert timer_obj.isActive() is False
    win._stop_cache_migration_timer()


def test_save_from_cache_and_tm_update_helpers_cover_error_paths(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    """Verify save-from-cache and TM update helpers cover failure and success branches."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    target = root / "BE" / "ui.txt"
    monkeypatch.setattr(win, "_can_write_originals", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(win, "_ensure_conflicts_resolved", lambda *_args: True)

    reported: list[tuple[Path, str]] = []
    monkeypatch.setattr(
        win,
        "_report_parse_error",
        lambda path, exc: reported.append((path, str(exc))),
    )

    class _ParseFailService:
        @staticmethod
        def write_from_cache(*_args, **_kwargs):  # type: ignore[no-untyped-def]
            raise mw._SaveFromCacheParseError(
                path=target,
                original=RuntimeError("parse-fail"),
            )

    monkeypatch.setattr(win, "_file_workflow_service", _ParseFailService())
    assert win._save_file_from_cache(target) is False
    assert reported == [(target, "parse-fail")]

    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr(
        mw.QMessageBox,
        "warning",
        lambda _parent, title, text: warnings.append((str(title), str(text))),
    )

    class _GenericFailService:
        @staticmethod
        def write_from_cache(*_args, **_kwargs):  # type: ignore[no-untyped-def]
            raise RuntimeError("generic-fail")

    monkeypatch.setattr(win, "_file_workflow_service", _GenericFailService())
    assert win._save_file_from_cache(target) is False
    assert warnings[-1] == ("Save failed", "generic-fail")

    dirty_calls: list[tuple[Path, bool]] = []
    monkeypatch.setattr(
        win.fs_model,
        "set_dirty",
        lambda path, dirty: dirty_calls.append((path, bool(dirty))),
    )

    class _NoDraftService:
        @staticmethod
        def write_from_cache(*_args, **_kwargs):  # type: ignore[no-untyped-def]
            return SimpleNamespace(had_drafts=False)

    monkeypatch.setattr(win, "_file_workflow_service", _NoDraftService())
    assert win._save_file_from_cache(target) is True
    assert dirty_calls == []

    queued: list[tuple[str, list[tuple[str, str, str, int]]]] = []
    pending_calls: list[dict[str, object]] = []
    flushed: list[str] = []

    class _Workflow:
        @staticmethod
        def queue_updates(file_key, rows):  # type: ignore[no-untyped-def]
            queued.append((str(file_key), list(rows)))

        @staticmethod
        def pending_batches(**kwargs):  # type: ignore[no-untyped-def]
            pending_calls.append(kwargs)
            return [
                SimpleNamespace(
                    rows=[("a", "b", "c")],
                    target_locale="BE",
                    file_key="bad",
                ),
                SimpleNamespace(
                    rows=[("x", "y", "z")],
                    target_locale="BE",
                    file_key="ok",
                ),
            ]

        @staticmethod
        def mark_batch_flushed(key):  # type: ignore[no-untyped-def]
            flushed.append(str(key))

    win._tm_workflow = _Workflow()  # type: ignore[assignment]
    rows = [("UI_OK", "src", "val", 1)]
    win._tm_store = None
    win._queue_tm_updates(target, rows)
    assert queued == []

    win._tm_store = object()  # type: ignore[assignment]
    win._tm_flush_timer.start(50)
    win._queue_tm_updates(target, rows)
    assert queued == [(str(target), rows)]
    assert win._tm_flush_timer.isActive() is True

    win._tm_store = None
    win._flush_tm_updates(paths=[target])

    warned: list[tuple[str, str]] = []
    monkeypatch.setattr(
        mw.QMessageBox,
        "warning",
        lambda _parent, title, text: warned.append((str(title), str(text))),
    )

    class _Store:
        @staticmethod
        def upsert_project_entries(
            rows,
            *,
            source_locale,
            target_locale,
            file_path,
        ):  # type: ignore[no-untyped-def]
            _ = rows
            _ = source_locale
            _ = target_locale
            if file_path == "bad":
                raise RuntimeError("tm-upsert-fail")

    win._tm_store = _Store()  # type: ignore[assignment]
    win._flush_tm_updates(paths=[target])
    assert pending_calls and pending_calls[-1]["paths"] == [str(target)]
    assert warned[-1] == ("TM update failed", "tm-upsert-fail")
    assert flushed == ["ok"]


def test_replace_helper_branches_cover_toggle_align_enable_and_request(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    """Verify replace helper methods cover toggle, align, enable, and request branches."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    calls: list[str] = []
    monkeypatch.setattr(win, "_align_replace_bar", lambda: calls.append("align"))
    monkeypatch.setattr(
        mw.QTimer,
        "singleShot",
        staticmethod(lambda _ms, callback: (calls.append("single"), callback())),
    )
    monkeypatch.setattr(
        win,
        "_update_replace_toggle_icon",
        lambda visible: calls.append(f"icon:{bool(visible)}"),
    )
    monkeypatch.setattr(win, "_update_replace_enabled", lambda: calls.append("enabled"))
    monkeypatch.setattr(win, "_update_status_bar", lambda: calls.append("status"))

    win._toggle_replace(True)
    assert win._replace_visible is True
    assert calls.count("align") == 2
    assert "single" in calls
    assert "icon:True" in calls
    calls.clear()

    win._toggle_replace(False)
    assert win._replace_visible is False
    assert "align" not in calls
    assert "icon:False" in calls
    calls.clear()

    win.replace_spacer.setFixedWidth(9)
    win.replace_toolbar.setVisible(False)
    monkeypatch.setattr(
        win, "_align_replace_bar", mw.MainWindow._align_replace_bar.__get__(win)
    )
    win._align_replace_bar()
    assert win.replace_spacer.width() == 9

    win.replace_toolbar.setVisible(True)
    monkeypatch.setattr(win.replace_toolbar, "isVisible", lambda: True, raising=False)
    monkeypatch.setattr(
        win.search_edit,
        "mapToGlobal",
        lambda _point: QPoint(120, 0),
        raising=False,
    )
    monkeypatch.setattr(
        win.replace_edit,
        "mapToGlobal",
        lambda _point: QPoint(20, 0),
        raising=False,
    )
    win._align_replace_bar()
    assert win.replace_spacer.width() == 109

    monkeypatch.setattr(
        win,
        "_update_replace_enabled",
        mw.MainWindow._update_replace_enabled.__get__(win),
    )
    win.replace_toggle.setChecked(True)
    win._current_model = None
    win.search_edit.setText("needle")
    win.search_mode.setCurrentIndex(2)
    win._update_replace_enabled()
    assert win.replace_toggle.isChecked() is False
    assert win.replace_toggle.isEnabled() is False

    win._current_model = object()  # type: ignore[assignment]
    win.search_mode.setCurrentIndex(2)
    win.search_edit.setText("needle")
    win._update_replace_enabled()
    assert win.replace_toggle.isEnabled() is True
    assert win.replace_edit.isEnabled() is True
    assert win.replace_btn.isEnabled() is True
    assert win.replace_all_btn.isEnabled() is True

    win.search_edit.setText("   ")
    win._update_replace_enabled()
    assert win.replace_edit.isEnabled() is False
    assert win.replace_btn.isEnabled() is False
    assert win.replace_all_btn.isEnabled() is False

    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr(
        mw.QMessageBox,
        "warning",
        lambda _parent, title, text: warnings.append((str(title), str(text))),
    )

    class _ErrorService:
        @staticmethod
        def build_replace_request(**_kwargs):  # type: ignore[no-untyped-def]
            raise mw._ReplaceRequestError()

    class _SuccessService:
        @staticmethod
        def build_replace_request(**_kwargs):  # type: ignore[no-untyped-def]
            return "request"

    win._search_replace_service = _ErrorService()  # type: ignore[assignment]
    assert win._prepare_replace_request() is None
    assert warnings[-1] == ("Invalid regex", "Regex pattern is invalid.")

    win._search_replace_service = _SuccessService()  # type: ignore[assignment]
    assert win._prepare_replace_request() == "request"


def test_tm_query_poll_and_show_matches_cover_timer_failure_and_accept_paths(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    """Verify TM query polling and suggestion rendering branches."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    progress_flags: list[bool] = []
    monkeypatch.setattr(
        win,
        "_set_tm_progress_visible",
        lambda visible: progress_flags.append(bool(visible)),
    )

    win._tm_query_timer.start(50)
    win._tm_query_future = None
    win._tm_rebuild_future = object()  # type: ignore[assignment]
    win._poll_tm_query()
    assert win._tm_query_timer.isActive() is False
    assert progress_flags[-1] is True

    class _PendingFuture:
        @staticmethod
        def done() -> bool:
            return False

    win._tm_query_future = _PendingFuture()  # type: ignore[assignment]
    win._tm_query_key = "k"
    win._tm_query_timer.start(50)
    win._poll_tm_query()
    assert win._tm_query_timer.isActive() is True
    assert win._tm_query_future is not None

    class _DoneFuture:
        def __init__(self, result) -> None:  # type: ignore[no-untyped-def]
            self._result = result

        @staticmethod
        def done() -> bool:
            return True

        def result(self):  # type: ignore[no-untyped-def]
            return self._result

    win._tm_query_timer.start(50)
    win._tm_query_future = _DoneFuture([])
    win._tm_query_key = None
    win._poll_tm_query()
    assert win._tm_query_future is None
    assert win._tm_query_key is None

    class _ErrorFuture:
        @staticmethod
        def done() -> bool:
            return True

        @staticmethod
        def result():  # type: ignore[no-untyped-def]
            raise RuntimeError("boom")

    win._tm_query_timer.start(50)
    win._tm_query_future = _ErrorFuture()  # type: ignore[assignment]
    win._tm_query_key = "k"
    win._poll_tm_query()
    assert win._tm_list.count() == 1
    assert win._tm_list.item(0).text() == "TM lookup failed."
    assert win._tm_apply_btn.isEnabled() is False

    shown: list[list[str]] = []
    monkeypatch.setattr(win, "_show_tm_matches", lambda matches: shown.append(matches))
    monkeypatch.setattr(win, "_current_tm_lookup", lambda: "lookup")
    monkeypatch.setattr(win, "_tm_query_policy", lambda: "policy")

    class _WorkflowDrop:
        @staticmethod
        def accept_query_result(**_kwargs):  # type: ignore[no-untyped-def]
            return False

    class _WorkflowKeep:
        @staticmethod
        def accept_query_result(**_kwargs):  # type: ignore[no-untyped-def]
            return True

    win._tm_workflow = _WorkflowDrop()  # type: ignore[assignment]
    win._tm_query_timer.start(50)
    win._tm_query_future = _DoneFuture(["m1"])
    win._tm_query_key = "k"
    win._poll_tm_query()
    assert shown == []

    win._tm_workflow = _WorkflowKeep()  # type: ignore[assignment]
    win._tm_query_timer.start(50)
    win._tm_query_future = _DoneFuture(["m2"])
    win._tm_query_key = "k"
    win._poll_tm_query()
    assert shown == [["m2"]]

    preview_calls: list[object] = []
    monkeypatch.setattr(win, "_set_tm_preview", lambda plan: preview_calls.append(plan))

    class _EmptyViewWorkflow:
        @staticmethod
        def build_suggestions_view(**_kwargs):  # type: ignore[no-untyped-def]
            return SimpleNamespace(message="No matches", items=())

        @staticmethod
        def build_selection_plan(**_kwargs):  # type: ignore[no-untyped-def]
            return "preview-plan"

    monkeypatch.setattr(
        win,
        "_show_tm_matches",
        mw.MainWindow._show_tm_matches.__get__(win),
    )
    win._tm_workflow = _EmptyViewWorkflow()  # type: ignore[assignment]
    win._show_tm_matches([])
    assert win._tm_list.count() == 1
    assert win._tm_list.item(0).text() == "No matches"
    assert win._tm_apply_btn.isEnabled() is False
    assert preview_calls == ["preview-plan"]


def test_status_combo_helpers_cover_guards_single_and_macro_paths(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    """Verify status combo update/change helpers cover guard, single-row, and macro paths."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    set_calls: list[object] = []
    monkeypatch.setattr(
        win, "_set_status_combo", lambda status: set_calls.append(status)
    )
    monkeypatch.setattr(win, "_selected_rows", lambda: [0])
    win._current_model = None
    win._update_status_combo_from_selection()
    assert set_calls[-1] is None

    class _UpdateModel:
        @staticmethod
        def status_for_row(_row: int):  # type: ignore[no-untyped-def]
            return None

    win._current_model = _UpdateModel()  # type: ignore[assignment]
    monkeypatch.setattr(win, "_selected_rows", lambda: [])
    win._update_status_combo_from_selection()
    assert set_calls[-1] is None

    status_a = win.status_combo.itemData(0)
    status_b = win.status_combo.itemData(1)

    class _UndoStack:
        def __init__(self) -> None:
            self.events: list[str] = []

        def beginMacro(self, _label: str) -> None:  # noqa: N802
            self.events.append("begin")

        def endMacro(self) -> None:  # noqa: N802
            self.events.append("end")

    class _Model:
        def __init__(self) -> None:
            self.undo_stack = _UndoStack()
            self.statuses: dict[int, object] = {}
            self.set_calls: list[tuple[int, int, object]] = []

        @staticmethod
        def index(row: int, column: int):  # type: ignore[no-untyped-def]
            return (row, column)

        def setData(self, model_index, status, _role):  # type: ignore[no-untyped-def]
            row = int(model_index[0])
            self.statuses[row] = status
            self.set_calls.append((int(model_index[0]), int(model_index[1]), status))

        def status_for_row(self, row: int):  # type: ignore[no-untyped-def]
            return self.statuses.get(row)

    model = _Model()
    win._current_model = model  # type: ignore[assignment]

    monkeypatch.setattr(win, "_selected_rows", lambda: [0, 1])
    win._update_status_combo_from_selection()
    assert set_calls[-1] is None

    monkeypatch.setattr(win.status_combo, "currentData", lambda: None, raising=False)
    win._status_combo_changed(0)
    assert model.set_calls == []

    monkeypatch.setattr(
        win.status_combo, "currentData", lambda: status_a, raising=False
    )
    monkeypatch.setattr(win, "_selected_rows", lambda: [])
    win._status_combo_changed(0)
    assert model.set_calls == []

    monkeypatch.setattr(win, "_selected_rows", lambda: [2])
    win._status_combo_changed(0)
    assert model.set_calls[-1] == (2, 3, status_a)

    model.statuses = {3: status_a, 4: status_a}
    monkeypatch.setattr(win, "_selected_rows", lambda: [3, 4])
    win._status_combo_changed(0)
    assert model.undo_stack.events == []

    model.statuses = {5: status_b, 6: status_a}
    monkeypatch.setattr(win, "_selected_rows", lambda: [5, 6])
    win._status_combo_changed(0)
    assert model.undo_stack.events == ["begin", "end"]
    assert (5, 3, status_a) in model.set_calls
    assert (6, 3, status_a) in model.set_calls


def test_selection_status_bar_and_scope_indicator_helpers_cover_guard_paths(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    """Verify selection, status bar, and scope-indicator helper branches."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    monkeypatch.setattr(win.table, "selectionModel", lambda: None, raising=False)
    assert win._selected_rows() == []

    class _Index:
        def __init__(self, row: int, valid: bool = True) -> None:
            self._row = row
            self._valid = valid

        def isValid(self) -> bool:  # noqa: N802
            return self._valid

        def row(self) -> int:
            return self._row

    class _Selection:
        @staticmethod
        def isSelected(_index) -> bool:  # noqa: N802
            return False

        @staticmethod
        def selectedRows():  # noqa: N802
            return []

        @staticmethod
        def selectedIndexes():  # noqa: N802
            return []

    monkeypatch.setattr(
        win.table, "selectionModel", lambda: _Selection(), raising=False
    )
    monkeypatch.setattr(win.table, "currentIndex", lambda: _Index(7), raising=False)
    assert win._selected_rows() == [7]

    class _FallbackSelection:
        @staticmethod
        def isSelected(_index) -> bool:  # noqa: N802
            return True

        @staticmethod
        def selectedRows():  # noqa: N802
            return []

        @staticmethod
        def selectedIndexes():  # noqa: N802
            return [_Index(2), _Index(4), _Index(2)]

    monkeypatch.setattr(
        win.table, "selectionModel", lambda: _FallbackSelection(), raising=False
    )
    monkeypatch.setattr(win.table, "currentIndex", lambda: _Index(0), raising=False)
    assert win._selected_rows() == [2, 4]

    shown_messages: list[str] = []
    monkeypatch.setattr(
        win.statusBar(),
        "showMessage",
        lambda text: shown_messages.append(str(text)),
    )
    scope_updates: list[str] = []
    monkeypatch.setattr(
        win, "_update_scope_indicators", lambda: scope_updates.append("u")
    )

    class _RowModel:
        @staticmethod
        def rowCount() -> int:  # noqa: N802
            return 11

    win._last_saved_text = "Saved 12:34:56"
    win._search_progress_text = "Searching..."
    win._current_model = _RowModel()  # type: ignore[assignment]
    monkeypatch.setattr(win.table, "currentIndex", lambda: _Index(3), raising=False)
    win._current_pf = SimpleNamespace(path=root / "BE" / "ui.txt")
    win._update_status_bar()
    assert "Saved 12:34:56" in shown_messages[-1]
    assert "Searching..." in shown_messages[-1]
    assert "Row 4 / 11" in shown_messages[-1]
    assert "BE/ui.txt" in shown_messages[-1]
    assert scope_updates[-1] == "u"

    win._current_pf = SimpleNamespace(path=Path("/tmp/external_ui.txt"))
    win._update_status_bar()
    assert "/tmp/external_ui.txt" in shown_messages[-1]

    win._last_saved_text = ""
    win._search_progress_text = ""
    win._current_model = None
    win._current_pf = None
    monkeypatch.setattr(
        win.table, "currentIndex", lambda: _Index(0, valid=False), raising=False
    )
    win._update_status_bar()
    assert shown_messages[-1] == "Ready"

    win._search_scope_widget = None
    win._replace_scope_widget = None
    win._update_scope_indicators()

    monkeypatch.setattr(
        win,
        "_update_scope_indicators",
        mw.MainWindow._update_scope_indicators.__get__(win),
    )
    win._search_scope_widget = mw.QWidget()
    win._replace_scope_widget = mw.QWidget()
    win._search_scope_icon = mw.QLabel()
    win._replace_scope_icon = mw.QLabel()
    indicator_calls: list[tuple[str, bool]] = []
    monkeypatch.setattr(
        win,
        "_set_scope_indicator",
        lambda widget, icon, scope, active, title: indicator_calls.append(  # noqa: ARG005
            (str(scope), bool(active))
        ),
    )
    win.search_edit.setText("find")
    win.replace_toolbar.setVisible(False)
    win._update_scope_indicators()
    assert indicator_calls[-2:] == [
        (win._search_scope, True),
        (win._replace_scope, False),
    ]

    monkeypatch.setattr(
        win,
        "_set_scope_indicator",
        mw.MainWindow._set_scope_indicator.__get__(win),
    )
    icon_label = mw.QLabel()
    indicator_widget = mw.QWidget()
    indicator_widget.setVisible(True)
    win._set_scope_indicator(
        indicator_widget, icon_label, "FILE", False, "Search scope"
    )
    assert indicator_widget.isVisible() is False
    win._set_scope_indicator(
        indicator_widget, icon_label, "LOCALE", True, "Replace scope"
    )
    assert indicator_widget.isVisible() is True
    assert indicator_widget.toolTip() == "Replace scope: Locale"


def test_status_apply_helpers_cover_row_filtering_and_qa_auto_mark_paths(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    """Verify status-apply helpers cover guard, row-filter, macro, and QA branches."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    win._current_model = None
    win._apply_status_to_rows([1], status=mw.Status.FOR_REVIEW, label="L")

    class _UndoStack:
        def __init__(self) -> None:
            self.events: list[str] = []

        def beginMacro(self, _label: str) -> None:  # noqa: N802
            self.events.append("begin")

        def endMacro(self) -> None:  # noqa: N802
            self.events.append("end")

    class _Model:
        def __init__(self) -> None:
            self.undo_stack = _UndoStack()
            self.statuses: dict[int, object] = {
                1: mw.Status.TRANSLATED,
                2: mw.Status.UNTOUCHED,
                3: mw.Status.PROOFREAD,
                4: mw.Status.TRANSLATED,
            }
            self.set_calls: list[tuple[int, int, object]] = []

        @staticmethod
        def index(row: int, column: int):  # type: ignore[no-untyped-def]
            return (row, column)

        def setData(self, model_index, status, _role):  # type: ignore[no-untyped-def]
            row = int(model_index[0])
            self.statuses[row] = status
            self.set_calls.append((int(model_index[0]), int(model_index[1]), status))

        def status_for_row(self, row: int):  # type: ignore[no-untyped-def]
            return self.statuses.get(row)

    model = _Model()
    win._current_model = model  # type: ignore[assignment]

    win._apply_status_to_rows([], status=mw.Status.TRANSLATED, label="L")
    assert model.set_calls == []

    win._apply_status_to_rows([-1, 1], status=mw.Status.TRANSLATED, label="L")
    assert model.set_calls == []

    win._apply_status_to_rows([2], status=mw.Status.TRANSLATED, label="single")
    assert model.set_calls[-1] == (2, 3, mw.Status.TRANSLATED)

    model.undo_stack.events.clear()
    win._apply_status_to_rows([3, 4], status=mw.Status.FOR_REVIEW, label="multi")
    assert model.undo_stack.events == ["begin", "end"]
    assert (3, 3, mw.Status.FOR_REVIEW) in model.set_calls
    assert (4, 3, mw.Status.FOR_REVIEW) in model.set_calls

    apply_calls: list[tuple[tuple[int, ...], object, str]] = []
    monkeypatch.setattr(
        win,
        "_apply_status_to_rows",
        lambda rows, *, status, label: apply_calls.append(
            (tuple(int(r) for r in rows), status, str(label))
        ),
    )

    class _QAService:
        @staticmethod
        def auto_mark_rows(_findings):  # type: ignore[no-untyped-def]
            return (1, 2, 3)

    model.statuses = {
        1: mw.Status.UNTOUCHED,
        2: mw.Status.TRANSLATED,
        3: mw.Status.PROOFREAD,
    }
    win._qa_service = _QAService()  # type: ignore[assignment]
    win._qa_auto_mark_translated_for_review = False
    win._qa_auto_mark_proofread_for_review = False
    win._apply_qa_auto_mark([object()])
    assert apply_calls[-1] == ((1,), mw.Status.FOR_REVIEW, "QA auto-mark For review")

    win._qa_auto_mark_translated_for_review = True
    win._apply_qa_auto_mark([object()])
    assert apply_calls[-1] == ((1, 2), mw.Status.FOR_REVIEW, "QA auto-mark For review")

    win._qa_auto_mark_translated_for_review = False
    win._qa_auto_mark_proofread_for_review = True
    win._apply_qa_auto_mark([object()])
    assert apply_calls[-1] == ((1, 3), mw.Status.FOR_REVIEW, "QA auto-mark For review")

    win._qa_auto_mark_translated_for_review = True
    win._qa_auto_mark_proofread_for_review = True
    win._apply_qa_auto_mark([object()])
    assert apply_calls[-1] == (
        (1, 2, 3),
        mw.Status.FOR_REVIEW,
        "QA auto-mark For review",
    )

    apply_selection_calls: list[tuple[tuple[int, ...], object, str]] = []
    combo_updates: list[str] = []
    monkeypatch.setattr(
        win,
        "_apply_status_to_rows",
        lambda rows, *, status, label: apply_selection_calls.append(
            (tuple(int(r) for r in rows), status, str(label))
        ),
    )
    monkeypatch.setattr(
        win,
        "_update_status_combo_from_selection",
        lambda: combo_updates.append("u"),
    )

    win._current_pf = None
    win._apply_status_to_selection(mw.Status.PROOFREAD, "label")
    assert apply_selection_calls == []

    win._current_pf = SimpleNamespace(path=root / "BE" / "ui.txt")
    monkeypatch.setattr(win, "_selected_rows", lambda: [])
    win._apply_status_to_selection(mw.Status.PROOFREAD, "label")
    assert apply_selection_calls == []

    monkeypatch.setattr(win, "_selected_rows", lambda: [4, 5])
    win._apply_status_to_selection(mw.Status.PROOFREAD, "label")
    assert apply_selection_calls[-1] == ((4, 5), mw.Status.PROOFREAD, "label")
    assert combo_updates == ["u"]

    # Keep teardown closeEvent on real-safe state.
    win._current_model = None
    win._current_pf = None


def test_show_resize_and_set_status_combo_helpers_cover_remaining_ui_branches(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    """Verify show/resize handlers and status-combo setter edge paths."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    toggle_calls: list[bool] = []
    monkeypatch.setattr(
        win,
        "_toggle_detail_panel",
        lambda checked: toggle_calls.append(bool(checked)),
    )
    monkeypatch.setattr(win._detail_panel, "isVisible", lambda: True, raising=False)
    win.showEvent(QShowEvent())
    assert toggle_calls == [True]

    layout_calls: list[str] = []
    reflow_calls: list[str] = []
    align_calls: list[str] = []
    monkeypatch.setattr(
        win, "_apply_table_layout", lambda: layout_calls.append("layout")
    )
    monkeypatch.setattr(
        win, "_schedule_resize_reflow", lambda: reflow_calls.append("reflow")
    )
    monkeypatch.setattr(win, "_align_replace_bar", lambda: align_calls.append("align"))

    target = root / "BE" / "ui.txt"
    index = win.fs_model.index_for_path(target)
    win._file_chosen(index)
    layout_calls.clear()
    reflow_calls.clear()
    align_calls.clear()
    win.replace_toolbar.setVisible(True)
    monkeypatch.setattr(win.replace_toolbar, "isVisible", lambda: True, raising=False)
    win.resizeEvent(QResizeEvent(QSize(1200, 800), QSize(1000, 700)))
    assert layout_calls == ["layout"]
    assert reflow_calls == ["reflow"]
    assert align_calls == ["align"]

    monkeypatch.setattr(win, "_selected_rows", lambda: [])
    win._set_status_combo(None)
    assert win.status_combo.isEnabled() is False
    assert win.status_combo.currentIndex() == -1

    monkeypatch.setattr(win, "_selected_rows", lambda: [0])
    win._set_status_combo(None)
    assert win.status_combo.isEnabled() is True
    assert win.status_combo.currentIndex() == -1

    known_status = win.status_combo.itemData(0)
    win._set_status_combo(known_status)
    assert win.status_combo.currentData() == known_status

    win._set_status_combo(object())  # type: ignore[arg-type]
    assert win.status_combo.currentIndex() == -1


def test_show_tm_matches_and_show_resize_guard_paths(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    """Verify TM/show/resize helpers cover fallback and non-visible guard branches."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    preview_calls: list[object] = []
    monkeypatch.setattr(win, "_set_tm_preview", lambda plan: preview_calls.append(plan))

    class _Workflow:
        @staticmethod
        def build_suggestions_view(**_kwargs):  # type: ignore[no-untyped-def]
            return SimpleNamespace(
                message="Has candidate",
                items=[
                    SimpleNamespace(label="item", match="m", tooltip_html="<b>x</b>"),
                ],
            )

        @staticmethod
        def build_selection_plan(**_kwargs):  # type: ignore[no-untyped-def]
            return "fallback-preview"

    monkeypatch.setattr(win._tm_list, "addItem", lambda _item: None, raising=False)
    monkeypatch.setattr(win, "_tm_query_policy", lambda: object())
    win._tm_workflow = _Workflow()  # type: ignore[assignment]
    win._show_tm_matches([])
    assert win._tm_list.count() == 1
    assert win._tm_list.item(0).text() == "Has candidate"
    assert win._tm_apply_btn.isEnabled() is False
    assert preview_calls == ["fallback-preview"]

    toggle_calls: list[bool] = []
    monkeypatch.setattr(
        win,
        "_toggle_detail_panel",
        lambda checked: toggle_calls.append(bool(checked)),
    )
    monkeypatch.setattr(win._detail_panel, "isVisible", lambda: False, raising=False)
    win.showEvent(QShowEvent())
    assert toggle_calls == []

    layout_calls: list[str] = []
    reflow_calls: list[str] = []
    align_calls: list[str] = []
    monkeypatch.setattr(
        win, "_apply_table_layout", lambda: layout_calls.append("layout")
    )
    monkeypatch.setattr(
        win, "_schedule_resize_reflow", lambda: reflow_calls.append("reflow")
    )
    monkeypatch.setattr(win, "_align_replace_bar", lambda: align_calls.append("align"))
    monkeypatch.setattr(win.table, "model", lambda: None, raising=False)
    monkeypatch.setattr(win.replace_toolbar, "isVisible", lambda: False, raising=False)
    win.resizeEvent(QResizeEvent(QSize(900, 700), QSize(800, 600)))
    assert layout_calls == []
    assert reflow_calls == ["reflow"]
    assert align_calls == []


def test_update_status_combo_from_selection_handles_single_and_mixed_statuses(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    """Verify status-combo update helper sets single status or clears on mixed selection."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    status_calls: list[object] = []
    monkeypatch.setattr(
        win, "_set_status_combo", lambda status: status_calls.append(status)
    )

    status_a = win.status_combo.itemData(0)
    status_b = win.status_combo.itemData(1)

    class _Model:
        statuses = {
            1: status_a,
            2: status_a,
            3: status_b,
            4: None,
        }

        @classmethod
        def status_for_row(cls, row: int):  # type: ignore[no-untyped-def]
            return cls.statuses.get(row)

    win._current_model = _Model()  # type: ignore[assignment]
    monkeypatch.setattr(win, "_selected_rows", lambda: [1, 2])
    win._update_status_combo_from_selection()
    assert status_calls[-1] == status_a

    monkeypatch.setattr(win, "_selected_rows", lambda: [3, 4])
    win._update_status_combo_from_selection()
    assert status_calls[-1] == status_b

    monkeypatch.setattr(win, "_selected_rows", lambda: [1, 3])
    win._update_status_combo_from_selection()
    assert status_calls[-1] is None

    win._current_model = None
