"""Test module for main-window preference application and TM action adapters."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from translationzed_py.core.preferences import load as load_preferences
from translationzed_py.core.preferences import save as save_preferences
from translationzed_py.gui import MainWindow
from translationzed_py.gui import main_window as mw


def _make_project(tmp_path: Path) -> Path:
    """Create minimal project fixture with EN and BE locales."""
    root = tmp_path / "proj"
    root.mkdir()
    for locale, text in (("EN", "English"), ("BE", "Belarusian")):
        (root / locale).mkdir()
        (root / locale / "language.txt").write_text(
            f"text = {text},\ncharset = UTF-8,\n",
            encoding="utf-8",
        )
    (root / "EN" / "ui.txt").write_text('UI_KEY = "OK"\n', encoding="utf-8")
    (root / "BE" / "ui.txt").write_text('UI_KEY = "Добра"\n', encoding="utf-8")
    return root


class _MsgBox:
    """Minimal QMessageBox stub for warning-dialog assertions."""

    Warning = 1
    _instances: list[_MsgBox] = []

    def __init__(self, *_args, **_kwargs) -> None:
        self.title = ""
        self.text = ""
        self.details = ""
        _MsgBox._instances.append(self)

    def setIcon(self, _icon) -> None:  # type: ignore[no-untyped-def]
        return None

    def setWindowTitle(self, title: str) -> None:
        self.title = title

    def setText(self, text: str) -> None:
        self.text = text

    def setDetailedText(self, text: str) -> None:
        self.details = text

    def exec(self) -> int:
        return 0


def test_apply_preferences_updates_state_and_triggers_follow_up_actions(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    """Verify applying preferences updates state and triggers dependent workflows."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    win.search_edit.setText("needle")
    win._left_stack.setCurrentIndex(1)
    win._current_model = object()  # type: ignore[assignment]

    calls: list[str] = []
    monkeypatch.setattr(
        win, "_apply_theme_mode", lambda *_args, **_kwargs: calls.append("theme")
    )
    monkeypatch.setattr(
        win, "_update_render_cost_flags", lambda: calls.append("render")
    )
    monkeypatch.setattr(
        win, "_update_large_file_mode", lambda: calls.append("large_mode")
    )
    monkeypatch.setattr(win, "_apply_wrap_mode", lambda: calls.append("wrap"))
    monkeypatch.setattr(
        win, "_apply_text_visual_options", lambda: calls.append("visual")
    )
    monkeypatch.setattr(
        win, "_set_qa_findings", lambda _rows: calls.append("qa_findings")
    )
    monkeypatch.setattr(
        win, "_set_qa_panel_message", lambda _msg: calls.append("qa_msg")
    )
    monkeypatch.setattr(
        win, "_apply_tm_preferences_actions", lambda _values: calls.append("tm_actions")
    )
    monkeypatch.setattr(win, "_schedule_search", lambda *_args: calls.append("search"))
    monkeypatch.setattr(win, "_persist_preferences", lambda: calls.append("persist"))
    monkeypatch.setattr(win, "_resolve_pending_tmx", lambda: calls.append("resolve"))
    monkeypatch.setattr(win, "_export_tmx", lambda: calls.append("export"))
    monkeypatch.setattr(win, "_rebuild_tm_selected", lambda: calls.append("rebuild"))
    monkeypatch.setattr(win, "_show_tm_diagnostics", lambda: calls.append("diag"))
    monkeypatch.setattr(
        win,
        "_sync_tm_import_folder",
        lambda **_kwargs: calls.append("sync_tm"),
    )
    monkeypatch.setattr(win, "_schedule_tm_update", lambda: calls.append("tm_update"))
    monkeypatch.setattr(
        win, "_update_replace_enabled", lambda *_args: calls.append("replace")
    )
    monkeypatch.setattr(win, "_update_status_bar", lambda: calls.append("status"))
    monkeypatch.setattr(
        mw,
        "_resolve_qa_preferences",
        lambda _values, current: (
            (False, False, False, False, False, False, False, False),
            current != (False, False, False, False, False, False, False, False),
        ),
    )
    monkeypatch.setattr(
        mw, "_apply_source_ref_preferences_for_window", lambda _win, _values: None
    )

    values = {
        "theme_mode": "LIGHT",
        "prompt_write_on_exit": False,
        "wrap_text": True,
        "large_text_optimizations": not win._large_text_optimizations,
        "visual_highlight": not win._visual_highlight,
        "visual_whitespace": not win._visual_whitespace,
        "default_root": str(root),
        "tm_import_dir": "",
        "search_scope": "LOCALE",
        "replace_scope": "POOL",
        "tm_resolve_pending": True,
        "tm_export_tmx": True,
        "tm_rebuild": True,
        "tm_show_diagnostics": True,
    }
    win._apply_preferences(values)

    assert "theme" in calls
    assert "render" in calls
    assert "large_mode" in calls
    assert "wrap" in calls
    assert "visual" in calls
    assert "qa_findings" in calls
    assert "qa_msg" in calls
    assert "tm_actions" in calls
    assert "search" in calls
    assert "persist" in calls
    assert "resolve" in calls
    assert "export" in calls
    assert "rebuild" in calls
    assert "diag" in calls
    assert "sync_tm" in calls
    assert "tm_update" in calls
    assert "replace" in calls
    assert "status" in calls


def test_apply_tm_preferences_actions_handles_empty_store_guard_sync_and_failures(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    """Verify TM preference action adapter covers empty, guard, sync, and failure branches."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    monkeypatch.setattr(mw, "QMessageBox", _MsgBox)
    _MsgBox._instances.clear()

    class _Actions:
        def __init__(
            self, *, empty: bool, remove_paths: set[str] | None = None
        ) -> None:
            self._empty = empty
            self.remove_paths = set(remove_paths or set())

        def is_empty(self) -> bool:
            return self._empty

    class _Report:
        def __init__(self, *, sync_paths=None, failures=None) -> None:  # type: ignore[no-untyped-def]
            self.sync_paths = list(sync_paths or [])
            self.failures = list(failures or [])

    applied: list[set[str]] = []
    sync_calls: list[set[Path]] = []

    class _Workflow:
        def __init__(self) -> None:
            self.actions = _Actions(empty=True)
            self.report = _Report()

        def build_preferences_actions(self, _values):  # type: ignore[no-untyped-def]
            return self.actions

        def apply_preferences_actions(self, **kwargs):  # type: ignore[no-untyped-def]
            actions = kwargs["actions"]
            applied.append(set(actions.remove_paths))
            return self.report

    workflow = _Workflow()
    win._tm_workflow = workflow  # type: ignore[assignment]
    monkeypatch.setattr(
        win,
        "_sync_tm_import_folder",
        lambda **kwargs: sync_calls.append(set(kwargs["only_paths"])),
    )

    win._apply_tm_preferences_actions({})
    assert applied == []

    workflow.actions = _Actions(empty=False, remove_paths={"a.tmx"})
    monkeypatch.setattr(win, "_ensure_tm_store", lambda: False)
    win._apply_tm_preferences_actions({})
    assert applied == []

    monkeypatch.setattr(win, "_ensure_tm_store", lambda: True)
    monkeypatch.setattr(win, "_confirm_tm_file_deletion", lambda _paths: False)
    workflow.report = _Report(sync_paths=[root / "tm-a.tmx"], failures=["boom"])
    win._apply_tm_preferences_actions({})

    assert applied == [set()]
    assert sync_calls == [{root / "tm-a.tmx"}]
    assert _MsgBox._instances
    assert _MsgBox._instances[0].title == "TM preferences"
    assert _MsgBox._instances[0].text == "Some TM file operations failed."
    assert _MsgBox._instances[0].details == "boom"


def test_noncritical_ui_layout_and_toggle_state_persist_across_restart(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    """Verify tree/column layout extras and search-case toggle survive restart."""
    monkeypatch.chdir(tmp_path)
    root = _make_project(tmp_path)

    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    index = win.fs_model.index_for_path(root / "BE" / "ui.txt")
    win._file_chosen(index)

    win._tree_last_width = 236
    win._key_column_width = 164
    win._status_column_width = 78
    win._source_translation_ratio = 0.37
    win._search_case_sensitive = True
    win._prefs_extras["TREE_PANEL_WIDTH"] = "236"
    win._prefs_extras["TABLE_KEY_WIDTH"] = "164"
    win._prefs_extras["TABLE_STATUS_WIDTH"] = "78"
    win._prefs_extras["TABLE_SRC_RATIO"] = "0.370000"
    win._prefs_extras["TABLE_COLUMNS_USER_RESIZED"] = "1"
    win._prefs_extras["SEARCH_CASE_SENSITIVE"] = "1"
    win._persist_preferences()

    raw = load_preferences(None)
    extras = dict(raw.get("__extras__", {}))
    assert extras["TREE_PANEL_WIDTH"] == "236"
    assert extras["TABLE_KEY_WIDTH"] == "164"
    assert extras["TABLE_STATUS_WIDTH"] == "78"
    assert extras["TABLE_SRC_RATIO"] == "0.370000"
    assert extras["TABLE_COLUMNS_USER_RESIZED"] == "1"
    assert extras["SEARCH_CASE_SENSITIVE"] == "1"

    win_reopen = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win_reopen)
    assert win_reopen._tree_last_width == 236
    assert win_reopen._key_column_width == 164
    assert win_reopen._status_column_width == 78
    assert win_reopen._search_case_sensitive is True
    assert abs(win_reopen._source_translation_ratio - 0.37) < 0.000001


def test_source_translation_ratio_defaults_to_equal_without_manual_resize_flag(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    """Verify source/translation columns default to 50/50 until user resizes manually."""
    monkeypatch.chdir(tmp_path)
    root = _make_project(tmp_path)
    raw = load_preferences(None)
    extras = dict(raw.get("__extras__", {}))
    extras["TABLE_SRC_RATIO"] = "0.370000"
    extras.pop("TABLE_COLUMNS_USER_RESIZED", None)
    payload = dict(raw)
    payload["__extras__"] = extras
    save_preferences(payload)

    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    assert abs(win._source_translation_ratio - 0.5) < 0.000001
