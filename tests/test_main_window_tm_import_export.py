"""Test module for main-window TM import/export and hash-check branches."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from translationzed_py.gui import MainWindow
from translationzed_py.gui import main_window as mw


@pytest.fixture(autouse=True)
def _disable_close_prompt_for_module(monkeypatch):
    """Disable write-on-exit prompt in this module to speed widget teardown."""
    original_init = mw.MainWindow.__init__

    def _patched_init(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        original_init(self, *args, **kwargs)
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

    monkeypatch.setattr(mw.MainWindow, "__init__", _patched_init)


def _make_project(tmp_path: Path) -> Path:
    """Create minimal project fixture for TM workflow tests."""
    root = tmp_path / "proj"
    root.mkdir()
    for locale, text in (("EN", "English"), ("BE", "Belarusian"), ("RU", "Russian")):
        (root / locale).mkdir()
        (root / locale / "language.txt").write_text(
            f"text = {text},\ncharset = UTF-8,\n",
            encoding="utf-8",
        )
    (root / "EN" / "ui.txt").write_text('UI_KEY = "OK"\n', encoding="utf-8")
    (root / "BE" / "ui.txt").write_text('UI_KEY = "Добра"\n', encoding="utf-8")
    (root / "RU" / "ui.txt").write_text('UI_KEY = "Хорошо"\n', encoding="utf-8")
    return root


class _MessageBoxStub:
    """QMessageBox stub that supports instance and static call patterns."""

    Warning = 1
    Question = 2
    AcceptRole = 3
    RejectRole = 4
    StandardButton = type("StandardButton", (), {"Yes": 1, "No": 2, "Cancel": 3})
    _warnings: list[tuple[str, str]] = []
    _infos: list[tuple[str, str]] = []

    def __init__(self, *_args, **_kwargs) -> None:
        self._clicked = None
        self._buttons: dict[str, object] = {}
        self._exec_result = int(self.StandardButton.Cancel)

    @staticmethod
    def warning(_parent, title: str, text: str) -> int:
        _MessageBoxStub._warnings.append((title, text))
        return 0

    @staticmethod
    def information(_parent, title: str, text: str) -> int:
        _MessageBoxStub._infos.append((title, text))
        return 0

    def setIcon(self, _icon) -> None:  # type: ignore[no-untyped-def]
        return None

    def setWindowTitle(self, _title: str) -> None:
        return None

    def setText(self, _text: str) -> None:
        return None

    def setInformativeText(self, _text: str) -> None:
        return None

    def setStandardButtons(self, _buttons) -> None:  # type: ignore[no-untyped-def]
        return None

    def addButton(self, label: str, _role):  # type: ignore[no-untyped-def]
        button = object()
        self._buttons[label] = button
        if label == "Continue":
            self._clicked = button
        return button

    def clickedButton(self):  # type: ignore[no-untyped-def]
        return self._clicked

    def exec(self) -> int:
        return self._exec_result


def test_check_en_hash_cache_paths_include_exception_empty_and_mismatch_ack(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    """Verify EN hash check handles exceptions, empty cache, and mismatch acknowledgement."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    monkeypatch.setattr(
        mw,
        "_compute_en_hashes",
        lambda _root: (_ for _ in ()).throw(RuntimeError("fail")),
    )
    assert win._check_en_hash_cache() is True

    monkeypatch.setattr(mw, "_compute_en_hashes", lambda _root: {})
    assert win._check_en_hash_cache() is True

    writes: list[dict[str, str]] = []
    monkeypatch.setattr(mw, "_compute_en_hashes", lambda _root: {"a": "1"})
    monkeypatch.setattr(mw, "_read_en_hash_cache", lambda _root: {})
    monkeypatch.setattr(
        mw, "_write_en_hash_cache", lambda _root, data: writes.append(dict(data))
    )
    assert win._check_en_hash_cache() is True
    assert writes[-1] == {"a": "1"}

    monkeypatch.setattr(mw, "QMessageBox", _MessageBoxStub)
    monkeypatch.setattr(mw, "_read_en_hash_cache", lambda _root: {"a": "0"})
    assert win._check_en_hash_cache() is True


def test_prompt_write_original_returns_yes_no_or_cancel(
    qtbot, tmp_path, monkeypatch
) -> None:
    """Verify prompt write helper maps message-box result to yes/no/cancel strings."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    class _Box(_MessageBoxStub):
        """Message box with configurable exec return value."""

        _next = int(_MessageBoxStub.StandardButton.Cancel)

        def exec(self) -> int:
            return self._next

    monkeypatch.setattr(mw, "QMessageBox", _Box)
    _Box._next = int(_MessageBoxStub.StandardButton.Yes)
    assert win._prompt_write_original() == "yes"
    _Box._next = int(_MessageBoxStub.StandardButton.No)
    assert win._prompt_write_original() == "no"
    _Box._next = int(_MessageBoxStub.StandardButton.Cancel)
    assert win._prompt_write_original() == "cancel"


def test_import_tmx_branches_cover_unavailable_cancel_copy_fail_and_success(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    """Verify TM import handles unavailable store, cancel, copy failure, and sync success."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    monkeypatch.setattr(mw, "QMessageBox", _MessageBoxStub)
    _MessageBoxStub._warnings.clear()

    monkeypatch.setattr(win, "_ensure_tm_store", lambda: False)
    win._import_tmx()
    assert ("TM unavailable", "TM store is not available.") in _MessageBoxStub._warnings

    monkeypatch.setattr(win, "_ensure_tm_store", lambda: True)
    monkeypatch.setattr(
        mw.QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *_args, **_kwargs: ("", "")),
    )
    win._import_tmx()

    monkeypatch.setattr(
        mw.QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *_args, **_kwargs: (str(root / "EN" / "ui.txt"), "")),
    )
    monkeypatch.setattr(
        win,
        "_copy_tmx_to_import_dir",
        lambda _path: (_ for _ in ()).throw(RuntimeError("copy-fail")),
    )
    win._import_tmx()
    assert any(title == "TM import failed" for title, _ in _MessageBoxStub._warnings)

    copied = root / ".tzp" / "tms" / "copied.tmx"
    copied.parent.mkdir(parents=True, exist_ok=True)
    copied.write_text("tmx", encoding="utf-8")
    sync_calls: list[dict[str, object]] = []
    monkeypatch.setattr(win, "_copy_tmx_to_import_dir", lambda _path: copied)
    monkeypatch.setattr(
        win,
        "_sync_tm_import_folder",
        lambda **kwargs: sync_calls.append(kwargs),
    )
    win._import_tmx()
    assert sync_calls == [
        {"interactive": True, "only_paths": {copied}, "show_summary": True}
    ]


def test_export_tmx_and_rebuild_selected_cover_core_branches(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    """Verify TM export/rebuild methods cover unavailable, validation, and success flows."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    monkeypatch.setattr(mw, "QMessageBox", _MessageBoxStub)
    _MessageBoxStub._warnings.clear()
    _MessageBoxStub._infos.clear()

    monkeypatch.setattr(win, "_ensure_tm_store", lambda: False)
    win._export_tmx()
    assert ("TM unavailable", "TM store is not available.") in _MessageBoxStub._warnings

    monkeypatch.setattr(win, "_ensure_tm_store", lambda: True)
    monkeypatch.setattr(
        mw.QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *_args, **_kwargs: ("", "")),
    )
    win._export_tmx()

    class _DialogReject:
        class DialogCode:
            Accepted = 1

        def __init__(self, *_args, **_kwargs):
            pass

        def exec(self) -> int:
            return 0

    monkeypatch.setattr(
        mw.QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *_args, **_kwargs: (str(root / "out.tmx"), "")),
    )
    monkeypatch.setattr(mw, "TmLanguageDialog", _DialogReject)
    win._export_tmx()

    class _DialogInvalid(_DialogReject):
        def exec(self) -> int:
            return self.DialogCode.Accepted

        def source_locale(self) -> str:
            return ""

        def target_locale(self) -> str:
            return ""

    monkeypatch.setattr(mw, "TmLanguageDialog", _DialogInvalid)
    win._export_tmx()
    assert any(title == "Invalid locales" for title, _ in _MessageBoxStub._warnings)

    class _DialogValid(_DialogReject):
        def exec(self) -> int:
            return self.DialogCode.Accepted

        def source_locale(self) -> str:
            return "EN"

        def target_locale(self) -> str:
            return "BE"

    monkeypatch.setattr(mw, "TmLanguageDialog", _DialogValid)
    win._tm_store = type(
        "_Store",
        (),
        {"export_tmx": staticmethod(lambda *_args, **_kwargs: 7)},
    )()
    win._export_tmx()
    assert any(title == "TMX export complete" for title, _ in _MessageBoxStub._infos)

    monkeypatch.setattr(win, "_ensure_tm_store", lambda: False)
    win._rebuild_tm_selected()
    monkeypatch.setattr(win, "_ensure_tm_store", lambda: True)
    win._selected_locales = ["EN"]
    win._rebuild_tm_selected()
    assert any(title == "TM rebuild" for title, _ in _MessageBoxStub._infos)

    start_calls: list[tuple[list[str], bool, bool]] = []
    monkeypatch.setattr(
        win,
        "_start_tm_rebuild",
        lambda locales, interactive, force: start_calls.append(
            (list(locales), bool(interactive), bool(force))
        ),
    )
    win._selected_locales = ["EN", "BE", "RU"]
    win._rebuild_tm_selected()
    assert start_calls == [(["BE", "RU"], True, True)]


def test_open_project_covers_cancel_aborted_and_success_paths(
    qtbot, tmp_path, monkeypatch
) -> None:
    """Verify open-project handles cancel, aborted child startup, and successful open."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    monkeypatch.setattr(
        mw.QFileDialog,
        "getExistingDirectory",
        staticmethod(lambda *_args, **_kwargs: ""),
    )
    win._open_project()
    assert win._child_windows == []

    picked = str(root)
    monkeypatch.setattr(
        mw.QFileDialog,
        "getExistingDirectory",
        staticmethod(lambda *_args, **_kwargs: picked),
    )
    created: list[object] = []

    class _FakeWindow:
        def __init__(self, _path: str) -> None:
            self._startup_aborted = True
            created.append(self)

        def show(self) -> None:
            raise AssertionError("show() must not run when startup is aborted")

    monkeypatch.setattr(mw, "MainWindow", _FakeWindow)
    win._open_project()
    assert len(created) == 1
    assert win._child_windows == []

    created.clear()

    class _FakeWindowOk:
        def __init__(self, _path: str) -> None:
            self._startup_aborted = False
            self.shown = False
            created.append(self)

        def show(self) -> None:
            self.shown = True

    monkeypatch.setattr(mw, "MainWindow", _FakeWindowOk)
    win._open_project()
    assert len(created) == 1
    assert created[0].shown is True
    assert win._child_windows == [created[0]]


def test_resolve_pending_tmx_delegates_sync_with_pending_only(
    qtbot, tmp_path, monkeypatch
) -> None:
    """Verify resolve-pending TMX forwards pending-only interactive sync options."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        win,
        "_sync_tm_import_folder",
        lambda **kwargs: calls.append(kwargs),
    )
    win._resolve_pending_tmx()
    assert calls == [
        {"interactive": True, "pending_only": True, "show_summary": True}
    ]


def test_export_tmx_uses_current_file_locale_and_handles_store_export_exception(
    qtbot, tmp_path, monkeypatch
) -> None:
    """Verify TM export derives dialog default target from current file and warns on failure."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    index = win.fs_model.index_for_path(root / "BE" / "ui.txt")
    win._file_chosen(index)
    monkeypatch.setattr(win, "_ensure_tm_store", lambda: True)
    monkeypatch.setattr(
        mw.QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *_args, **_kwargs: (str(root / "out.tmx"), "")),
    )
    monkeypatch.setattr(mw, "QMessageBox", _MessageBoxStub)
    _MessageBoxStub._warnings.clear()
    captured_targets: list[str | None] = []

    class _Dialog:
        class DialogCode:
            Accepted = 1

        def __init__(self, _langs, **kwargs):  # type: ignore[no-untyped-def]
            captured_targets.append(kwargs.get("default_target"))

        def exec(self) -> int:
            return self.DialogCode.Accepted

        @staticmethod
        def source_locale() -> str:
            return "EN"

        @staticmethod
        def target_locale() -> str:
            return "BE"

    monkeypatch.setattr(mw, "TmLanguageDialog", _Dialog)
    win._tm_store = type(
        "_Store",
        (),
        {
            "export_tmx": staticmethod(
                lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom"))
            )
        },
    )()
    win._export_tmx()
    assert captured_targets == ["BE"]
    assert ("TMX export failed", "boom") in _MessageBoxStub._warnings


def test_show_copyable_report_executes_dialog(qtbot, tmp_path, monkeypatch) -> None:
    """Verify copyable report builds and executes a dialog without blocking tests."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    calls: list[str] = []
    monkeypatch.setattr(
        mw.QDialog,
        "exec",
        lambda _self: calls.append("exec") or 0,
        raising=False,
    )

    win._show_copyable_report("TM diagnostics", "line-1\nline-2")
    assert calls == ["exec"]
