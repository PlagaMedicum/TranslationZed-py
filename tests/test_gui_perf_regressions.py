"""Test module for gui perf regressions."""

import os
import shutil
import time
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QAbstractItemView

from translationzed_py.gui import MainWindow


def _budget_ms(env_name: str, default_ms: float) -> float:
    raw = os.getenv(env_name, "")
    if not raw:
        return default_ms
    try:
        return float(raw)
    except ValueError:
        return default_ms


def _make_perf_project(
    tmp_path: Path,
    *,
    files: tuple[str, ...],
    locales: tuple[str, ...] = ("EN", "BE"),
) -> Path:
    root = tmp_path / "proj"
    for locale in locales:
        (root / locale).mkdir(parents=True, exist_ok=True)
        (root / locale / "language.txt").write_text(
            f"text = {locale},\ncharset = UTF-8,\n",
            encoding="utf-8",
        )
    src = Path(__file__).parent / "fixtures" / "perf_root" / "BE"
    for name in files:
        for locale in locales:
            shutil.copy2(src / name, root / locale / name)
    return root


def _open_file(win: MainWindow, path: Path) -> None:
    index = win.fs_model.index_for_path(path)
    win._file_chosen(index)


def test_row_resize_is_budget_sliced_for_large_file(
    qtbot, tmp_path: Path, monkeypatch, perf_recorder
) -> None:
    """Verify row resize is budget sliced for large file."""
    monkeypatch.chdir(tmp_path)
    root = _make_perf_project(tmp_path, files=("SurvivalGuide_BE.txt",))
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    win.show()

    _open_file(win, root / "BE" / "SurvivalGuide_BE.txt")
    model = win.table.model()
    assert model is not None
    assert model.rowCount() > 500

    win._wrap_text_user = True
    win._apply_wrap_mode()
    assert win._wrap_text is True

    win._row_resize_budget_ms = 0.0
    win._pending_row_span = (0, min(model.rowCount() - 1, 600))
    win._row_resize_cursor = None

    budget_ms = _budget_ms("TZP_PERF_GUI_ROW_RESIZE_BURST_MS", 800.0)
    start = time.perf_counter()
    win._resize_visible_rows()
    elapsed_ms = (time.perf_counter() - start) * 1000.0

    perf_recorder(
        "gui row-resize burst",
        elapsed_ms,
        budget_ms,
        f"rows={model.rowCount()} cursor={win._row_resize_cursor}",
    )
    assert elapsed_ms <= budget_ms
    assert win._row_resize_cursor is not None
    assert win._row_resize_timer.isActive()
    win._row_resize_timer.stop()


@pytest.mark.parametrize(
    "filename",
    ("SurvivalGuide_BE.txt", "Recorded_Media_BE.txt"),
)
def test_large_file_scroll_and_selection_stability(
    qtbot, tmp_path: Path, monkeypatch, perf_recorder, filename: str
) -> None:
    """Verify large file scroll and selection stability."""
    monkeypatch.chdir(tmp_path)
    root = _make_perf_project(tmp_path, files=(filename,))
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    win.show()

    _open_file(win, root / "BE" / filename)
    model = win.table.model()
    assert model is not None
    rows = model.rowCount()
    assert rows > 300

    win._wrap_text_user = True
    win._apply_wrap_mode()

    table = win.table
    scrollbar = table.verticalScrollBar()
    checkpoints = [0, rows // 4, rows // 2, rows - 1]
    start = time.perf_counter()
    for row in checkpoints:
        idx = model.index(row, 2)
        table.setCurrentIndex(idx)
        table.scrollTo(idx, QAbstractItemView.PositionAtCenter)
        if scrollbar.maximum() > 0:
            frac = row / max(1, rows - 1)
            scrollbar.setValue(int(scrollbar.maximum() * frac))
        qtbot.wait(20)
        assert table.currentIndex().row() == row
    elapsed_ms = (time.perf_counter() - start) * 1000.0

    qtbot.waitUntil(lambda: not win._scroll_idle_timer.isActive(), timeout=4000)
    # Row-resize timer can keep slicing long spans for a while on loaded CI
    # runners; this test measures scroll/selection latency, not full resize drain.
    qtbot.wait(120)
    if win._row_resize_timer.isActive():
        win._row_resize_timer.stop()

    budget_ms = _budget_ms("TZP_PERF_GUI_SCROLL_SELECT_MS", 2500.0)
    perf_recorder(
        "gui large-file scroll+selection",
        elapsed_ms,
        budget_ms,
        f"file={filename} rows={rows}",
    )
    assert elapsed_ms <= budget_ms


def test_header_resize_reflow_is_debounced(qtbot, tmp_path: Path, monkeypatch) -> None:
    """Verify header resize reflow is debounced."""
    monkeypatch.chdir(tmp_path)
    root = _make_perf_project(tmp_path, files=("SurvivalGuide_BE.txt",))
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    win.show()

    _open_file(win, root / "BE" / "SurvivalGuide_BE.txt")
    model = win.table.model()
    assert model is not None
    win._wrap_text_user = True
    win._apply_wrap_mode()
    win._row_resize_timer.stop()
    win._resize_reflow_timer.stop()
    win._resize_reflow_pending = False

    clear_calls = 0
    resize_calls = 0
    original_clear = win._clear_row_height_cache
    original_resize = win._schedule_row_resize

    def _spy_clear(rows=None):
        nonlocal clear_calls
        clear_calls += 1
        return original_clear(rows)

    def _spy_resize(*, full: bool = False):
        nonlocal resize_calls
        resize_calls += 1
        return original_resize(full=full)

    monkeypatch.setattr(win, "_clear_row_height_cache", _spy_clear)
    monkeypatch.setattr(win, "_schedule_row_resize", _spy_resize)

    header = win.table.horizontalHeader()
    base = header.sectionSize(1)
    for delta in (8, 16, 24, 32):
        win._on_header_resized(1, base, base + delta)

    assert clear_calls == 0
    assert resize_calls == 0
    assert win._resize_reflow_pending is True
    win._resize_reflow_timer.stop()
    win._flush_resize_reflow()
    assert clear_calls == 1
    assert resize_calls == 1
    win._flush_resize_reflow()
    assert clear_calls == 1
    assert resize_calls == 1


def test_splitter_resize_reflow_is_debounced(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    """Verify splitter resize reflow is debounced."""
    monkeypatch.chdir(tmp_path)
    root = _make_perf_project(tmp_path, files=("SurvivalGuide_BE.txt",))
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    win.show()

    _open_file(win, root / "BE" / "SurvivalGuide_BE.txt")
    model = win.table.model()
    assert model is not None
    win._wrap_text_user = True
    win._apply_wrap_mode()
    win._row_resize_timer.stop()
    win._resize_reflow_timer.stop()
    win._resize_reflow_pending = False

    clear_calls = 0
    resize_calls = 0
    original_clear = win._clear_row_height_cache
    original_resize = win._schedule_row_resize

    def _spy_clear(rows=None):
        nonlocal clear_calls
        clear_calls += 1
        return original_clear(rows)

    def _spy_resize(*, full: bool = False):
        nonlocal resize_calls
        resize_calls += 1
        return original_resize(full=full)

    monkeypatch.setattr(win, "_clear_row_height_cache", _spy_clear)
    monkeypatch.setattr(win, "_schedule_row_resize", _spy_resize)

    for _ in range(5):
        win._on_content_splitter_moved(0, 0)

    assert clear_calls == 0
    assert resize_calls == 0
    assert win._resize_reflow_pending is True
    win._resize_reflow_timer.stop()
    win._flush_resize_reflow()
    assert clear_calls == 1
    assert resize_calls == 1


def test_source_reference_switch_is_budgeted(
    qtbot, tmp_path, monkeypatch, perf_recorder
):
    """Verify source reference switch is budgeted."""
    monkeypatch.chdir(tmp_path)
    root = _make_perf_project(
        tmp_path,
        files=("SurvivalGuide_BE.txt",),
        locales=("EN", "BE", "RU"),
    )
    win = MainWindow(str(root), selected_locales=["BE", "RU"])
    qtbot.addWidget(win)
    win.show()

    _open_file(win, root / "BE" / "SurvivalGuide_BE.txt")
    model = win.table.model()
    assert model is not None
    rows = model.rowCount()
    assert rows > 500

    ru_idx = win.source_ref_combo.findData("RU")
    en_idx = win.source_ref_combo.findData("EN")
    assert ru_idx >= 0
    assert en_idx >= 0

    budget_ms = _budget_ms("TZP_PERF_GUI_SOURCE_REF_SWITCH_MS", 1500.0)
    start = time.perf_counter()
    win.source_ref_combo.setCurrentIndex(ru_idx)
    qtbot.wait(20)
    win.source_ref_combo.setCurrentIndex(en_idx)
    qtbot.wait(20)
    elapsed_ms = (time.perf_counter() - start) * 1000.0

    perf_recorder(
        "gui source-reference switch",
        elapsed_ms,
        budget_ms,
        f"rows={rows}",
    )
    assert elapsed_ms <= budget_ms
