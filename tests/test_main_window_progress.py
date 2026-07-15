"""Tests for Project-tab progress strip behavior and progress semantics."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt

from translationzed_py.core.model import Status
from translationzed_py.gui import MainWindow
from translationzed_py.gui import main_window as mw
from translationzed_py.gui import main_window_panel_helpers as panel_helpers


def _make_project(root: Path) -> None:
    for locale in ("EN", "BE"):
        (root / locale).mkdir()
        (root / locale / "language.txt").write_text(
            f"text = {locale},\ncharset = UTF-8,\n",
            encoding="utf-8",
        )
    (root / "EN" / "a.txt").write_text('A1 = "One"\nA2 = "Two"\n', encoding="utf-8")
    (root / "EN" / "b.txt").write_text('B1 = "Three"\nB2 = "Four"\n', encoding="utf-8")
    (root / "BE" / "a.txt").write_text('A1 = "Adzin"\nA2 = "Dva"\n', encoding="utf-8")
    (root / "BE" / "b.txt").write_text('B1 = "Try"\nB2 = "Chatyry"\n', encoding="utf-8")


def test_progress_strip_updates_for_file_and_locale(qtbot, tmp_path: Path) -> None:
    """Verify progress strip reflects file + locale status distribution."""
    root = tmp_path / "proj"
    root.mkdir()
    _make_project(root)

    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    win._post_locale_timer.stop()

    ix_a = win.fs_model.index_for_path(root / "BE" / "a.txt")
    win._file_chosen(ix_a)
    model_a = win.table.model()
    assert model_a is not None
    assert model_a.setData(model_a.index(0, 3), Status.TRANSLATED, Qt.EditRole)
    assert model_a.setData(model_a.index(1, 3), Status.PROOFREAD, Qt.EditRole)
    assert win._write_cache_current() is True

    ix_b = win.fs_model.index_for_path(root / "BE" / "b.txt")
    win._file_chosen(ix_b)
    assert win._current_pf is not None
    assert win._current_pf.path == root / "BE" / "b.txt"
    current_model = win.table.model()
    assert current_model is not None
    assert current_model.canonical_status_counts() == (2, 0, 0, 0)
    win._refresh_progress_ui()
    qtbot.waitUntil(
        lambda: "BE" in getattr(win, "_progress_locale_progress_cache", {}),
        timeout=3000,
    )

    assert win._progress_file_row.percent_label.text() == "T:0% P:0%"
    assert win._progress_locale_row.percent_label.text() == "T:25% P:25%"


def test_cache_failure_keeps_edit_in_memory_and_blocks_file_switch(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    """A failed draft write must not silently discard the current in-memory edit."""
    root = tmp_path / "proj"
    root.mkdir()
    _make_project(root)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    win._post_locale_timer.stop()
    first = root / "BE" / "a.txt"
    win._file_chosen(win.fs_model.index_for_path(first))
    model = win.table.model()
    assert model is not None
    errors: list[str] = []

    def _fail_write(*_args, **_kwargs) -> None:  # type: ignore[no-untyped-def]
        raise OSError("disk full")

    with monkeypatch.context() as patch:
        patch.setattr(mw, "_write_status_cache", _fail_write)
        patch.setattr(
            mw,
            "_show_critical_box",
            lambda _parent, _title, text: errors.append(text),
        )
        assert model.setData(model.index(0, 2), "kept in memory", Qt.EditRole)
        win._file_chosen(win.fs_model.index_for_path(root / "BE" / "b.txt"))

    assert model.data(model.index(0, 2), Qt.EditRole) == "kept in memory"
    assert win._current_pf is not None and win._current_pf.path == first
    assert errors and "remains in this window" in errors[-1]
    assert win._write_cache_current() is True


def test_locale_progress_reuses_session_cache_and_updates_incrementally(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    """Verify no locale recompute on file switch/edit after first aggregation."""
    root = tmp_path / "proj"
    root.mkdir()
    _make_project(root)

    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    win._post_locale_timer.stop()

    ix_a = win.fs_model.index_for_path(root / "BE" / "a.txt")
    win._file_chosen(ix_a)
    win._refresh_progress_ui()
    qtbot.waitUntil(
        lambda: "BE" in getattr(win, "_progress_locale_progress_cache", {}),
        timeout=3000,
    )
    qtbot.waitUntil(
        lambda: getattr(win, "_progress_locale_future", None) is None,
        timeout=3000,
    )

    scheduled: list[str] = []

    def _track_schedule(*_args, **_kwargs):
        locale = _kwargs.get("locale")
        if locale is None and len(_args) >= 2:
            locale = _args[1]
        scheduled.append(str(locale))
        return None

    monkeypatch.setattr(
        panel_helpers, "_schedule_locale_progress_refresh", _track_schedule
    )

    ix_b = win.fs_model.index_for_path(root / "BE" / "b.txt")
    win._file_chosen(ix_b)
    assert scheduled == []

    model_b = win.table.model()
    assert model_b is not None
    assert model_b.setData(model_b.index(0, 3), Status.TRANSLATED, Qt.EditRole)
    assert model_b.setData(model_b.index(1, 3), Status.PROOFREAD, Qt.EditRole)
    assert scheduled == []
    assert win._progress_locale_row.percent_label.text() == "T:25% P:25%"


def test_progress_uses_canonical_counts_under_filter_and_sort(
    qtbot, tmp_path: Path
) -> None:
    """Verify progress ignores view filter/sort and uses canonical status counts."""
    root = tmp_path / "proj"
    root.mkdir()
    _make_project(root)

    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    win._post_locale_timer.stop()

    ix_a = win.fs_model.index_for_path(root / "BE" / "a.txt")
    win._file_chosen(ix_a)
    model = win.table.model()
    assert model is not None

    assert model.setData(model.index(0, 3), Status.TRANSLATED, Qt.EditRole)
    assert model.setData(model.index(1, 3), Status.PROOFREAD, Qt.EditRole)
    model.set_status_filter({Status.UNTOUCHED})
    model.set_status_sort_enabled(True)
    win._refresh_progress_ui()

    assert win._progress_file_row.percent_label.text() == "T:50% P:50%"


def test_status_bar_and_empty_state_defaults(qtbot, tmp_path: Path) -> None:
    """Verify no-file-open placeholder and default status text contract."""
    root = tmp_path / "proj"
    root.mkdir()
    _make_project(root)

    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    win._post_locale_timer.stop()

    assert win._right_stack.currentWidget() is win._empty_table_placeholder
    assert win.statusBar().currentMessage() == "Ready to edit"

    ix_a = win.fs_model.index_for_path(root / "BE" / "a.txt")
    win._file_chosen(ix_a)
    assert win._right_stack.currentWidget() is win._table_container


def test_shutdown_progress_workers_joins_active_pool() -> None:
    """Verify progress-worker shutdown joins the background pool deterministically."""

    class _Timer:
        def __init__(self) -> None:
            self.stopped = False

        def isActive(self) -> bool:  # noqa: N802
            return True

        def stop(self) -> None:
            self.stopped = True

    class _Future:
        def __init__(self) -> None:
            self.cancelled = False

        def cancel(self) -> None:
            self.cancelled = True

    class _Pool:
        def __init__(self) -> None:
            self.calls: list[tuple[bool, bool]] = []

        def shutdown(self, *, wait: bool, cancel_futures: bool) -> None:
            self.calls.append((wait, cancel_futures))

    class _Window:
        pass

    win = _Window()
    win._progress_locale_timer = _Timer()
    win._progress_locale_future = _Future()
    win._progress_locale_pending = "BE"
    win._progress_locale_pending_current_path = Path("BE/a.txt")
    win._progress_locale_pending_current_counts = (1, 0, 0, 0)
    pool = _Pool()
    win._progress_locale_pool = pool

    panel_helpers._shutdown_progress_workers(win)

    assert win._progress_locale_timer.stopped is True
    assert win._progress_locale_future is None
    assert win._progress_locale_pending is None
    assert win._progress_locale_pending_current_path is None
    assert win._progress_locale_pending_current_counts is None
    assert win._progress_locale_pool is None
    assert pool.calls == [(True, True)]
