"""Test module for gui smoke."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from translationzed_py.gui import MainWindow


def test_table_fills(qtbot, tmp_path: Path):
    # copy fixture
    """Verify table fills."""
    dst = tmp_path / "proj"
    dst.mkdir()
    for loc in ("EN", "BE"):
        (dst / loc).mkdir()
        (dst / loc / "language.txt").write_text(
            f"text = {loc},\ncharset = UTF-8,\n", encoding="utf-8"
        )
        (dst / loc / "ui.txt").write_text('UI_YES = "Yes"\n')
    win = MainWindow(str(dst), selected_locales=["BE"])
    qtbot.addWidget(win)
    # select BE/ui.txt
    ix = win.fs_model.index_for_path(dst / "BE" / "ui.txt")
    win._file_chosen(ix)
    assert win.table.model().rowCount() == 1


def test_detail_editor_shows_live_char_counts(qtbot, tmp_path: Path):
    """Verify detail editor shows live char counts."""
    dst = tmp_path / "proj"
    dst.mkdir()
    for loc in ("EN", "BE"):
        (dst / loc).mkdir()
        (dst / loc / "language.txt").write_text(
            f"text = {loc},\ncharset = UTF-8,\n", encoding="utf-8"
        )
    (dst / "EN" / "ui.txt").write_text('UI_YES = "Hello"\n', encoding="utf-8")
    (dst / "BE" / "ui.txt").write_text('UI_YES = "Hi"\n', encoding="utf-8")

    win = MainWindow(str(dst), selected_locales=["BE"])
    qtbot.addWidget(win)
    win.show()
    ix = win.fs_model.index_for_path(dst / "BE" / "ui.txt")
    win._file_chosen(ix)
    if not win.detail_toggle.isChecked():
        win._toggle_detail_panel(True)
    model = win.table.model()
    assert model is not None
    win.table.setCurrentIndex(model.index(0, 2))
    win._sync_detail_editors()

    qtbot.waitUntil(
        lambda: "S: 5" in win._detail_counter_label.text(),
        timeout=1000,
    )
    assert "S = source" in win._detail_counter_label.toolTip()
    assert "T: 2" in win._detail_counter_label.text()
    assert "Delta: -3" in win._detail_counter_label.text()

    win._detail_translation.setPlainText("Hello there")
    qtbot.waitUntil(
        lambda: "T: 11" in win._detail_counter_label.text(),
        timeout=1000,
    )
    assert "Delta: +6" in win._detail_counter_label.text()
