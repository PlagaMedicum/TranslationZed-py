"""Test module for gui service adapters."""

import re
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidgetItem

from translationzed_py.core.conflict_service import (
    ConflictMergeExecution,
    ConflictPromptPlan,
    ConflictResolution,
)
from translationzed_py.core.save_exit_flow import SaveBatchOutcome
from translationzed_py.core.search import Match
from translationzed_py.core.search_replace_service import (
    ReplaceAllFileApplyResult,
    ReplaceAllRowsApplyResult,
    ReplaceRequest,
    SearchMatchApplyPlan,
    SearchMatchOpenPlan,
    SearchRowsBuildResult,
    SearchRowsCacheKey,
    SearchRowsCacheLookupPlan,
    SearchRowsCacheStamp,
    SearchRowsCacheStorePlan,
    SearchRowsSourcePlan,
    SearchRunPlan,
)
from translationzed_py.core.tm_import_sync import TMImportSyncReport
from translationzed_py.core.tm_preferences import TMPreferencesApplyReport
from translationzed_py.core.tm_rebuild import TMRebuildResult
from translationzed_py.gui import MainWindow
from translationzed_py.gui import main_window as mw


def _make_project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    for locale, text in (
        ("EN", "English"),
        ("BE", "Belarusian"),
        ("RU", "Russian"),
    ):
        (root / locale).mkdir()
        (root / locale / "language.txt").write_text(
            f"text = {text},\ncharset = UTF-8,\n", encoding="utf-8"
        )
    (root / "EN" / "ui.txt").write_text('UI_OK = "OK"\n', encoding="utf-8")
    (root / "BE" / "ui.txt").write_text('UI_OK = "Добра"\n', encoding="utf-8")
    (root / "RU" / "ui.txt").write_text('UI_OK = "Хорошо"\n', encoding="utf-8")
    return root


def test_open_file_delegates_to_file_workflow_service(qtbot, tmp_path, monkeypatch):
    """Verify open file delegates to file workflow service."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    target = root / "BE" / "ui.txt"
    index = win.fs_model.index_for_path(target)

    calls: list[tuple[Path, str]] = []
    delegate = win._file_workflow_service

    class _SpyService:
        def __getattr__(self, name: str):
            return getattr(delegate, name)

        def prepare_open_file(self, path: Path, encoding: str, **kwargs):  # type: ignore[no-untyped-def]
            calls.append((path, encoding))
            return delegate.prepare_open_file(path, encoding, **kwargs)

    monkeypatch.setattr(win, "_file_workflow_service", _SpyService())
    win._file_chosen(index)
    assert calls == [(target, "UTF-8")]


def test_switch_locales_delegates_to_project_session_service(
    qtbot, tmp_path, monkeypatch
):
    """Verify switch locales delegates to project session service."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    class _FakeDialog:
        class DialogCode:
            Accepted = 1

        def __init__(self, *_args, **_kwargs):
            pass

        def exec(self) -> int:
            return self.DialogCode.Accepted

        def selected_codes(self) -> list[str]:
            return ["RU"]

    calls: list[tuple[tuple[str, ...], tuple[str, ...]]] = []
    delegate = win._project_session_service

    class _SpyService:
        def __getattr__(self, name: str):
            return getattr(delegate, name)

        def build_locale_switch_plan(
            self,
            *,
            requested_locales,
            available_locales,
            current_locales,
        ):  # type: ignore[no-untyped-def]
            calls.append((tuple(requested_locales), tuple(current_locales)))
            return delegate.build_locale_switch_plan(
                requested_locales=requested_locales,
                available_locales=available_locales,
                current_locales=current_locales,
            )

    monkeypatch.setattr(mw, "LocaleChooserDialog", _FakeDialog)
    monkeypatch.setattr(win, "_project_session_service", _SpyService())
    assert win._selected_locales == ["BE"]
    win._switch_locales()
    assert calls == [(("RU",), ("BE",))]
    assert win._selected_locales == ["RU"]


def test_warn_orphan_caches_delegates_warning_plan_to_project_session(
    qtbot, tmp_path, monkeypatch
):
    """Verify warn orphan caches delegates warning plan to project session."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    orphan = root / ".tzp" / "cache" / "BE" / "ghost.bin"

    calls: list[tuple[str, tuple[Path, ...], Path, int]] = []
    delegate = win._project_session_service

    class _SpyService:
        def __getattr__(self, name: str):
            return getattr(delegate, name)

        def collect_orphan_cache_paths(
            self,
            *,
            root,
            selected_locales,
            warned_locales,
        ):  # type: ignore[no-untyped-def]
            return {"BE": [orphan]}

        def build_orphan_cache_warning(
            self,
            *,
            locale,
            orphan_paths,
            root,
            preview_limit=20,
        ):  # type: ignore[no-untyped-def]
            calls.append((locale, tuple(orphan_paths), root, preview_limit))
            return delegate.build_orphan_cache_warning(
                locale=locale,
                orphan_paths=orphan_paths,
                root=root,
                preview_limit=preview_limit,
            )

    class _FakeMessageBox:
        Warning = 1
        AcceptRole = 2
        RejectRole = 3
        _instances: list["_FakeMessageBox"] = []

        def __init__(self, *_args, **_kwargs):
            self._title = ""
            self._text = ""
            self._info = ""
            self._detail = ""
            self._clicked = None
            _FakeMessageBox._instances.append(self)

        def setIcon(self, _icon):
            return None

        def setWindowTitle(self, title):
            self._title = title

        def setText(self, text):
            self._text = text

        def setInformativeText(self, text):
            self._info = text

        def setDetailedText(self, text):
            self._detail = text

        def addButton(self, _label, _role):
            btn = object()
            self._clicked = btn
            return btn

        def exec(self):
            return None

        def clickedButton(self):
            return self._clicked

    monkeypatch.setattr(win, "_project_session_service", _SpyService())
    monkeypatch.setattr(mw, "QMessageBox", _FakeMessageBox)
    win._warn_orphan_caches()

    assert calls == [("BE", (orphan,), root, 20)]
    assert _FakeMessageBox._instances
    assert _FakeMessageBox._instances[0]._title == "Orphan cache files"
    assert _FakeMessageBox._instances[0]._text.startswith("Locale BE has cache files")


def test_schedule_cache_migration_delegates_execution_to_project_session(
    qtbot, tmp_path, monkeypatch
):
    """Verify schedule cache migration delegates execution to project session."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    legacy = root / ".tzp-cache" / "BE" / "legacy.bin"

    calls: list[tuple[tuple[Path, ...], int, int]] = []
    delegate = win._project_session_service

    class _SpyService:
        def __getattr__(self, name: str):
            return getattr(delegate, name)

        def execute_cache_migration_schedule(
            self,
            *,
            legacy_paths,
            batch_size,
            migrated_count,
            callbacks,
        ):  # type: ignore[no-untyped-def]
            calls.append((tuple(legacy_paths), batch_size, migrated_count))
            return delegate.execute_cache_migration_schedule(
                legacy_paths=legacy_paths,
                batch_size=batch_size,
                migrated_count=migrated_count,
                callbacks=callbacks,
            )

    monkeypatch.setattr(win, "_project_session_service", _SpyService())
    monkeypatch.setattr(mw, "_legacy_cache_paths", lambda _root: [legacy])
    monkeypatch.setattr(mw, "_migrate_status_caches", lambda _root, _locales: 0)
    win._schedule_cache_migration()

    assert calls == [((legacy,), win._migration_batch_size, 0)]


def test_run_cache_migration_batch_delegates_execution_to_project_session(
    qtbot, tmp_path, monkeypatch
):
    """Verify run cache migration batch delegates execution to project session."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    pending = root / ".tzp-cache" / "BE" / "legacy.bin"
    win._pending_cache_migrations = [pending]
    win._migration_count = 1

    calls: list[tuple[tuple[Path, ...], int, int]] = []
    delegate = win._project_session_service

    class _SpyService:
        def __getattr__(self, name: str):
            return getattr(delegate, name)

        def execute_cache_migration_batch(
            self,
            *,
            pending_paths,
            batch_size,
            migrated_count,
            callbacks,
        ):  # type: ignore[no-untyped-def]
            calls.append((tuple(pending_paths), batch_size, migrated_count))
            return delegate.execute_cache_migration_batch(
                pending_paths=pending_paths,
                batch_size=batch_size,
                migrated_count=migrated_count,
                callbacks=callbacks,
            )

    monkeypatch.setattr(win, "_project_session_service", _SpyService())
    monkeypatch.setattr(
        mw,
        "_migrate_status_cache_paths",
        lambda _root, _locales, paths: len(paths),
    )
    win._run_cache_migration_batch()

    assert calls == [((pending,), win._migration_batch_size, 1)]


def test_save_all_files_delegates_to_save_batch_flow(qtbot, tmp_path, monkeypatch):
    """Verify save all files delegates to save batch flow."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    target = root / "BE" / "ui.txt"

    calls: dict[str, object] = {}
    saved_status: list[bool] = []
    delegate = win._save_exit_flow_service

    class _SpyService:
        def __getattr__(self, name: str):
            return getattr(delegate, name)

        def run_save_batch_flow(
            self,
            *,
            files,
            current_file,
            save_current,
            save_from_cache,
        ):  # type: ignore[no-untyped-def]
            calls["files"] = tuple(files)
            calls["current_file"] = current_file
            calls["save_current"] = save_current
            calls["save_from_cache"] = save_from_cache
            return SaveBatchOutcome(aborted=False, failures=(), saved_any=True)

    monkeypatch.setattr(win, "_save_exit_flow_service", _SpyService())
    monkeypatch.setattr(win, "_can_write_originals", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(win, "_set_saved_status", lambda: saved_status.append(True))

    win._save_all_files([target])
    assert calls["files"] == (target,)
    assert calls["save_current"] == win._save_current
    assert calls["save_from_cache"] == win._save_file_from_cache
    assert saved_status == [True]


def test_request_write_original_delegates_to_save_exit_flow_service(
    qtbot, tmp_path, monkeypatch
):
    """Verify request write original delegates to save exit flow service."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    calls: list[dict[str, object]] = []
    delegate = win._save_exit_flow_service

    class _SpyService:
        def __getattr__(self, name: str):
            return getattr(delegate, name)

        def apply_write_original_flow(self, **kwargs):  # type: ignore[no-untyped-def]
            calls.append(kwargs)
            return None

    monkeypatch.setattr(win, "_save_exit_flow_service", _SpyService())
    monkeypatch.setattr(win, "_can_write_originals", lambda *_args, **_kwargs: True)
    win._request_write_original()
    assert calls
    assert calls[0]["write_cache"] == win._write_cache_current
    assert calls[0]["save_all"] == win._save_all_files


def test_request_write_original_skips_flow_when_guard_blocks(
    qtbot, tmp_path, monkeypatch
) -> None:
    """Verify write-original flow is not invoked when write guard rejects the action."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    called: list[str] = []
    delegate = win._save_exit_flow_service

    class _StubService:
        def __getattr__(self, name: str):
            return getattr(delegate, name)

        def apply_write_original_flow(self, **_kwargs):  # type: ignore[no-untyped-def]
            called.append("flow")

    monkeypatch.setattr(win, "_save_exit_flow_service", _StubService())
    monkeypatch.setattr(win, "_can_write_originals", lambda *_args, **_kwargs: False)
    win._request_write_original()
    assert called == []


def test_open_flow_guard_restores_depth_after_nested_and_exception(
    qtbot, tmp_path
) -> None:
    """Verify open-flow guard increments depth and always restores it."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    assert win._open_flow_depth == 0
    with win._open_flow_guard():
        assert win._open_flow_depth == 1
        with win._open_flow_guard():
            assert win._open_flow_depth == 2
        assert win._open_flow_depth == 1
    assert win._open_flow_depth == 0

    with pytest.raises(RuntimeError, match="boom"):
        with win._open_flow_guard():
            assert win._open_flow_depth == 1
            raise RuntimeError("boom")
    assert win._open_flow_depth == 0


def test_can_write_originals_warns_when_read_flow_is_active(
    qtbot, tmp_path, monkeypatch
) -> None:
    """Verify write guard warns and blocks while open/read flow is active."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr(
        mw.QMessageBox,
        "warning",
        lambda _parent, title, text: warnings.append((str(title), str(text))),
    )

    win._open_flow_depth = 1
    assert win._can_write_originals("save now") is False
    assert warnings == [
        ("Operation blocked", "Cannot save now while file open/read flow is active.")
    ]

    win._open_flow_depth = 0
    assert win._can_write_originals("save now") is True


def test_notify_nothing_to_write_shows_information_dialog(
    qtbot, tmp_path, monkeypatch
) -> None:
    """Verify helper shows the expected informational dialog for empty draft set."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    infos: list[tuple[str, str]] = []
    monkeypatch.setattr(
        mw.QMessageBox,
        "information",
        lambda _parent, title, text: infos.append((str(title), str(text))),
    )
    win._notify_nothing_to_write()
    assert infos == [("Nothing to write", "No draft changes to write.")]


def test_show_save_files_dialog_returns_non_write_without_mutating_files(
    qtbot, tmp_path, monkeypatch
) -> None:
    """Verify save-files dialog returns early for non-write decisions."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    files = [root / "BE" / "ui.txt", root / "BE" / "menu.txt"]
    before = list(files)

    calls: list[tuple[str, object]] = []
    delegate = win._save_exit_flow_service

    class _StubService:
        def __getattr__(self, name: str):
            return getattr(delegate, name)

        def build_save_dialog_labels(self, items, *, root):  # type: ignore[no-untyped-def]
            calls.append(("labels", tuple(items)))
            return [p.relative_to(root).as_posix() for p in items]

        def apply_save_dialog_selection(self, **_kwargs):  # type: ignore[no-untyped-def]
            calls.append(("apply", _kwargs))
            return ()

    class _Dialog:
        def __init__(self, labels, *_args, **_kwargs):
            calls.append(("dialog_labels", tuple(labels)))

        def exec(self):
            return None

        def choice(self):
            return "cache"

    monkeypatch.setattr(win, "_save_exit_flow_service", _StubService())
    monkeypatch.setattr(mw, "SaveFilesDialog", _Dialog)
    decision = win._show_save_files_dialog(files)

    assert decision == "cache"
    assert files == before
    assert not any(kind == "apply" for kind, _ in calls)


def test_show_save_files_dialog_write_without_selected_files_uses_none(
    qtbot, tmp_path, monkeypatch
) -> None:
    """Verify write decision passes selected_labels=None when dialog omits selected_files hook."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    files = [root / "BE" / "ui.txt", root / "BE" / "menu.txt"]
    selected_seen: list[object] = []
    delegate = win._save_exit_flow_service

    class _StubService:
        def __getattr__(self, name: str):
            return getattr(delegate, name)

        def build_save_dialog_labels(self, items, *, root):  # type: ignore[no-untyped-def]
            return [p.relative_to(root).as_posix() for p in items]

        def apply_save_dialog_selection(
            self, *, files, labels, selected_labels
        ):  # type: ignore[no-untyped-def]
            _ = files
            _ = labels
            selected_seen.append(selected_labels)
            return (root / "BE" / "menu.txt",)

    class _Dialog:
        def __init__(self, *_args, **_kwargs):
            pass

        def exec(self):
            return None

        def choice(self):
            return "write"

    monkeypatch.setattr(win, "_save_exit_flow_service", _StubService())
    monkeypatch.setattr(mw, "SaveFilesDialog", _Dialog)
    decision = win._show_save_files_dialog(files)

    assert decision == "write"
    assert selected_seen == [None]
    assert files == [root / "BE" / "menu.txt"]


def test_apply_preferences_delegates_scope_normalization_to_preferences_service(
    qtbot, tmp_path, monkeypatch
):
    """Verify expected behavior."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    calls: list[tuple[object, str]] = []
    delegate = win._preferences_service

    class _SpyService:
        def __getattr__(self, name: str):
            return getattr(delegate, name)

        def normalize_scope(self, value: object, *, default: str = "FILE") -> str:
            calls.append((value, default))
            if str(value).lower() == "locale":
                return "LOCALE"
            return "POOL"

    monkeypatch.setattr(win, "_preferences_service", _SpyService())
    monkeypatch.setattr(win, "_apply_tm_preferences_actions", lambda _values: None)
    monkeypatch.setattr(win, "_persist_preferences", lambda: None)
    monkeypatch.setattr(win, "_update_replace_enabled", lambda: None)
    monkeypatch.setattr(win, "_update_status_bar", lambda: None)

    win._apply_preferences(
        {
            "search_scope": "locale",
            "replace_scope": "pool",
            "default_root": "",
            "tm_import_dir": "",
        }
    )

    assert calls == [("locale", "FILE"), ("pool", "FILE")]
    assert win._search_scope == "LOCALE"
    assert win._replace_scope == "POOL"


def test_apply_tm_preferences_actions_delegates_to_tm_workflow_service(
    qtbot, tmp_path, monkeypatch
):
    """Verify apply tm preferences actions delegates to tm workflow service."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    class _Actions:
        remove_paths: set[str] = set()

        @staticmethod
        def is_empty() -> bool:
            return False

    calls: dict[str, object] = {}
    delegate = win._tm_workflow

    class _SpyService:
        def __getattr__(self, name: str):
            return getattr(delegate, name)

        def build_preferences_actions(self, values):  # type: ignore[no-untyped-def]
            calls["values"] = values
            return _Actions()

        def apply_preferences_actions(  # type: ignore[no-untyped-def]
            self,
            *,
            store,
            actions,
            copy_to_import_dir,
        ):
            calls["store"] = store
            calls["actions"] = actions
            calls["copy_to_import_dir"] = copy_to_import_dir
            return TMPreferencesApplyReport(sync_paths=(), failures=())

    monkeypatch.setattr(win, "_tm_workflow", _SpyService())
    monkeypatch.setattr(win, "_ensure_tm_store", lambda: True)
    win._tm_store = object()  # type: ignore[assignment]

    win._apply_tm_preferences_actions({"tm_import_paths": ["/tmp/sample.tmx"]})

    assert calls["values"] == {"tm_import_paths": ["/tmp/sample.tmx"]}
    assert calls["store"] is win._tm_store
    assert calls["actions"].is_empty() is False
    assert callable(calls["copy_to_import_dir"])


def test_sync_tm_import_folder_delegates_to_tm_workflow_service(
    qtbot, tmp_path, monkeypatch
):
    """Verify sync tm import folder delegates to tm workflow service."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    tm_dir = tmp_path / "tm-imports"
    calls: dict[str, object] = {}
    applied: list[tuple[TMImportSyncReport, bool, bool]] = []
    delegate = win._tm_workflow

    class _SpyService:
        def __getattr__(self, name: str):
            return getattr(delegate, name)

        def sync_import_folder(  # type: ignore[no-untyped-def]
            self,
            *,
            store,
            tm_dir,
            resolve_locales,
            only_paths=None,
            pending_only=False,
        ):
            calls["store"] = store
            calls["tm_dir"] = tm_dir
            calls["resolve_locales"] = resolve_locales
            calls["only_paths"] = only_paths
            calls["pending_only"] = pending_only
            return TMImportSyncReport(
                imported_segments=0,
                imported_files=(),
                unresolved_files=(),
                zero_segment_files=(),
                failures=(),
                checked_files=(),
                changed=False,
            )

    monkeypatch.setattr(win, "_tm_workflow", _SpyService())
    monkeypatch.setattr(win, "_ensure_tm_store", lambda: True)
    monkeypatch.setattr(win, "_tm_import_dir_path", lambda: tm_dir)
    monkeypatch.setattr(
        win,
        "_apply_tm_sync_report",
        lambda report, *, interactive, show_summary: applied.append(
            (report, interactive, show_summary)
        ),
    )
    win._tm_store = object()  # type: ignore[assignment]
    only = {tmp_path / "sample.tmx"}

    win._sync_tm_import_folder(
        interactive=False,
        only_paths=only,
        pending_only=True,
        show_summary=True,
    )

    assert calls["store"] is win._tm_store
    assert calls["tm_dir"] == tm_dir
    assert calls["only_paths"] == only
    assert calls["pending_only"] is True
    assert callable(calls["resolve_locales"])
    assert len(applied) == 1
    assert applied[0][1:] == (False, True)


def test_start_tm_rebuild_delegates_collect_locales_to_tm_workflow_service(
    qtbot, tmp_path, monkeypatch
):
    """Verify expected behavior."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    win._tm_store = object()  # type: ignore[assignment]

    calls: list[tuple[object, object]] = []
    delegate = win._tm_workflow

    class _SpyService:
        def __getattr__(self, name: str):
            return getattr(delegate, name)

        def collect_rebuild_locales(  # type: ignore[no-untyped-def]
            self, *, locale_map, selected_locales
        ):
            calls.append((locale_map, selected_locales))
            return ([], "utf-8")

    monkeypatch.setattr(win, "_tm_workflow", _SpyService())
    win._start_tm_rebuild(["BE"], interactive=False, force=False)

    assert len(calls) == 1
    assert calls[0][0] is win._locales
    assert calls[0][1] == ["BE"]


def test_start_tm_rebuild_submits_tm_rebuild_via_tm_workflow_service(
    qtbot, tmp_path, monkeypatch
):
    """Verify start tm rebuild submits tm rebuild via tm workflow service."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    win._tm_store = object()  # type: ignore[assignment]

    class _Spec:
        locale = "BE"

    submitted: dict[str, object] = {}

    class _FakeFuture:
        def done(self) -> bool:
            return False

    class _FakePool:
        def submit(self, fn, *args, **kwargs):  # type: ignore[no-untyped-def]
            submitted["fn"] = fn
            submitted["args"] = args
            submitted["kwargs"] = kwargs
            return _FakeFuture()

    delegate = win._tm_workflow

    class _SpyService:
        def __getattr__(self, name: str):
            return getattr(delegate, name)

        def collect_rebuild_locales(  # type: ignore[no-untyped-def]
            self, *, locale_map, selected_locales
        ):
            _ = locale_map
            _ = selected_locales
            return ([_Spec()], "utf-8")

        def rebuild_project_tm(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            _ = args
            _ = kwargs
            return None

    monkeypatch.setattr(win, "_tm_workflow", _SpyService())
    win._tm_rebuild_pool = _FakePool()  # type: ignore[assignment]
    win._start_tm_rebuild(["BE"], interactive=False, force=False)

    assert submitted["fn"] == win._tm_workflow.rebuild_project_tm
    assert submitted["args"][0] == win._root
    assert submitted["kwargs"]["source_locale"] == win._tm_source_locale
    assert submitted["kwargs"]["en_encoding"] == "utf-8"


def test_finish_tm_rebuild_delegates_status_formatting_to_tm_workflow_service(
    qtbot, tmp_path, monkeypatch
):
    """Verify expected behavior."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    calls: list[tuple[str, object]] = []
    delegate = win._tm_workflow

    class _SpyService:
        def __getattr__(self, name: str):
            return getattr(delegate, name)

        def clear_cache(self) -> None:
            calls.append(("clear_cache", None))

        def format_rebuild_status(self, result: TMRebuildResult) -> str:
            calls.append(("format", result))
            return "rebuilt"

    shown: list[tuple[str, int]] = []
    monkeypatch.setattr(win, "_tm_workflow", _SpyService())
    monkeypatch.setattr(
        win.statusBar(),
        "showMessage",
        lambda text, ms=0: shown.append((text, ms)),
    )
    result = TMRebuildResult(files=1, entries=2)
    win._finish_tm_rebuild(result)

    assert calls == [("clear_cache", None), ("format", result)]
    assert shown == [("rebuilt", 8000)]


def test_save_all_files_delegates_to_save_batch_render_plan(
    qtbot, tmp_path, monkeypatch
):
    """Verify save all files delegates to save batch render plan."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    target = root / "BE" / "ui.txt"

    rendered: dict[str, object] = {}
    saved_status: list[bool] = []
    delegate = win._save_exit_flow_service

    class _SpyService:
        def __getattr__(self, name: str):
            return getattr(delegate, name)

        def run_save_batch_flow(
            self,
            *,
            files,
            current_file,
            save_current,
            save_from_cache,
        ):  # type: ignore[no-untyped-def]
            return SaveBatchOutcome(aborted=False, failures=(), saved_any=True)

        def build_save_batch_render_plan(
            self,
            *,
            outcome,
            root,
        ):  # type: ignore[no-untyped-def]
            rendered["outcome"] = outcome
            rendered["root"] = root

            class _Plan:
                aborted = False
                warning_message = None
                set_saved_status = True

            return _Plan()

    monkeypatch.setattr(win, "_save_exit_flow_service", _SpyService())
    monkeypatch.setattr(win, "_can_write_originals", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(win, "_set_saved_status", lambda: saved_status.append(True))

    win._save_all_files([target])

    assert isinstance(rendered["outcome"], SaveBatchOutcome)
    assert rendered["root"] == root
    assert saved_status == [True]


def test_save_file_from_cache_delegates_to_file_workflow_service(
    qtbot, tmp_path, monkeypatch
):
    """Verify save file from cache delegates to file workflow service."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    target = root / "BE" / "ui.txt"

    calls: dict[str, object] = {}

    class _SpyService:
        def __getattr__(self, name: str):
            return getattr(delegate, name)

        def write_from_cache(
            self,
            path: Path,
            encoding: str,
            *,
            cache_map,
            callbacks,
            hash_for_entry,
        ):  # type: ignore[no-untyped-def]
            calls["path"] = path
            calls["encoding"] = encoding
            calls["cache_map"] = cache_map
            calls["callbacks"] = callbacks
            calls["hash_for_entry"] = hash_for_entry
            return delegate.write_from_cache(
                path,
                encoding,
                cache_map=cache_map,
                callbacks=callbacks,
                hash_for_entry=hash_for_entry,
            )

    delegate = win._file_workflow_service
    monkeypatch.setattr(win, "_file_workflow_service", _SpyService())
    monkeypatch.setattr(win, "_can_write_originals", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(win, "_ensure_conflicts_resolved", lambda *_args: True)
    assert win._save_file_from_cache(target) is True
    assert calls["path"] == target
    assert calls["encoding"] == "UTF-8"
    assert "callbacks" in calls


def test_save_current_delegates_to_file_workflow_service(qtbot, tmp_path, monkeypatch):
    """Verify save current delegates to file workflow service."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    target = root / "BE" / "ui.txt"
    index = win.fs_model.index_for_path(target)
    win._file_chosen(index)
    assert win._current_model is not None
    value_idx = win._current_model.index(0, 2)
    win._current_model.setData(value_idx, "New value", Qt.EditRole)

    run_calls: list[tuple[bool, bool]] = []
    persist_calls: list[Path] = []
    delegate = win._file_workflow_service

    class _SpyService:
        def __getattr__(self, name: str):
            return getattr(delegate, name)

        def build_save_current_run_plan(
            self,
            *,
            has_current_file: bool,
            has_current_model: bool,
            conflicts_resolved: bool,
            has_changed_keys: bool,
        ):  # type: ignore[no-untyped-def]
            run_calls.append((conflicts_resolved, has_changed_keys))
            return delegate.build_save_current_run_plan(
                has_current_file=has_current_file,
                has_current_model=has_current_model,
                conflicts_resolved=conflicts_resolved,
                has_changed_keys=has_changed_keys,
            )

        def persist_current_save(
            self,
            *,
            path: Path,
            parsed_file,
            changed_values,
            encoding: str,
            callbacks,
        ):  # type: ignore[no-untyped-def]
            _ = parsed_file
            _ = changed_values
            _ = encoding
            _ = callbacks
            persist_calls.append(path)
            return delegate.persist_current_save(
                path=path,
                parsed_file=win._current_pf,
                changed_values=win._current_model.changed_values(),  # type: ignore[arg-type]
                encoding=win._current_encoding,
                callbacks=callbacks,
            )

    monkeypatch.setattr(win, "_file_workflow_service", _SpyService())
    monkeypatch.setattr(win, "_can_write_originals", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(win, "_ensure_conflicts_resolved", lambda *_args: True)
    assert win._save_current() is True
    assert run_calls
    assert run_calls[0][0] is True
    assert run_calls[0][1] is True
    assert persist_calls == [target]


def test_save_current_returns_false_when_write_is_blocked(
    qtbot, tmp_path, monkeypatch
) -> None:
    """Verify save current exits early when original writes are blocked."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    calls: list[str] = []
    monkeypatch.setattr(win, "_can_write_originals", lambda *_args, **_kwargs: False)

    class _StubService:
        @staticmethod
        def build_save_current_run_plan(**_kwargs):  # type: ignore[no-untyped-def]
            calls.append("plan")
            return SimpleNamespace(immediate_result=False, run_save=False)

    monkeypatch.setattr(win, "_file_workflow_service", _StubService())
    assert win._save_current() is False
    assert calls == []


def test_save_current_returns_immediate_result_from_run_plan(
    qtbot, tmp_path, monkeypatch
) -> None:
    """Verify save current returns immediate run-plan result without persistence."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    monkeypatch.setattr(win, "_can_write_originals", lambda *_args, **_kwargs: True)
    plan_box: dict[str, object] = {
        "plan": SimpleNamespace(immediate_result=True, run_save=False)
    }

    class _StubService:
        @staticmethod
        def build_save_current_run_plan(**_kwargs):  # type: ignore[no-untyped-def]
            return plan_box["plan"]

    monkeypatch.setattr(win, "_file_workflow_service", _StubService())
    assert win._save_current() is True

    plan_box["plan"] = SimpleNamespace(immediate_result=False, run_save=False)
    assert win._save_current() is False


def test_save_current_returns_false_when_run_plan_skips_save(
    qtbot, tmp_path, monkeypatch
) -> None:
    """Verify save current returns false when plan requests no save run."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    monkeypatch.setattr(win, "_can_write_originals", lambda *_args, **_kwargs: True)

    class _StubService:
        @staticmethod
        def build_save_current_run_plan(**_kwargs):  # type: ignore[no-untyped-def]
            return SimpleNamespace(immediate_result=None, run_save=False)

    monkeypatch.setattr(win, "_file_workflow_service", _StubService())
    assert win._save_current() is False


def test_save_current_shows_error_dialog_when_persist_fails(
    qtbot, tmp_path, monkeypatch
) -> None:
    """Verify save current surfaces persist exceptions through error dialog."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    target = root / "BE" / "ui.txt"
    index = win.fs_model.index_for_path(target)
    win._file_chosen(index)
    assert win._current_model is not None
    value_idx = win._current_model.index(0, 2)
    win._current_model.setData(value_idx, "Changed", Qt.EditRole)

    monkeypatch.setattr(win, "_can_write_originals", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(win, "_ensure_conflicts_resolved", lambda *_args: True)

    class _StubService:
        @staticmethod
        def build_save_current_run_plan(**_kwargs):  # type: ignore[no-untyped-def]
            return SimpleNamespace(immediate_result=None, run_save=True)

        @staticmethod
        def persist_current_save(**_kwargs):  # type: ignore[no-untyped-def]
            raise RuntimeError("persist failed")

    monkeypatch.setattr(win, "_file_workflow_service", _StubService())
    errors: list[tuple[str, str]] = []
    monkeypatch.setattr(
        mw.QMessageBox,
        "critical",
        lambda _parent, title, text: errors.append((str(title), str(text))),
    )

    assert win._save_current() is False
    assert errors == [("Save failed", "persist failed")]


def test_prompt_conflicts_delegates_to_conflict_service(qtbot, tmp_path, monkeypatch):
    """Verify prompt conflicts delegates to conflict service."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    target = root / "BE" / "ui.txt"
    win._conflict_files[target] = {"UI_OK": "original"}

    calls: list[tuple[bool, bool, bool]] = []
    delegate = win._conflict_workflow_service

    class _SpyService:
        def __getattr__(self, name: str):
            return getattr(delegate, name)

        def build_prompt_plan(
            self,
            *,
            has_conflicts: bool,
            is_current_file: bool,
            for_save: bool,
        ) -> ConflictPromptPlan:
            calls.append((has_conflicts, is_current_file, for_save))
            return ConflictPromptPlan(require_dialog=False, immediate_result=True)

    monkeypatch.setattr(win, "_conflict_workflow_service", _SpyService())
    assert win._prompt_conflicts(target) is True
    assert calls == [(True, False, False)]


def test_prompt_conflicts_dialog_path_delegates_choice_execution(
    qtbot, tmp_path, monkeypatch
):
    """Verify prompt conflicts dialog path delegates choice execution."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    target = root / "BE" / "ui.txt"
    index = win.fs_model.index_for_path(target)
    win._file_chosen(index)
    win._conflict_files[target] = {"UI_OK": "original"}

    class _FakeDialog:
        def __init__(self, *_args, **_kwargs):
            pass

        def exec(self) -> int:
            return 0

        def choice(self) -> str:
            return "merge"

    calls: list[str | None] = []
    delegate = win._conflict_workflow_service

    class _SpyService:
        def __getattr__(self, name: str):
            return getattr(delegate, name)

        def execute_choice(
            self,
            choice: str | None,
            *,
            on_drop_cache,
            on_drop_original,
            on_merge,
        ):  # type: ignore[no-untyped-def]
            calls.append(choice)
            return on_merge()

    monkeypatch.setattr(mw, "ConflictChoiceDialog", _FakeDialog)
    monkeypatch.setattr(win, "_conflict_workflow_service", _SpyService())
    monkeypatch.setattr(win, "_resolve_conflicts_merge", lambda _path: True)
    assert win._prompt_conflicts(target) is True
    assert calls == ["merge"]


def test_resolve_conflicts_drop_cache_delegates_persist_execution(
    qtbot, tmp_path, monkeypatch
):
    """Verify resolve conflicts drop cache delegates persist execution."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    target = root / "BE" / "ui.txt"
    index = win.fs_model.index_for_path(target)
    win._file_chosen(index)
    win._conflict_files[target] = {"UI_OK": "orig"}

    persist_calls: list[ConflictResolution] = []
    run_plan_calls: list[tuple[str, int]] = []
    delegate = win._conflict_workflow_service

    class _SpyService:
        def __getattr__(self, name: str):
            return getattr(delegate, name)

        def build_resolution_run_plan(
            self,
            *,
            action: str,
            has_current_file: bool,
            has_current_model: bool,
            is_current_file: bool,
            conflict_count: int,
        ):  # type: ignore[no-untyped-def]
            run_plan_calls.append((action, conflict_count))
            return delegate.build_resolution_run_plan(
                action=action,
                has_current_file=has_current_file,
                has_current_model=has_current_model,
                is_current_file=is_current_file,
                conflict_count=conflict_count,
            )

        def execute_persist_resolution(
            self,
            *,
            resolution: ConflictResolution,
            callbacks,
        ):  # type: ignore[no-untyped-def]
            _ = callbacks
            persist_calls.append(resolution)
            return True

    monkeypatch.setattr(win, "_conflict_workflow_service", _SpyService())
    monkeypatch.setattr(win, "_reload_file", lambda _path: None)
    assert win._resolve_conflicts_drop_cache(target) is True
    assert run_plan_calls == [("drop_cache", 1)]
    assert len(persist_calls) == 1


def test_resolve_conflicts_merge_delegates_merge_execution(
    qtbot, tmp_path, monkeypatch
):
    """Verify resolve conflicts merge delegates merge execution."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    target = root / "BE" / "ui.txt"
    index = win.fs_model.index_for_path(target)
    win._file_chosen(index)
    win._conflict_files[target] = {"UI_OK": "orig"}
    win._conflict_sources[target] = {"UI_OK": "src"}

    calls: list[int] = []
    delegate = win._conflict_workflow_service

    class _SpyService:
        def __getattr__(self, name: str):
            return getattr(delegate, name)

        def execute_merge_resolution(
            self,
            *,
            entries,
            changed_keys,
            baseline_values,
            conflict_originals,
            sources,
            request_resolutions,
        ):  # type: ignore[no-untyped-def]
            _ = entries
            _ = changed_keys
            _ = baseline_values
            _ = sources
            _ = request_resolutions
            calls.append(len(conflict_originals))
            return ConflictMergeExecution(
                resolved=False,
                immediate_result=False,
                resolution=None,
            )

    monkeypatch.setattr(win, "_conflict_workflow_service", _SpyService())
    assert win._resolve_conflicts_merge(target) is False
    assert calls == [1]


def test_search_from_anchor_delegates_to_search_replace_service(
    qtbot, tmp_path, monkeypatch
):
    """Verify search from anchor delegates to search replace service."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    index = win.fs_model.index_for_path(root / "BE" / "ui.txt")
    win._file_chosen(index)

    calls: list[dict[str, object]] = []
    delegate = win._search_replace_service

    class _SpyService:
        def __getattr__(self, name: str):
            return getattr(delegate, name)

        def build_search_run_plan(self, **kwargs):  # type: ignore[no-untyped-def]
            calls.append(kwargs)
            return SearchRunPlan(
                run_search=False,
                query="",
                use_regex=False,
                field=None,
                include_source=False,
                include_value=False,
                files=(),
                anchor_path=None,
                anchor_row=-1,
                status_message="No query.",
            )

    monkeypatch.setattr(win, "_search_replace_service", _SpyService())
    win.search_edit.setText("")
    assert win._search_from_anchor(direction=1) is False
    assert calls
    assert calls[0]["query_text"] == ""
    assert calls[0]["current_file"] == root / "BE" / "ui.txt"
    assert win._search_status_label.text() == "No query."


def test_files_for_scope_delegates_to_search_replace_service(
    qtbot, tmp_path, monkeypatch
):
    """Verify files for scope delegates to search replace service."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    index = win.fs_model.index_for_path(root / "BE" / "ui.txt")
    win._file_chosen(index)

    calls: list[dict[str, object]] = []
    delegate = win._search_replace_service

    class _SpyService:
        def __getattr__(self, name: str):
            return getattr(delegate, name)

        def scope_files(self, **kwargs):  # type: ignore[no-untyped-def]
            calls.append(kwargs)
            return [root / "BE" / "ui.txt"]

    monkeypatch.setattr(win, "_search_replace_service", _SpyService())
    files = win._files_for_scope("FILE")
    assert files == [root / "BE" / "ui.txt"]
    assert calls and calls[0]["scope"] == "FILE"


def test_find_match_in_rows_delegates_to_search_replace_service(
    qtbot, tmp_path, monkeypatch
):
    """Verify find match in rows delegates to search replace service."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    rows = [
        mw._SearchRow(file=root / "BE" / "ui.txt", row=0, key="K", source="", value="V")
    ]

    calls: list[dict[str, object]] = []
    delegate = win._search_replace_service

    class _SpyService:
        def __getattr__(self, name: str):
            return getattr(delegate, name)

        def find_match_in_rows(
            self,
            rows,
            query,
            field,
            use_regex,
            *,
            start_row,
            direction,
            case_sensitive,
        ):  # type: ignore[no-untyped-def]
            calls.append(
                {
                    "rows": list(rows),
                    "query": query,
                    "field": field,
                    "use_regex": use_regex,
                    "start_row": start_row,
                    "direction": direction,
                    "case_sensitive": case_sensitive,
                }
            )
            return None

    monkeypatch.setattr(win, "_search_replace_service", _SpyService())
    assert (
        win._find_match_in_rows(
            rows,
            "needle",
            mw._SearchField.TRANSLATION,
            False,
            start_row=-1,
            direction=1,
            case_sensitive=False,
        )
        is None
    )
    assert calls and calls[0]["query"] == "needle"


def test_refresh_search_panel_delegates_search_spec_to_service(
    qtbot, tmp_path, monkeypatch
):
    """Verify refresh search panel delegates search spec to service."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    calls: list[int] = []
    delegate = win._search_replace_service

    class _SpyService:
        def __getattr__(self, name: str):
            return getattr(delegate, name)

        def search_spec_for_column(self, column: int):  # type: ignore[no-untyped-def]
            calls.append(column)
            return mw._SearchField.KEY, False, False

        def build_search_panel_plan(self, **kwargs):  # type: ignore[no-untyped-def]
            return delegate.build_search_panel_plan(**kwargs)

    monkeypatch.setattr(win, "_search_replace_service", _SpyService())
    win.search_edit.setText("needle")
    win._refresh_search_panel_results()
    assert calls


def test_replace_all_count_in_file_delegates_to_search_replace_service(
    qtbot, tmp_path, monkeypatch
):
    """Verify replace all count in file delegates to search replace service."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    target = root / "BE" / "ui.txt"

    calls: list[Path] = []
    delegate = win._search_replace_service

    class _SpyService:
        def __getattr__(self, name: str):
            return getattr(delegate, name)

        def count_replace_all_in_file(self, path: Path, **_kwargs) -> int:  # type: ignore[no-untyped-def]
            calls.append(path)
            return 7

    monkeypatch.setattr(win, "_search_replace_service", _SpyService())
    count = win._replace_all_count_in_file(
        target,
        pattern=re.compile("UI"),
        replacement="ZZ",
        use_regex=False,
        matches_empty=False,
        has_group_ref=False,
    )
    assert count == 7
    assert calls == [target]


def test_replace_all_count_in_model_delegates_to_search_replace_service(
    qtbot, tmp_path, monkeypatch
):
    """Verify replace all count in model delegates to search replace service."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    index = win.fs_model.index_for_path(root / "BE" / "ui.txt")
    win._file_chosen(index)

    calls: list[dict[str, object]] = []
    delegate = win._search_replace_service

    class _SpyService:
        def __getattr__(self, name: str):
            return getattr(delegate, name)

        def count_replace_all_in_rows(self, **kwargs) -> int:  # type: ignore[no-untyped-def]
            calls.append(kwargs)
            return 3

    monkeypatch.setattr(win, "_search_replace_service", _SpyService())
    count = win._replace_all_count_in_model(
        pattern=re.compile("UI"),
        replacement="ZZ",
        use_regex=False,
        matches_empty=False,
        has_group_ref=False,
    )
    assert count == 3
    assert calls


def test_replace_all_in_file_delegates_to_search_replace_service(
    qtbot, tmp_path, monkeypatch
):
    """Verify replace all in file delegates to search replace service."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    target = root / "BE" / "ui.txt"

    calls: list[Path] = []
    dirty_calls: list[tuple[Path, bool]] = []
    delegate = win._search_replace_service

    class _SpyService:
        def __getattr__(self, name: str):
            return getattr(delegate, name)

        def apply_replace_all_in_file(
            self, path: Path, **_kwargs
        ) -> ReplaceAllFileApplyResult:  # type: ignore[no-untyped-def]
            calls.append(path)
            return ReplaceAllFileApplyResult(changed_keys={"UI_OK"}, changed_any=True)

    monkeypatch.setattr(win, "_search_replace_service", _SpyService())
    monkeypatch.setattr(
        win.fs_model,
        "set_dirty",
        lambda path, dirty: dirty_calls.append((path, dirty)),
    )
    ok = win._replace_all_in_file(
        target,
        pattern=re.compile("UI"),
        replacement="ZZ",
        use_regex=False,
        matches_empty=False,
        has_group_ref=False,
    )
    assert ok is True
    assert calls == [target]
    assert dirty_calls == [(target, True)]


def test_replace_all_in_model_delegates_to_search_replace_service(
    qtbot, tmp_path, monkeypatch
):
    """Verify replace all in model delegates to search replace service."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    index = win.fs_model.index_for_path(root / "BE" / "ui.txt")
    win._file_chosen(index)

    calls: list[dict[str, object]] = []
    delegate = win._search_replace_service

    class _SpyService:
        def __getattr__(self, name: str):
            return getattr(delegate, name)

        def apply_replace_all_in_rows(
            self, **kwargs
        ) -> ReplaceAllRowsApplyResult:  # type: ignore[no-untyped-def]
            calls.append(kwargs)
            return ReplaceAllRowsApplyResult(changed_rows=1)

    monkeypatch.setattr(win, "_search_replace_service", _SpyService())
    ok = win._replace_all_in_model(
        pattern=re.compile("UI"),
        replacement="ZZ",
        use_regex=False,
        matches_empty=False,
        has_group_ref=False,
    )
    assert ok is True
    assert calls


def test_replace_current_delegates_to_search_replace_service(
    qtbot, tmp_path, monkeypatch
):
    """Verify replace current delegates to search replace service."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    index = win.fs_model.index_for_path(root / "BE" / "ui.txt")
    win._file_chosen(index)
    current = win.table.currentIndex()
    if not current.isValid():
        current = win._current_model.index(0, 2)  # type: ignore[union-attr]
        win.table.setCurrentIndex(current)

    request = ReplaceRequest(
        pattern=re.compile("UI"),
        replacement="ZZ",
        use_regex=False,
        matches_empty=False,
        has_group_ref=False,
    )
    calls: list[dict[str, object]] = []
    delegate = win._search_replace_service

    class _SpyService:
        def __getattr__(self, name: str):
            return getattr(delegate, name)

        def build_replace_request(self, **_kwargs):  # type: ignore[no-untyped-def]
            return request

        def apply_replace_in_row(self, **kwargs):  # type: ignore[no-untyped-def]
            calls.append(kwargs)
            return True

    scheduled: list[bool] = []
    monkeypatch.setattr(win, "_search_replace_service", _SpyService())
    monkeypatch.setattr(win, "_schedule_search", lambda: scheduled.append(True))
    win._replace_current()
    assert calls
    assert calls[0]["row"] == current.row()
    assert calls[0]["request"] == request
    assert scheduled == [True]


def test_cached_rows_from_file_delegates_cache_plans(qtbot, tmp_path, monkeypatch):
    """Verify cached rows from file delegates cache plans."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    target = root / "BE" / "ui.txt"
    cached_rows = [mw._SearchRow(file=target, row=0, key="K", source="", value="V")]
    stamp = SearchRowsCacheStamp(file_mtime_ns=1, cache_mtime_ns=0, source_mtime_ns=0)
    key = (target, False, False)
    win._search_rows_cache[key] = (stamp, cached_rows)

    calls: list[str] = []
    delegate = win._search_replace_service

    class _SpyService:
        def __getattr__(self, name: str):
            return getattr(delegate, name)

        def build_rows_cache_lookup_plan(
            self, **kwargs
        ) -> SearchRowsCacheLookupPlan:  # type: ignore[no-untyped-def]
            calls.append("lookup")
            return SearchRowsCacheLookupPlan(
                key=SearchRowsCacheKey(
                    path=target,
                    include_source=False,
                    include_value=False,
                ),
                stamp=stamp,
                use_cached_rows=True,
            )

        def build_rows_cache_store_plan(
            self, **_kwargs
        ) -> SearchRowsCacheStorePlan:  # type: ignore[no-untyped-def]
            calls.append("store")
            return SearchRowsCacheStorePlan(should_store_rows=False)

    def _fail_rows_loader(*_args, **_kwargs):
        raise AssertionError("rows loader should not run on cache hit")

    monkeypatch.setattr(win, "_search_replace_service", _SpyService())
    monkeypatch.setattr(win, "_rows_from_file", _fail_rows_loader)
    rows = list(
        win._cached_rows_from_file(
            target,
            "BE",
            include_source=False,
            include_value=False,
        )
    )
    assert rows == cached_rows
    assert calls == ["lookup"]


def test_cached_rows_from_file_delegates_stamp_collection_to_service(
    qtbot, tmp_path, monkeypatch
):
    """Verify cached rows from file delegates stamp collection to service."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    target = root / "BE" / "ui.txt"

    calls: list[str] = []
    delegate = win._search_replace_service

    class _SpyService:
        def __getattr__(self, name: str):
            return getattr(delegate, name)

        def collect_rows_cache_stamp(self, **_kwargs):  # type: ignore[no-untyped-def]
            calls.append("stamp")
            return None

        def build_rows_cache_lookup_plan(
            self, **_kwargs
        ):  # type: ignore[no-untyped-def]
            raise AssertionError("lookup should not run when stamp is missing")

    monkeypatch.setattr(win, "_search_replace_service", _SpyService())
    rows = list(
        win._cached_rows_from_file(
            target,
            "BE",
            include_source=True,
            include_value=True,
        )
    )
    assert rows == []
    assert calls == ["stamp"]


def test_search_rows_for_file_delegates_rows_source_plan_current_model(
    qtbot, tmp_path, monkeypatch
):
    """Verify search rows for file delegates rows source plan current model."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    target = root / "BE" / "ui.txt"
    index = win.fs_model.index_for_path(target)
    win._file_chosen(index)

    calls: list[dict[str, object]] = []
    delegate = win._search_replace_service
    current_rows = [mw._SearchRow(file=target, row=0, key="K", source="", value="V")]

    class _SpyService:
        def __getattr__(self, name: str):
            return getattr(delegate, name)

        def build_rows_source_plan(
            self, **kwargs
        ) -> SearchRowsSourcePlan:  # type: ignore[no-untyped-def]
            calls.append(kwargs)
            return SearchRowsSourcePlan(has_rows=True, use_active_model_rows=True)

    monkeypatch.setattr(win, "_search_replace_service", _SpyService())
    monkeypatch.setattr(win, "_rows_from_model", lambda **_kwargs: current_rows)
    monkeypatch.setattr(
        win,
        "_cached_rows_from_file",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("cached rows should not be used for current-model plan")
        ),
    )
    rows = list(
        win._search_rows_for_file(
            target,
            include_source=False,
            include_value=False,
        )
    )
    assert rows == current_rows
    assert calls and calls[0]["is_current_file"] is True


def test_search_rows_for_file_delegates_rows_source_plan_cached_file(
    qtbot, tmp_path, monkeypatch
):
    """Verify search rows for file delegates rows source plan cached file."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    target = root / "BE" / "ui.txt"

    calls: list[dict[str, object]] = []
    delegate = win._search_replace_service
    cached_rows = [mw._SearchRow(file=target, row=0, key="K", source="", value="V")]

    class _SpyService:
        def __getattr__(self, name: str):
            return getattr(delegate, name)

        def build_rows_source_plan(
            self, **kwargs
        ) -> SearchRowsSourcePlan:  # type: ignore[no-untyped-def]
            calls.append(kwargs)
            return SearchRowsSourcePlan(has_rows=True, use_active_model_rows=False)

    monkeypatch.setattr(win, "_search_replace_service", _SpyService())
    monkeypatch.setattr(
        win, "_cached_rows_from_file", lambda *_args, **_kwargs: cached_rows
    )
    rows = list(
        win._search_rows_for_file(
            target,
            include_source=False,
            include_value=False,
        )
    )
    assert rows == cached_rows
    assert calls and calls[0]["is_current_file"] is False


def test_rows_from_file_delegates_file_row_load_to_service(
    qtbot, tmp_path, monkeypatch
):
    """Verify rows from file delegates file row load to service."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    target = root / "BE" / "ui.txt"
    expected_rows = [
        mw._SearchRow(file=target, row=0, key="UI_OK", source="", value="x")
    ]

    calls: list[dict[str, object]] = []
    delegate = win._search_replace_service

    class _SpyService:
        def __getattr__(self, name: str):
            return getattr(delegate, name)

        def load_search_rows_from_file(
            self, **kwargs
        ) -> SearchRowsBuildResult:  # type: ignore[no-untyped-def]
            calls.append(kwargs)
            return SearchRowsBuildResult(rows=expected_rows, entry_count=1)

    monkeypatch.setattr(win, "_search_replace_service", _SpyService())
    rows, count = win._rows_from_file(
        target,
        "BE",
        include_source=False,
        include_value=False,
    )
    assert list(rows) == expected_rows
    assert count == 1
    assert calls
    assert calls[0]["path"] == target
    assert calls[0]["encoding"] == "UTF-8"


def test_select_match_delegates_match_selection_plans(qtbot, tmp_path, monkeypatch):
    """Verify select match delegates match selection plans."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    target = root / "BE" / "ui.txt"
    index = win.fs_model.index_for_path(target)
    win._file_chosen(index)
    win._search_column = 2
    match = Match(target, 0)

    calls: list[str] = []
    delegate = win._search_replace_service

    class _SpyService:
        def __getattr__(self, name: str):
            return getattr(delegate, name)

        def build_match_open_plan(self, **_kwargs):  # type: ignore[no-untyped-def]
            calls.append("open")
            return SearchMatchOpenPlan(open_target_file=False, target_file=target)

        def build_match_apply_plan(self, **_kwargs):  # type: ignore[no-untyped-def]
            calls.append("apply")
            return SearchMatchApplyPlan(
                select_in_table=True,
                target_row=0,
                target_column=2,
            )

    monkeypatch.setattr(win, "_search_replace_service", _SpyService())
    assert win._select_match(match) is True
    assert calls == ["open", "apply"]


def test_rows_from_model_handles_missing_context_and_active_model(
    qtbot, tmp_path
) -> None:
    """Verify rows from model returns empty without context and delegates otherwise."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    target = root / "BE" / "ui.txt"

    assert tuple(win._rows_from_model()) == ()

    calls: list[dict[str, object]] = []
    expected_rows = [
        mw._SearchRow(file=target, row=0, key="UI_OK", source="", value="x")
    ]

    class _Model:
        def iter_search_rows(self, **kwargs):  # type: ignore[no-untyped-def]
            calls.append(kwargs)
            return expected_rows

    win._current_model = _Model()  # type: ignore[assignment]
    win._current_pf = SimpleNamespace(path=target)
    rows = list(win._rows_from_model(include_source=False, include_value=True))
    assert rows == expected_rows
    assert calls == [{"include_source": False, "include_value": True}]
    win._current_model = None
    win._current_pf = None


def test_rows_from_file_returns_empty_on_loader_failure_result(
    qtbot, tmp_path, monkeypatch
) -> None:
    """Verify rows from file returns empty tuple/count when service returns None."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    target = root / "BE" / "ui.txt"

    calls: list[dict[str, object]] = []
    delegate = win._search_replace_service

    class _SpyService:
        def __getattr__(self, name: str):
            return getattr(delegate, name)

        def load_search_rows_from_file(self, **kwargs):  # type: ignore[no-untyped-def]
            calls.append(kwargs)
            return None

    monkeypatch.setattr(win, "_search_replace_service", _SpyService())
    rows, count = win._rows_from_file(
        target,
        "XX",
        include_source=True,
        include_value=False,
    )
    assert tuple(rows) == ()
    assert count == 0
    assert calls and calls[0]["encoding"] == "utf-8"


def test_cached_rows_from_file_stores_rows_and_prunes_lru(qtbot, tmp_path, monkeypatch):
    """Verify cached rows store path and LRU eviction branch when cache exceeds max."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    target_a = root / "BE" / "ui.txt"
    target_b = root / "BE" / "other.txt"
    target_b.write_text('UI_OTHER = "x"\n', encoding="utf-8")
    stamp = SearchRowsCacheStamp(file_mtime_ns=1, cache_mtime_ns=0, source_mtime_ns=0)
    win._search_cache_max = 1

    delegate = win._search_replace_service

    class _SpyService:
        def __getattr__(self, name: str):
            return getattr(delegate, name)

        def collect_rows_cache_stamp(self, **_kwargs):  # type: ignore[no-untyped-def]
            return stamp

        def build_rows_cache_lookup_plan(
            self, **kwargs
        ) -> SearchRowsCacheLookupPlan:  # type: ignore[no-untyped-def]
            return SearchRowsCacheLookupPlan(
                key=SearchRowsCacheKey(
                    path=kwargs["path"],
                    include_source=kwargs["include_source"],
                    include_value=kwargs["include_value"],
                ),
                stamp=stamp,
                use_cached_rows=False,
            )

        def build_rows_cache_store_plan(
            self, **_kwargs
        ) -> SearchRowsCacheStorePlan:  # type: ignore[no-untyped-def]
            return SearchRowsCacheStorePlan(should_store_rows=True)

    monkeypatch.setattr(win, "_search_replace_service", _SpyService())
    monkeypatch.setattr(
        win,
        "_rows_from_file",
        lambda path, *_args, **_kwargs: (
            [mw._SearchRow(file=path, row=0, key="K", source="", value="V")],
            1,
        ),
    )

    rows_a = list(
        win._cached_rows_from_file(
            target_a,
            "BE",
            include_source=False,
            include_value=False,
        )
    )
    rows_b = list(
        win._cached_rows_from_file(
            target_b,
            "BE",
            include_source=False,
            include_value=False,
        )
    )

    assert rows_a and rows_a[0].file == target_a
    assert rows_b and rows_b[0].file == target_b
    assert len(win._search_rows_cache) == 1
    only_key = next(iter(win._search_rows_cache.keys()))
    assert only_key[0] == target_b


def test_rows_mtime_helpers_cover_missing_paths_and_locale_fallback(
    qtbot, tmp_path, monkeypatch
) -> None:
    """Verify row mtime helpers handle missing paths and same-locale source fallback."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    missing = root / "BE" / "missing.txt"
    outside = tmp_path / "outside.txt"

    assert win._file_mtime_for_rows(missing) is None
    assert win._cache_mtime_for_rows(outside) == 0

    monkeypatch.setattr(
        mw,
        "_effective_source_reference_mode_for_window",
        lambda *_args, **_kwargs: "BE",
    )
    monkeypatch.setattr(
        mw,
        "_reference_path_for",
        lambda *_args, **_kwargs: root / "EN" / "ui.txt",
    )
    assert win._source_mtime_for_rows(missing, "BE") == 0

    monkeypatch.setattr(
        mw,
        "_effective_source_reference_mode_for_window",
        lambda *_args, **_kwargs: "EN",
    )
    assert win._source_mtime_for_rows(root / "BE" / "ui.txt", "BE") > 0


def test_search_rows_for_file_returns_empty_when_plan_has_no_rows(
    qtbot, tmp_path, monkeypatch
) -> None:
    """Verify search rows for file returns empty when source plan has no rows."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    target = root / "BE" / "ui.txt"
    delegate = win._search_replace_service

    class _SpyService:
        def __getattr__(self, name: str):
            return getattr(delegate, name)

        @staticmethod
        def build_rows_source_plan(**_kwargs):  # type: ignore[no-untyped-def]
            return SearchRowsSourcePlan(has_rows=False, use_active_model_rows=False)

    monkeypatch.setattr(win, "_search_replace_service", _SpyService())
    monkeypatch.setattr(
        win,
        "_cached_rows_from_file",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("cached rows must not be used when plan has no rows")
        ),
    )
    rows = tuple(
        win._search_rows_for_file(
            target,
            include_source=False,
            include_value=False,
        )
    )
    assert rows == ()


def test_select_match_handles_open_target_fail_and_nonselect_paths(
    qtbot, tmp_path, monkeypatch
) -> None:
    """Verify select match returns False for invalid open target and no-select plans."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    target = root / "BE" / "ui.txt"
    missing = root / "BE" / "missing.txt"
    index = win.fs_model.index_for_path(target)
    win._file_chosen(index)
    win._search_column = 2

    delegate = win._search_replace_service

    class _OpenFailService:
        def __getattr__(self, name: str):
            return getattr(delegate, name)

        @staticmethod
        def build_match_open_plan(**_kwargs):  # type: ignore[no-untyped-def]
            return SearchMatchOpenPlan(open_target_file=True, target_file=missing)

        @staticmethod
        def build_match_apply_plan(**_kwargs):  # type: ignore[no-untyped-def]
            raise AssertionError("apply plan must not run when open target is invalid")

    monkeypatch.setattr(win, "_search_replace_service", _OpenFailService())
    assert win._select_match(Match(missing, 0)) is False

    opened: list[Path] = []

    class _NoSelectService:
        def __getattr__(self, name: str):
            return getattr(delegate, name)

        @staticmethod
        def build_match_open_plan(**_kwargs):  # type: ignore[no-untyped-def]
            return SearchMatchOpenPlan(open_target_file=True, target_file=target)

        @staticmethod
        def build_match_apply_plan(**_kwargs):  # type: ignore[no-untyped-def]
            return SearchMatchApplyPlan(
                select_in_table=False,
                target_row=0,
                target_column=2,
            )

    monkeypatch.setattr(
        win,
        "_file_chosen",
        lambda idx: opened.append(Path(idx.data(Qt.UserRole))),
    )
    win._current_pf = SimpleNamespace(path=target)
    monkeypatch.setattr(win, "_search_replace_service", _NoSelectService())
    assert win._select_match(Match(target, 0)) is False
    assert opened == [target]


def test_search_and_qa_result_openers_ignore_invalid_payloads(
    qtbot, tmp_path, monkeypatch
) -> None:
    """Verify search/qa side-panel item openers ignore malformed payloads."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    selected: list[Match] = []
    monkeypatch.setattr(win, "_select_match", lambda match: selected.append(match))

    search_item = QListWidgetItem("bad search")
    search_item.setData(Qt.UserRole, "bad")
    win._open_search_result_item(search_item)
    search_item.setData(Qt.UserRole, ("/tmp/x", "bad-row"))
    win._open_search_result_item(search_item)

    qa_item = QListWidgetItem("bad qa")
    qa_item.setData(Qt.UserRole, "bad")
    win._open_qa_result_item(qa_item)
    qa_item.setData(Qt.UserRole, ("/tmp/x", "bad-row"))
    win._open_qa_result_item(qa_item)

    assert selected == []


def test_refresh_search_panel_results_covers_guard_empty_query_and_empty_files(
    qtbot, tmp_path, monkeypatch
) -> None:
    """Verify search panel refresh handles missing widgets, empty query, and empty file scopes."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    win._search_results_list = None
    win.search_edit.setText("needle")
    win._refresh_search_panel_results()

    win._search_results_list = mw.QListWidget()
    win._search_status_label = mw.QLabel()
    win.search_edit.setText("   ")
    win._refresh_search_panel_results()
    assert (
        win._search_status_label.text()
        == "Press Enter in the search box to populate results."
    )

    win.search_edit.setText("needle")
    monkeypatch.setattr(win, "_search_files_for_scope", lambda: [])
    win._refresh_search_panel_results()
    assert win._search_status_label.text() == "No files in current search scope."


def test_schedule_qa_refresh_covers_disabled_busy_immediate_and_timer_paths(
    qtbot, tmp_path, monkeypatch
) -> None:
    """Verify QA refresh scheduling handles guard, immediate, and deferred branches."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    calls: list[str] = []
    monkeypatch.setattr(
        win,
        "_start_qa_scan_for_current_file",
        lambda: calls.append("scan"),
    )

    win._qa_auto_refresh = False
    win._schedule_qa_refresh(immediate=False)
    assert win._qa_refresh_timer.isActive() is False

    win._qa_auto_refresh = True
    win._qa_scan_busy = True
    win._schedule_qa_refresh(immediate=False)
    assert win._qa_refresh_timer.isActive() is False

    win._qa_scan_busy = False
    win._schedule_qa_refresh(immediate=False)
    assert win._qa_refresh_timer.isActive() is True

    win._qa_refresh_timer.start(50)
    win._schedule_qa_refresh(immediate=True)
    assert calls == ["scan"]
    assert win._qa_refresh_timer.isActive() is False


def test_qa_panel_helpers_cover_empty_plan_navigation_and_focus_paths(
    qtbot, tmp_path, monkeypatch
) -> None:
    """Verify QA panel helpers cover missing-list, no-finding, failed-open, and success paths."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    target = root / "BE" / "ui.txt"
    index = win.fs_model.index_for_path(target)
    win._file_chosen(index)

    win._set_qa_panel_message("hello")
    assert win._qa_status_label.text() == "hello"
    assert win._qa_results_list.count() == 0

    win._qa_results_list = None
    win._refresh_qa_panel_results()
    win._qa_results_list = mw.QListWidget()

    item = QListWidgetItem("qa row")
    item.setData(Qt.UserRole, (str(target), 0))
    win._qa_results_list.addItem(item)
    finding = SimpleNamespace(file=target, row=0)
    win._focus_qa_finding_item(finding)
    assert win._qa_results_list.currentItem() is item
    win._focus_qa_finding_item(SimpleNamespace(file=target, row=999))

    status_calls: list[tuple[str, int]] = []
    monkeypatch.setattr(
        win.statusBar(),
        "showMessage",
        lambda text, ms=0: status_calls.append((text, int(ms))),
    )

    win._qa_findings = ()
    win._navigate_qa_finding(direction=1)
    assert status_calls[-1] == ("Run QA first to navigate findings.", 3000)

    win._qa_findings = (finding,)
    plan_box: dict[str, object] = {
        "value": SimpleNamespace(finding=None, status_message="No finding")
    }

    class _QAService:
        @staticmethod
        def build_navigation_plan(**_kwargs):  # type: ignore[no-untyped-def]
            return plan_box["value"]

    win._qa_service = _QAService()  # type: ignore[assignment]
    win._navigate_qa_finding(direction=1)
    assert status_calls[-1] == ("No finding", 3000)

    plan_box["value"] = SimpleNamespace(
        finding=SimpleNamespace(file=target, row=0),
        status_message="Go row",
    )
    monkeypatch.setattr(win, "_select_match", lambda _match: False)
    win._navigate_qa_finding(direction=1)
    assert status_calls[-1] == ("Unable to navigate to QA finding.", 3000)

    focused: list[object] = []
    monkeypatch.setattr(win, "_select_match", lambda _match: True)
    monkeypatch.setattr(
        win, "_focus_qa_finding_item", lambda found: focused.append(found)
    )
    win._left_stack.setCurrentIndex(mw._LEFT_PANEL_QA)
    win._navigate_qa_finding(direction=1)
    assert focused
    assert status_calls[-1] == ("Go row", 4000)


def test_search_next_prev_and_prompt_toggle_cover_timer_and_persist_paths(
    qtbot, tmp_path, monkeypatch
) -> None:
    """Verify search next/prev stop active timer and prompt toggle persists value."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    calls: list[int] = []
    monkeypatch.setattr(
        win,
        "_search_from_anchor",
        lambda *, direction, **_kwargs: calls.append(int(direction)),
    )
    win._search_timer.start(50)
    win._search_next()
    win._search_timer.start(50)
    win._search_prev()
    assert calls == [1, -1]
    assert win._search_timer.isActive() is False

    persisted: list[bool] = []
    monkeypatch.setattr(win, "_persist_preferences", lambda: persisted.append(True))
    win._toggle_prompt_on_exit(True)
    assert win._prompt_write_on_exit is True
    assert persisted == [True]


def test_left_panel_changed_routes_tm_search_and_qa_branches(
    qtbot, tmp_path, monkeypatch
) -> None:
    """Verify left-panel toggle routes TM/Search/QA behavior through helper branches."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    tm_calls: list[object] = []
    monkeypatch.setattr(win, "_ensure_tm_store", lambda: True)
    monkeypatch.setattr(
        win,
        "_sync_tm_import_folder",
        lambda *, interactive, show_summary: tm_calls.append(
            ("sync", bool(interactive), bool(show_summary))
        ),
    )
    monkeypatch.setattr(
        win, "_maybe_bootstrap_tm", lambda: tm_calls.append("bootstrap")
    )
    monkeypatch.setattr(win, "_schedule_tm_update", lambda: tm_calls.append("update"))
    win._tm_bootstrap_pending = True
    win._on_left_panel_changed(win._left_tm_btn)
    assert win._left_stack.currentIndex() == mw._LEFT_PANEL_TM
    assert tm_calls == [("sync", True, False), "bootstrap", "update"]
    assert win._tm_bootstrap_pending is False

    search_calls: list[str] = []
    monkeypatch.setattr(
        win,
        "_refresh_search_panel_results",
        lambda: search_calls.append("refresh"),
    )
    win._on_left_panel_changed(win._left_search_btn)
    assert win._left_stack.currentIndex() == mw._LEFT_PANEL_SEARCH
    assert search_calls == ["refresh"]

    qa_messages: list[str] = []
    qa_refresh_calls: list[str] = []
    monkeypatch.setattr(win, "_set_qa_panel_message", qa_messages.append)
    monkeypatch.setattr(
        win, "_refresh_qa_panel_results", lambda: qa_refresh_calls.append("refresh")
    )
    win._qa_findings = ()
    win._qa_auto_refresh = False
    win._on_left_panel_changed(win._left_qa_btn)
    assert win._left_stack.currentIndex() == mw._LEFT_PANEL_QA
    assert qa_messages == ["QA is manual. Click Run QA for this file."]
    assert qa_refresh_calls == []

    win._qa_findings = (SimpleNamespace(file=root / "BE" / "ui.txt", row=0),)
    win._on_left_panel_changed(win._left_qa_btn)
    assert qa_refresh_calls == ["refresh"]


def test_left_panel_tm_branch_skips_followups_when_store_unavailable(
    qtbot, tmp_path, monkeypatch
) -> None:
    """Verify TM panel does not run sync/bootstrap/update when TM store is unavailable."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    calls: list[str] = []
    monkeypatch.setattr(win, "_ensure_tm_store", lambda: False)
    monkeypatch.setattr(
        win,
        "_sync_tm_import_folder",
        lambda **_kwargs: calls.append("sync"),
    )
    monkeypatch.setattr(win, "_maybe_bootstrap_tm", lambda: calls.append("bootstrap"))
    monkeypatch.setattr(win, "_schedule_tm_update", lambda: calls.append("update"))

    win._tm_bootstrap_pending = True
    win._on_left_panel_changed(win._left_tm_btn)
    assert win._left_stack.currentIndex() == mw._LEFT_PANEL_TM
    assert calls == []
    assert win._tm_bootstrap_pending is True


def test_scroll_handlers_cover_wrap_disabled_and_idle_paths(
    qtbot, tmp_path, monkeypatch
) -> None:
    """Verify scroll hooks handle wrap-off guard and idle follow-up work."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    calls: list[str] = []
    monkeypatch.setattr(win, "_prefetch_visible_rows", lambda: calls.append("prefetch"))
    monkeypatch.setattr(win, "_schedule_row_resize", lambda: calls.append("resize"))

    win._wrap_text = False
    win._scrolling = False
    win._prefetch_pending = False
    win._on_table_scrolled()
    assert win._prefetch_pending is True
    assert win._scrolling is False
    assert win._scroll_idle_timer.isActive() is False

    win._wrap_text = True
    win._prefetch_pending = False
    win._on_table_scrolled()
    assert win._scrolling is True
    assert win._scroll_idle_timer.isActive() is True

    win._prefetch_pending = True
    win._on_scroll_idle()
    assert win._scrolling is False
    assert win._prefetch_pending is False
    assert calls == ["prefetch", "resize"]

    calls.clear()
    win._prefetch_pending = False
    win._on_scroll_idle()
    assert calls == ["resize"]


def test_resize_reflow_helpers_cover_pending_and_wrap_model_guards(
    qtbot, tmp_path, monkeypatch
) -> None:
    """Verify resize-reflow scheduling and flush guards for pending/wrap/model states."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    target = root / "BE" / "ui.txt"
    index = win.fs_model.index_for_path(target)
    win._file_chosen(index)

    win._wrap_text = True
    assert win._current_model is not None
    win._resize_reflow_timer.start(50)
    win._schedule_resize_reflow()
    assert win._resize_reflow_pending is True
    assert win._resize_reflow_timer.isActive() is True

    clear_calls: list[str] = []
    resize_calls: list[str] = []
    monkeypatch.setattr(win, "_clear_row_height_cache", lambda: clear_calls.append("c"))
    monkeypatch.setattr(win, "_schedule_row_resize", lambda: resize_calls.append("r"))

    win._resize_reflow_pending = False
    win._flush_resize_reflow()
    assert clear_calls == []
    assert resize_calls == []

    win._resize_reflow_pending = True
    win._wrap_text = False
    win._flush_resize_reflow()
    assert win._resize_reflow_pending is False
    assert clear_calls == []
    assert resize_calls == []

    win._resize_reflow_pending = True
    win._wrap_text = True
    win._current_model = None
    win._flush_resize_reflow()
    assert win._resize_reflow_pending is False
    assert clear_calls == []
    assert resize_calls == []


def test_on_header_resized_covers_key_status_and_unknown_column_paths(
    qtbot, tmp_path, monkeypatch
) -> None:
    """Verify header resize updates persisted key/status widths and ignores unknown columns."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    target = root / "BE" / "ui.txt"
    index = win.fs_model.index_for_path(target)
    win._file_chosen(index)

    calls: list[str] = []
    monkeypatch.setattr(win, "_apply_table_layout", lambda: calls.append("layout"))
    monkeypatch.setattr(win, "_schedule_resize_reflow", lambda: calls.append("reflow"))

    win._on_header_resized(0, win._key_column_width, 40)
    assert win._key_column_width == 60
    assert win._prefs_extras["TABLE_KEY_WIDTH"] == "60"
    assert calls == ["layout", "reflow"]

    calls.clear()
    win._on_header_resized(3, win._status_column_width, 77)
    assert win._status_column_width == 77
    assert win._prefs_extras["TABLE_STATUS_WIDTH"] == "77"
    assert calls == ["layout", "reflow"]

    calls.clear()
    ratio_before = win._source_translation_ratio
    win._on_header_resized(9, 0, 120)
    assert calls == []
    assert win._source_translation_ratio == ratio_before

    win.show()
    qtbot.wait(1)
    calls.clear()
    win._on_header_resized(2, 120, 180)
    assert "TABLE_SRC_RATIO" in win._prefs_extras
    assert win._user_resized_columns is True
    assert calls == ["reflow"]


def test_tooltip_event_filter_covers_move_leave_and_tooltip_paths(
    qtbot, tmp_path, monkeypatch
) -> None:
    """Verify tooltip event-filter handles move, leave, and tooltip suppression branches."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    target = root / "BE" / "ui.txt"
    index = win.fs_model.index_for_path(target)
    win._file_chosen(index)
    win.show()
    qtbot.wait(1)
    viewport = win.table.viewport()

    class _MoveEvent:
        def __init__(self, pos, global_pos) -> None:
            self._pos = pos
            self._global_pos = global_pos

        def type(self):
            return mw.QEvent.Type.MouseMove

        def pos(self):
            return self._pos

        def globalPos(self):
            return self._global_pos

    class _TypeEvent:
        def __init__(self, event_type) -> None:
            self._event_type = event_type

        def type(self):
            return self._event_type

    hidden_calls: list[str] = []
    monkeypatch.setattr(mw.QToolTip, "hideText", lambda: hidden_calls.append("hide"))

    invalid_move = _MoveEvent(
        mw.QPoint(-100, -100),
        viewport.mapToGlobal(mw.QPoint(0, 0)),
    )
    assert win.eventFilter(viewport, invalid_move) is False
    assert not win._tooltip_index.isValid()
    assert hidden_calls == ["hide"]

    pos = mw.QPoint(
        win.table.columnViewportPosition(0) + 8,
        win.table.rowViewportPosition(0) + 8,
    )
    idx = win.table.indexAt(pos)
    assert idx.isValid()
    move = _MoveEvent(pos, viewport.mapToGlobal(pos))
    assert win.eventFilter(viewport, move) is False
    assert win._tooltip_index == idx
    assert win._tooltip_timer.isActive() is True

    updated_global = viewport.mapToGlobal(pos + mw.QPoint(2, 2))
    move_same = _MoveEvent(pos, updated_global)
    assert win.eventFilter(viewport, move_same) is False
    assert win._tooltip_pos == updated_global

    leave = _TypeEvent(mw.QEvent.Type.Leave)
    assert win.eventFilter(viewport, leave) is False
    assert not win._tooltip_index.isValid()
    assert win._tooltip_timer.isActive() is False

    tooltip_event = _TypeEvent(mw.QEvent.Type.ToolTip)
    assert win.eventFilter(viewport, tooltip_event) is True


def test_show_delayed_tooltip_covers_guard_and_show_paths(
    qtbot, tmp_path, monkeypatch
) -> None:
    """Verify delayed tooltip helper skips invalid states and shows tooltip on valid hover."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    target = root / "BE" / "ui.txt"
    index = win.fs_model.index_for_path(target)
    win._file_chosen(index)
    win.show()
    qtbot.wait(1)
    viewport = win.table.viewport()

    pos = mw.QPoint(
        win.table.columnViewportPosition(2) + 8,
        win.table.rowViewportPosition(0) + 8,
    )
    idx = win.table.indexAt(pos)
    assert idx.isValid()

    shown: list[tuple[object, ...]] = []
    monkeypatch.setattr(mw.QToolTip, "showText", lambda *args: shown.append(args))

    win._tooltip_index = mw.QModelIndex()
    win._show_delayed_tooltip()
    assert shown == []

    win._tooltip_index = idx
    monkeypatch.setattr(
        mw.QCursor,
        "pos",
        staticmethod(lambda: viewport.mapToGlobal(mw.QPoint(-10, -10))),
    )
    win._show_delayed_tooltip()
    assert shown == []

    win._tooltip_pos = viewport.mapToGlobal(pos)
    monkeypatch.setattr(mw.QCursor, "pos", staticmethod(lambda: win._tooltip_pos))
    win._show_delayed_tooltip()
    assert len(shown) == 1


def test_row_height_cache_helpers_cover_subset_and_full_clear_paths(
    qtbot, tmp_path
) -> None:
    """Verify row-height cache helpers handle model-missing and cache-clear branches."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    win.table.setModel(None)
    assert win._row_height_cache_signature() == ()

    win._row_height_cache = {0: 24, 1: 30}
    win._row_height_cache_key = (100, 200, 300, 120)
    win._clear_row_height_cache(rows=[0, 99])
    assert win._row_height_cache == {1: 30}
    assert win._row_height_cache_key == (100, 200, 300, 120)

    win._clear_row_height_cache()
    assert win._row_height_cache == {}
    assert win._row_height_cache_key is None


def test_resize_visible_rows_covers_cached_budget_resume_and_zero_height_paths(
    qtbot, tmp_path, monkeypatch
) -> None:
    """Verify row-resize loop handles cached-row budget resume and zero-height rows."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    target = root / "BE" / "ui.txt"
    index = win.fs_model.index_for_path(target)
    win._file_chosen(index)

    win._wrap_text = True

    cached_height = max(1, win.table.rowHeight(0)) + 7
    win._row_height_cache = {0: cached_height}
    win._row_height_cache_key = win._row_height_cache_signature()
    win._pending_row_span = (0, 0)
    win._row_resize_cursor = None
    win._row_resize_budget_ms = 0
    win._resize_visible_rows()
    assert win.table.rowHeight(0) == cached_height
    assert win._row_resize_cursor == 1
    assert win._pending_row_span == (0, 0)
    assert win._row_resize_timer.isActive() is True

    win._row_resize_timer.stop()
    win._row_height_cache.clear()
    win._pending_row_span = (999, 999)
    win._row_resize_cursor = None
    win._row_resize_budget_ms = 10_000
    monkeypatch.setattr(win.table, "sizeHintForRow", lambda _row: 0)
    win._resize_visible_rows()
    assert win._pending_row_span is None
    assert win._row_resize_cursor is None
    assert win._row_height_cache == {}

    win._pending_row_span = (0, 0)
    win._row_resize_cursor = 5
    win._resize_visible_rows()
    assert win._pending_row_span == (0, 0)
    assert win._row_resize_cursor == 5
