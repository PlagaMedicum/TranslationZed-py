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


def _make_perf_project(tmp_path: Path, *, files: tuple[str, ...]) -> Path:
    root = tmp_path / "proj"
    for locale in ("EN", "BE"):
        (root / locale).mkdir(parents=True, exist_ok=True)
        (root / locale / "language.txt").write_text(
            f"text = {locale},\ncharset = UTF-8,\n",
            encoding="utf-8",
        )
    src = Path(__file__).parent / "fixtures" / "perf_root" / "BE"
    for name in files:
        shutil.copy2(src / name, root / "BE" / name)
        shutil.copy2(src / name, root / "EN" / name)
    return root


def _open_file(win: MainWindow, path: Path) -> None:
    index = win.fs_model.index_for_path(path)
    win._file_chosen(index)


def test_row_resize_is_budget_sliced_for_large_file(
    qtbot, tmp_path: Path, monkeypatch, perf_recorder
) -> None:
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
    qtbot.waitUntil(lambda: not win._row_resize_timer.isActive(), timeout=4000)

    budget_ms = _budget_ms("TZP_PERF_GUI_SCROLL_SELECT_MS", 2500.0)
    perf_recorder(
        "gui large-file scroll+selection",
        elapsed_ms,
        budget_ms,
        f"file={filename} rows={rows}",
    )
    assert elapsed_ms <= budget_ms
