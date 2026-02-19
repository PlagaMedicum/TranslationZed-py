"""Test module for main-window bootstrap and helper utilities."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent
from PySide6.QtGui import QFocusEvent

from translationzed_py.gui import main_window as mw


def _make_project(tmp_path: Path) -> Path:
    """Create a minimal two-locale project fixture."""
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


def test_in_test_mode_and_pref_parsers_handle_common_inputs(monkeypatch) -> None:
    """Verify helper parsers normalize booleans/ints and detect test mode flags."""
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("TZP_TESTING", raising=False)
    assert mw._in_test_mode() is False

    monkeypatch.setenv("TZP_TESTING", "1")
    assert mw._in_test_mode() is True

    assert mw._bool_from_pref(True, default=False) is True
    assert mw._bool_from_pref("yes", default=False) is True
    assert mw._bool_from_pref("off", default=True) is False
    assert mw._bool_from_pref("unknown", default=True) is True

    assert mw._int_from_pref("10", default=3, min_value=0, max_value=99) == 10
    assert mw._int_from_pref("999", default=3, min_value=0, max_value=50) == 50
    assert mw._int_from_pref("-5", default=3, min_value=0, max_value=50) == 0
    assert mw._int_from_pref("bad", default=7, min_value=0, max_value=50) == 7


def test_patch_message_boxes_uses_test_shortcuts_and_non_test_fallback(
    monkeypatch,
) -> None:
    """Verify message-box patching returns Ok in test mode and defers otherwise."""
    monkeypatch.setattr(mw, "_TEST_DIALOGS_PATCHED", False)
    monkeypatch.setattr(mw, "_ORIG_QMESSAGEBOX_EXEC", None)
    monkeypatch.setattr(mw, "_ORIG_QMESSAGEBOX_WARNING", None)
    monkeypatch.setattr(mw, "_ORIG_QMESSAGEBOX_CRITICAL", None)
    monkeypatch.setattr(mw, "_ORIG_QMESSAGEBOX_INFORMATION", None)

    test_mode = {"enabled": True}
    monkeypatch.setattr(mw, "_in_test_mode", lambda: test_mode["enabled"])

    class _FakeMessageBox:
        """QMessageBox replacement used to validate patched handlers."""

        class StandardButton:
            Ok = 42

        @staticmethod
        def exec(_self) -> int:
            return 10

        @staticmethod
        def warning(*_args, **_kwargs) -> int:
            return 11

        @staticmethod
        def critical(*_args, **_kwargs) -> int:
            return 12

        @staticmethod
        def information(*_args, **_kwargs) -> int:
            return 13

    monkeypatch.setattr(mw, "QMessageBox", _FakeMessageBox)
    mw._patch_message_boxes_for_tests()

    assert mw._TEST_DIALOGS_PATCHED is True
    assert mw.QMessageBox.exec(object()) == int(_FakeMessageBox.StandardButton.Ok)
    assert mw.QMessageBox.warning(object(), "t", "m") == int(
        _FakeMessageBox.StandardButton.Ok
    )
    assert mw.QMessageBox.critical(object(), "t", "m") == int(
        _FakeMessageBox.StandardButton.Ok
    )
    assert mw.QMessageBox.information(object(), "t", "m") == int(
        _FakeMessageBox.StandardButton.Ok
    )

    test_mode["enabled"] = False
    assert mw.QMessageBox.exec(object()) == 10
    assert mw.QMessageBox.warning(object(), "t", "m") == 11
    assert mw.QMessageBox.critical(object(), "t", "m") == 12
    assert mw.QMessageBox.information(object(), "t", "m") == 13


def test_commit_plain_text_edit_focus_hooks_trigger_callbacks(qtbot) -> None:
    """Verify focus in/out events call configured commit and focus callbacks."""
    events: list[str] = []
    widget = mw._CommitPlainTextEdit(
        commit_cb=lambda: events.append("commit"),
        focus_cb=lambda: events.append("focus"),
    )
    qtbot.addWidget(widget)

    widget.focusInEvent(QFocusEvent(QEvent.FocusIn))
    widget.focusOutEvent(QFocusEvent(QEvent.FocusOut))

    assert events == ["focus", "commit"]


def test_main_window_startup_aborts_when_picker_cancelled(monkeypatch) -> None:
    """Verify startup returns early when root picker is cancelled."""

    class _Prefs:
        """Preferences stub that requests startup directory picker."""

        def resolve_startup_root(self, *, project_root):  # type: ignore[no-untyped-def]
            _ = project_root
            return SimpleNamespace(root=None, default_root="", requires_picker=True)

    monkeypatch.setattr(mw, "_PreferencesService", _Prefs)
    monkeypatch.setattr(
        mw.QFileDialog,
        "getExistingDirectory",
        staticmethod(lambda *_args, **_kwargs: ""),
    )
    win = mw.MainWindow(project_root=None)
    assert win._startup_aborted is True


def test_main_window_startup_warns_for_missing_picked_root(
    tmp_path,
    monkeypatch,
) -> None:
    """Verify startup warns and aborts when selected project root is missing."""
    selected = tmp_path / "missing-root"
    persisted: list[str] = []
    warnings: list[tuple[str, str]] = []

    class _Prefs:
        """Preferences stub with picker-driven startup flow."""

        def resolve_startup_root(self, *, project_root):  # type: ignore[no-untyped-def]
            _ = project_root
            return SimpleNamespace(root=None, default_root="", requires_picker=True)

        def persist_default_root(self, value: str) -> None:
            persisted.append(value)

    monkeypatch.setattr(mw, "_PreferencesService", _Prefs)
    monkeypatch.setattr(
        mw.QFileDialog,
        "getExistingDirectory",
        staticmethod(lambda *_args, **_kwargs: str(selected)),
    )
    monkeypatch.setattr(
        mw.QMessageBox,
        "warning",
        staticmethod(lambda _self, title, text: warnings.append((title, text))),
    )

    win = mw.MainWindow(project_root=None)
    assert win._startup_aborted is True
    assert persisted == [str(selected.resolve())]
    assert warnings == [("Invalid project root", str(selected.resolve()))]


def test_init_locales_handles_scan_exceptions(qtbot, tmp_path, monkeypatch) -> None:
    """Verify locale init handles scan failures with critical error fallback."""
    root = _make_project(tmp_path)
    win = mw.MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    errors: list[tuple[str, str]] = []

    def _raise_scan(_root: Path):  # type: ignore[no-untyped-def]
        raise RuntimeError("scan failed")

    monkeypatch.setattr(mw, "scan_root_with_errors", _raise_scan)
    monkeypatch.setattr(
        mw.QMessageBox,
        "critical",
        staticmethod(lambda _parent, title, text: errors.append((title, text))),
    )

    win._init_locales(selected_locales=["BE"])
    assert errors == [("Invalid language.txt", "scan failed")]
    assert win._locales == {}
    assert win._selected_locales == []


def test_init_locales_covers_malformed_warning_and_empty_selectable_branch(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    """Verify locale init warns on malformed files and handles EN-only scans."""
    root = _make_project(tmp_path)
    win = mw.MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    class _WarningBox:
        """Message-box stub used to capture malformed-language warnings."""

        Warning = 1
        instances: list[_WarningBox] = []

        def __init__(self, *_args, **_kwargs):
            self.title = ""
            self.text = ""
            self.detail = ""
            self.executed = False
            _WarningBox.instances.append(self)

        def setIcon(self, _icon):
            return None

        def setWindowTitle(self, title: str) -> None:
            self.title = title

        def setText(self, text: str) -> None:
            self.text = text

        def setDetailedText(self, detail: str) -> None:
            self.detail = detail

        def exec(self) -> None:
            self.executed = True

    calls: list[str] = []
    monkeypatch.setattr(mw, "QMessageBox", _WarningBox)
    monkeypatch.setattr(
        win, "_schedule_cache_migration", lambda: calls.append("migrate")
    )
    monkeypatch.setattr(
        win, "_schedule_post_locale_tasks", lambda: calls.append("post")
    )
    monkeypatch.setattr(win, "_warn_orphan_caches", lambda: calls.append("warn"))
    monkeypatch.setattr(mw.QTimer, "singleShot", lambda _ms, callback: callback())

    def _scan_with_errors(_root: Path):  # type: ignore[no-untyped-def]
        return {"EN": "English", "BE": "Belarusian"}, ["BE/language.txt: malformed"]

    monkeypatch.setattr(mw, "scan_root_with_errors", _scan_with_errors)
    win._init_locales(selected_locales=["BE"])

    assert _WarningBox.instances
    warning = _WarningBox.instances[-1]
    assert warning.executed is True
    assert warning.title == "Malformed language.txt"
    assert "skipped" in warning.text
    assert warning.detail == "BE/language.txt: malformed"
    assert win._selected_locales == ["BE"]
    assert calls == ["migrate", "warn", "post"]

    monkeypatch.setattr(
        mw, "scan_root_with_errors", lambda _root: ({"EN": "English"}, [])
    )
    win._selected_locales = ["BE"]
    win._init_locales(selected_locales=None)
    assert win._selected_locales == []


def test_init_locales_returns_empty_when_locale_dialog_is_cancelled(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    """Verify locale init returns no selection when chooser dialog is cancelled."""
    root = _make_project(tmp_path)
    win = mw.MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    class _Dialog:
        class DialogCode:
            Accepted = 1

        def __init__(self, *_args, **_kwargs):
            pass

        def exec(self) -> int:
            return 0

        def selected_codes(self) -> list[str]:
            return ["BE"]

    monkeypatch.setattr(mw, "LocaleChooserDialog", _Dialog)
    monkeypatch.setattr(
        mw._ProjectSessionService,
        "resolve_requested_locales",
        lambda _self, **_kwargs: None,
    )
    win._selected_locales = ["BE"]
    win._init_locales(selected_locales=None)
    assert win._selected_locales == []


def test_init_locales_malformed_scan_with_chooser_accept_schedules_followups(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    """Verify malformed-locale warning + accepted chooser path schedules follow-up tasks."""
    root = _make_project(tmp_path)
    win = mw.MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    win._post_locale_timer.stop()
    win._pending_post_locale_plan = SimpleNamespace(should_schedule=False)
    delegate = win._project_session_service

    class _WarningBox:
        """Message-box stub used to capture malformed-language warning rendering."""

        Warning = 1
        instances: list[_WarningBox] = []

        def __init__(self, *_args, **_kwargs):
            self.title = ""
            self.text = ""
            self.detail = ""
            self.executed = False
            _WarningBox.instances.append(self)

        def setIcon(self, _icon):
            return None

        def setWindowTitle(self, title: str) -> None:
            self.title = title

        def setText(self, text: str) -> None:
            self.text = text

        def setDetailedText(self, detail: str) -> None:
            self.detail = detail

        def exec(self) -> None:
            self.executed = True

    class _Dialog:
        class DialogCode:
            Accepted = 1

        def __init__(self, *_args, **_kwargs):
            pass

        def exec(self) -> int:
            return self.DialogCode.Accepted

        def selected_codes(self) -> list[str]:
            return ["BE"]

    class _Service:
        def __getattr__(self, name: str):
            return getattr(delegate, name)

        @staticmethod
        def resolve_requested_locales(**_kwargs):  # type: ignore[no-untyped-def]
            return None

        @staticmethod
        def build_locale_selection_plan(**_kwargs):  # type: ignore[no-untyped-def]
            return SimpleNamespace(selected_locales=["BE"])

    call_log: list[str] = []
    monkeypatch.setattr(mw, "QMessageBox", _WarningBox)
    monkeypatch.setattr(mw, "LocaleChooserDialog", _Dialog)
    monkeypatch.setattr(win, "_project_session_service", _Service())
    monkeypatch.setattr(
        win, "_schedule_cache_migration", lambda: call_log.append("migrate")
    )
    monkeypatch.setattr(win, "_warn_orphan_caches", lambda: call_log.append("warn"))
    monkeypatch.setattr(
        win,
        "_schedule_post_locale_tasks",
        lambda: call_log.append("post"),
    )
    monkeypatch.setattr(mw.QTimer, "singleShot", lambda _ms, callback: callback())
    monkeypatch.setattr(
        mw,
        "scan_root_with_errors",
        lambda _root: (  # type: ignore[no-untyped-def]
            {"EN": "English", "BE": "Belarusian"},
            ["BE/language.txt: trailing comma"],
        ),
    )

    win._init_locales(selected_locales=None)

    assert win._selected_locales == ["BE"]
    assert call_log == ["migrate", "warn", "post"]
    assert _WarningBox.instances
    warning = _WarningBox.instances[-1]
    assert warning.executed is True
    assert warning.title == "Malformed language.txt"
    assert warning.detail == "BE/language.txt: trailing comma"


def test_init_locales_rejected_plan_clears_selection_without_post_tasks(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    """Verify locale-plan rejection clears selection and skips orphan/post scheduling."""
    root = _make_project(tmp_path)
    win = mw.MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    win._post_locale_timer.stop()
    win._pending_post_locale_plan = SimpleNamespace(should_schedule=False)
    delegate = win._project_session_service

    class _Service:
        def __getattr__(self, name: str):
            return getattr(delegate, name)

        @staticmethod
        def resolve_requested_locales(**_kwargs):  # type: ignore[no-untyped-def]
            return ["BE"]

        @staticmethod
        def build_locale_selection_plan(**_kwargs):  # type: ignore[no-untyped-def]
            return None

    calls: list[str] = []
    scheduled: list[int] = []
    monkeypatch.setattr(
        mw,
        "scan_root_with_errors",
        lambda _root: ({"EN": "English", "BE": "Belarusian"}, []),  # type: ignore[no-untyped-def]
    )
    monkeypatch.setattr(win, "_project_session_service", _Service())
    monkeypatch.setattr(
        win, "_schedule_cache_migration", lambda: calls.append("migrate")
    )
    monkeypatch.setattr(
        win,
        "_schedule_post_locale_tasks",
        lambda: calls.append("post"),
    )
    monkeypatch.setattr(
        mw.QTimer,
        "singleShot",
        lambda ms, _callback: scheduled.append(int(ms)),
    )

    win._selected_locales = ["BE"]
    win._tm_bootstrap_pending = False
    win._init_locales(selected_locales=["BE"])

    assert win._selected_locales == []
    assert win._tm_bootstrap_pending is False
    assert calls == ["migrate"]
    assert scheduled == []


def test_main_window_startup_aborts_when_en_hash_guard_rejects(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    """Verify startup aborts when EN hash guard blocks initialization."""
    root = _make_project(tmp_path)
    monkeypatch.setattr(mw.MainWindow, "_check_en_hash_cache", lambda _self: False)

    win = mw.MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    assert win._startup_aborted is True


def test_warn_orphan_caches_purge_deletes_existing_and_ignores_unlink_errors(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    """Verify orphan-cache purge unlinks existing files and ignores unlink failures."""
    root = _make_project(tmp_path)
    win = mw.MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    orphan_keep = root / ".tzp" / "cache" / "BE" / "orphan_keep.bin"
    orphan_keep.parent.mkdir(parents=True, exist_ok=True)
    orphan_keep.write_bytes(b"cache")
    orphan_missing = root / ".tzp" / "cache" / "BE" / "orphan_missing.bin"
    win._post_locale_timer.stop()
    win._pending_post_locale_plan = SimpleNamespace(should_schedule=False)

    class _Service:
        @staticmethod
        def collect_orphan_cache_paths(  # type: ignore[no-untyped-def]
            *,
            root,
            selected_locales,
            warned_locales,
        ):
            _ = root
            _ = selected_locales
            _ = warned_locales
            return {"BE": [orphan_keep, orphan_missing]}

        @staticmethod
        def build_orphan_cache_warning(  # type: ignore[no-untyped-def]
            *,
            locale,
            orphan_paths,
            root,
            preview_limit=20,
        ):
            _ = locale
            _ = root
            _ = preview_limit
            return SimpleNamespace(
                window_title="Orphan cache files",
                text="Locale BE has cache files without source files.",
                informative_text="Purge recommended.",
                detailed_text="orphan entries",
                orphan_paths=list(orphan_paths),
            )

    class _PurgeMessageBox:
        Warning = 1
        AcceptRole = 2
        RejectRole = 3

        def __init__(self, *_args, **_kwargs):
            self._clicked = None

        def setIcon(self, _icon):
            return None

        def setWindowTitle(self, _title):
            return None

        def setText(self, _text):
            return None

        def setInformativeText(self, _text):
            return None

        def setDetailedText(self, _text):
            return None

        def addButton(self, label, _role):  # type: ignore[no-untyped-def]
            button = object()
            if str(label) == "Purge":
                self._clicked = button
            return button

        def exec(self):
            return None

        def clickedButton(self):
            return self._clicked

    monkeypatch.setattr(win, "_project_session_service", _Service())
    monkeypatch.setattr(mw, "QMessageBox", _PurgeMessageBox)
    win._warn_orphan_caches()

    assert orphan_keep.exists() is False
    assert "BE" in win._orphan_cache_warned_locales


def test_warn_orphan_caches_tracks_warned_locales_and_respects_dismiss(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    """Verify orphan warning supports purge/dismiss paths and avoids duplicate warnings."""
    root = _make_project(tmp_path)
    win = mw.MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    win._post_locale_timer.stop()
    win._pending_post_locale_plan = SimpleNamespace(should_schedule=False)
    delegate = win._project_session_service

    orphan_purge = root / ".tzp" / "cache" / "BE" / "purge.bin"
    orphan_keep = root / ".tzp" / "cache" / "RU" / "keep.bin"
    orphan_purge.parent.mkdir(parents=True, exist_ok=True)
    orphan_keep.parent.mkdir(parents=True, exist_ok=True)
    orphan_purge.write_bytes(b"purge")
    orphan_keep.write_bytes(b"keep")

    collect_calls: list[tuple[str, ...]] = []

    class _Service:
        def __getattr__(self, name: str):
            return getattr(delegate, name)

        @staticmethod
        def collect_orphan_cache_paths(  # type: ignore[no-untyped-def]
            *,
            root,
            selected_locales,
            warned_locales,
        ):
            _ = root
            _ = selected_locales
            collect_calls.append(tuple(sorted(str(loc) for loc in warned_locales)))
            if warned_locales:
                return {}
            return {"BE": [orphan_purge], "RU": [orphan_keep]}

        @staticmethod
        def build_orphan_cache_warning(  # type: ignore[no-untyped-def]
            *,
            locale,
            orphan_paths,
            root,
            preview_limit=20,
        ):
            _ = root
            _ = preview_limit
            return SimpleNamespace(
                window_title=f"Orphan cache files ({locale})",
                text=f"Locale {locale} has orphan cache files.",
                informative_text="Use Purge to delete stale cache entries.",
                detailed_text=f"{locale} details",
                orphan_paths=list(orphan_paths),
            )

    class _DecisionMessageBox:
        Warning = 1
        AcceptRole = 2
        RejectRole = 3
        instances: list[_DecisionMessageBox] = []

        def __init__(self, *_args, **_kwargs):
            self._title = ""
            self._text = ""
            self._info = ""
            self._detail = ""
            self._purge = None
            self._dismiss = None
            _DecisionMessageBox.instances.append(self)

        def setIcon(self, _icon):
            return None

        def setWindowTitle(self, title: str):
            self._title = title

        def setText(self, text: str):
            self._text = text

        def setInformativeText(self, text: str):
            self._info = text

        def setDetailedText(self, text: str):
            self._detail = text

        def addButton(self, label, _role):  # type: ignore[no-untyped-def]
            button = object()
            if str(label) == "Purge":
                self._purge = button
            elif str(label) == "Dismiss":
                self._dismiss = button
            return button

        def exec(self):
            return None

        def clickedButton(self):
            if "BE" in self._title:
                return self._purge
            return self._dismiss

    monkeypatch.setattr(win, "_project_session_service", _Service())
    monkeypatch.setattr(mw, "QMessageBox", _DecisionMessageBox)

    win._warn_orphan_caches()
    win._warn_orphan_caches()

    assert orphan_purge.exists() is False
    assert orphan_keep.exists() is True
    assert win._orphan_cache_warned_locales == {"BE", "RU"}
    assert collect_calls == [(), ("BE", "RU")]
    assert len(_DecisionMessageBox.instances) == 2
    assert _DecisionMessageBox.instances[0]._title == "Orphan cache files (BE)"
    assert _DecisionMessageBox.instances[0]._text == "Locale BE has orphan cache files."
    assert _DecisionMessageBox.instances[0]._info.startswith("Use Purge")
    assert _DecisionMessageBox.instances[0]._detail == "BE details"
