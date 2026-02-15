from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt

from translationzed_py.core.model import Status
from translationzed_py.core.qa_service import QAFinding
from translationzed_py.gui import MainWindow


def test_qa_side_panel_lists_findings_and_navigates(qtbot, tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    for loc in ("EN", "BE"):
        (root / loc).mkdir()
        (root / loc / "language.txt").write_text(
            f"text = {loc},\ncharset = UTF-8,\n",
            encoding="utf-8",
        )
    (root / "EN" / "first.txt").write_text('UI_FIRST = "One"\n', encoding="utf-8")
    (root / "EN" / "second.txt").write_text('UI_SECOND = "Two."\n', encoding="utf-8")
    (root / "BE" / "first.txt").write_text('UI_FIRST = "Adzin"\n', encoding="utf-8")
    (root / "BE" / "second.txt").write_text('UI_SECOND = "Dva"\n', encoding="utf-8")

    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    ix_first = win.fs_model.index_for_path(root / "BE" / "first.txt")
    win._file_chosen(ix_first)
    win._left_qa_btn.click()

    finding = QAFinding(
        file=root / "BE" / "second.txt",
        row=0,
        code="qa.trailing",
        excerpt="Missing trailing '.'",
    )
    win._set_qa_findings([finding])
    win._refresh_qa_panel_results()

    qtbot.waitUntil(lambda: win._qa_results_list.count() == 1, timeout=1000)
    item = win._qa_results_list.item(0)
    assert item is not None
    assert "second.txt:1" in item.text()
    assert "qa.trailing" in item.text()
    assert "Missing trailing" in item.text()

    win._open_qa_result_item(item)
    qtbot.waitUntil(
        lambda: win._current_pf and win._current_pf.path == root / "BE" / "second.txt",
        timeout=1000,
    )


def test_qa_side_panel_refreshes_trailing_and_newline_findings(
    qtbot, tmp_path: Path
) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    for loc in ("EN", "BE"):
        (root / loc).mkdir()
        (root / loc / "language.txt").write_text(
            f"text = {loc},\ncharset = UTF-8,\n",
            encoding="utf-8",
        )
    (root / "EN" / "qa.txt").write_text(
        'L1 = "Hello."\nL2 = "Line one\\nLine two"\n',
        encoding="utf-8",
    )
    (root / "BE" / "qa.txt").write_text(
        'L1 = "Privet"\nL2 = "Radok adzin"\n',
        encoding="utf-8",
    )

    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    win._qa_auto_mark_for_review = False
    ix = win.fs_model.index_for_path(root / "BE" / "qa.txt")
    win._file_chosen(ix)
    win._left_qa_btn.click()

    qtbot.waitUntil(lambda: win._qa_results_list.count() >= 2, timeout=1000)
    labels = [win._qa_results_list.item(i).text() for i in range(win._qa_results_list.count())]
    assert any("qa.trailing" in label for label in labels)
    assert any("qa.newlines" in label for label in labels)


def test_qa_auto_mark_for_review_toggle_controls_status_mutation(
    qtbot, tmp_path: Path
) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    for loc in ("EN", "BE"):
        (root / loc).mkdir()
        (root / loc / "language.txt").write_text(
            f"text = {loc},\ncharset = UTF-8,\n",
            encoding="utf-8",
        )
    (root / "EN" / "qa.txt").write_text('L1 = "Hello."\n', encoding="utf-8")
    (root / "BE" / "qa.txt").write_text('L1 = "Privet"\n', encoding="utf-8")

    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    ix = win.fs_model.index_for_path(root / "BE" / "qa.txt")
    win._file_chosen(ix)
    model = win.table.model()
    assert model is not None
    status_index = model.index(0, 3)
    assert model.data(status_index, Qt.EditRole) == Status.UNTOUCHED

    win._refresh_qa_for_current_file()
    assert model.data(status_index, Qt.EditRole) == Status.UNTOUCHED

    win._qa_auto_mark_for_review = True
    win._refresh_qa_for_current_file()
    assert model.data(status_index, Qt.EditRole) == Status.FOR_REVIEW
