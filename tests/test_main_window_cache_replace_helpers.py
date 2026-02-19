"""Test module for main-window cache and replace helper branches."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint

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
    monkeypatch.setattr(win, "_align_replace_bar", mw.MainWindow._align_replace_bar.__get__(win))
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
