"""Test module for TM sync-report and import-copy workflows in main window."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from translationzed_py.core.tm_import_sync import TMImportSyncReport
from translationzed_py.gui import MainWindow
from translationzed_py.gui import main_window as mw


def _make_project(tmp_path: Path) -> Path:
    """Create a minimal EN/BE/RU project fixture."""
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


class _FakeMessageBox:
    """Simple QMessageBox stub that records rendered messages."""

    Warning = 1
    Information = 2
    _instances: list[_FakeMessageBox] = []

    def __init__(self, *_args, **_kwargs) -> None:
        self.icon = None
        self.title = ""
        self.text = ""
        self.details = ""
        _FakeMessageBox._instances.append(self)

    @staticmethod
    def warning(_parent, _title, _text):  # type: ignore[no-untyped-def]
        return 0

    def setIcon(self, icon) -> None:  # type: ignore[no-untyped-def]
        self.icon = icon

    def setWindowTitle(self, title: str) -> None:
        self.title = title

    def setText(self, text: str) -> None:
        self.text = text

    def setDetailedText(self, details: str) -> None:
        self.details = details

    def exec(self) -> int:
        return 0


def test_apply_tm_sync_report_renders_issue_summary_and_refreshes_tm_panel(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    """Verify issue report path clears TM cache, refreshes panel, and shows warning."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    calls: list[str] = []
    win._left_stack.setCurrentIndex(1)
    win._tm_workflow = type(
        "_WorkflowSpy",
        (),
        {"clear_cache": staticmethod(lambda: calls.append("clear"))},
    )()
    monkeypatch.setattr(win, "_schedule_tm_update", lambda: calls.append("update"))
    monkeypatch.setattr(mw, "QMessageBox", _FakeMessageBox)
    _FakeMessageBox._instances.clear()

    report = TMImportSyncReport(
        imported_segments=5,
        imported_files=("a.tmx (5 segment(s))",),
        unresolved_files=("pending.tmx",),
        zero_segment_files=("zero.tmx",),
        failures=("failed.tmx: boom",),
        checked_files=("a.tmx", "pending.tmx", "zero.tmx"),
        changed=True,
    )
    win._apply_tm_sync_report(report, interactive=True, show_summary=True)

    assert calls == ["clear", "update"]
    assert len(_FakeMessageBox._instances) == 1
    msg = _FakeMessageBox._instances[0]
    assert msg.icon == _FakeMessageBox.Warning
    assert msg.title == "TM import sync"
    assert "Imported 1 file(s)," in msg.text
    assert "Failures:" in msg.details
    assert "Pending mapping:" in msg.details
    assert "Imported with 0 segments:" in msg.details


def test_apply_tm_sync_report_renders_summary_and_no_change_messages(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    """Verify summary/info branches for imported and no-change sync results."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    monkeypatch.setattr(mw, "QMessageBox", _FakeMessageBox)
    _FakeMessageBox._instances.clear()

    imported = TMImportSyncReport(
        imported_segments=3,
        imported_files=("one.tmx (3 segment(s))",),
        unresolved_files=(),
        zero_segment_files=(),
        failures=(),
        checked_files=("one.tmx",),
        changed=False,
    )
    win._apply_tm_sync_report(imported, interactive=True, show_summary=True)

    unchanged = TMImportSyncReport(
        imported_segments=0,
        imported_files=(),
        unresolved_files=(),
        zero_segment_files=(),
        failures=(),
        checked_files=("one.tmx",),
        changed=False,
    )
    win._apply_tm_sync_report(unchanged, interactive=True, show_summary=True)

    assert len(_FakeMessageBox._instances) == 2
    assert _FakeMessageBox._instances[0].icon == _FakeMessageBox.Information
    assert "Imported 1 file(s)," in _FakeMessageBox._instances[0].text
    assert "Imported:" in _FakeMessageBox._instances[0].details
    assert (
        "No TM files changed (already up to date)."
        in _FakeMessageBox._instances[1].text
    )
    assert "Checked:" in _FakeMessageBox._instances[1].details


def test_sync_tm_import_folder_handles_mkdir_errors_for_interactive_and_non_interactive(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    """Verify sync import folder reports mkdir errors for both interaction modes."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    monkeypatch.setattr(win, "_ensure_tm_store", lambda: True)
    tm_dir = root / ".tm-import"
    monkeypatch.setattr(win, "_tm_import_dir_path", lambda: tm_dir)
    monkeypatch.setattr(
        tm_dir.__class__,
        "mkdir",
        lambda _self, **_kwargs: (_ for _ in ()).throw(OSError("denied")),
    )

    shown: list[tuple[str, int]] = []
    monkeypatch.setattr(
        win.statusBar(), "showMessage", lambda text, ms=0: shown.append((text, ms))
    )
    monkeypatch.setattr(mw, "QMessageBox", _FakeMessageBox)

    win._sync_tm_import_folder(interactive=True)
    win._sync_tm_import_folder(interactive=False)

    assert shown == [("TM import folder unavailable: denied", 5000)]


def test_copy_tmx_to_import_dir_renames_when_target_exists(qtbot, tmp_path) -> None:
    """Verify copying TMX into import folder appends numeric suffix on collisions."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    import_dir = tmp_path / "tm-import"
    win._tm_import_dir = str(import_dir)
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    source = source_dir / "file.tmx"
    source.write_text("tmx", encoding="utf-8")

    import_dir.mkdir(parents=True, exist_ok=True)
    (import_dir / "file.tmx").write_text("existing", encoding="utf-8")
    (import_dir / "file_1.tmx").write_text("existing", encoding="utf-8")

    copied = win._copy_tmx_to_import_dir(source)
    assert copied.name == "file_2.tmx"
    assert copied.exists() is True

    same_path = import_dir / "already_here.tmx"
    same_path.write_text("tmx", encoding="utf-8")
    copied_same = win._copy_tmx_to_import_dir(same_path)
    assert copied_same == same_path.resolve()


def test_locale_resolution_helpers_handle_outside_and_root_relative_paths(
    qtbot,
    tmp_path,
) -> None:
    """Verify locale helper returns None for outside/root and locale for file paths."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    assert win._locale_for_path(root) is None
    assert win._locale_for_path(tmp_path / "outside.txt") is None
    assert win._locale_for_string_path(str(root / "BE" / "ui.txt")) == "BE"
