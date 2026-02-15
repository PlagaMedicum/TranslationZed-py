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
    win._qa_check_trailing = True
    win._qa_check_newlines = True
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
    win._qa_check_trailing = True
    win._qa_check_newlines = True
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


def test_qa_token_check_toggle_controls_placeholder_tag_findings(
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
        'L1 = "<LINE> [img=music] %1 <gasps from the courtroom>"\n',
        encoding="utf-8",
    )
    (root / "BE" / "qa.txt").write_text(
        'L1 = "<gasps from the courtroom>"\n',
        encoding="utf-8",
    )

    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    ix = win.fs_model.index_for_path(root / "BE" / "qa.txt")
    win._file_chosen(ix)
    win._qa_check_trailing = False
    win._qa_check_newlines = False

    win._qa_check_escapes = False
    win._refresh_qa_for_current_file()
    assert not any(f.code == "qa.tokens" for f in win._qa_findings)

    win._qa_check_escapes = True
    win._refresh_qa_for_current_file()
    assert any(f.code == "qa.tokens" for f in win._qa_findings)


def test_qa_same_as_source_toggle_adds_content_group_finding(
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
    (root / "EN" / "qa.txt").write_text('L1 = "The Same"\n', encoding="utf-8")
    (root / "BE" / "qa.txt").write_text('L1 = "The Same"\n', encoding="utf-8")

    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    ix = win.fs_model.index_for_path(root / "BE" / "qa.txt")
    win._file_chosen(ix)
    win._qa_check_trailing = False
    win._qa_check_newlines = False
    win._qa_check_escapes = False
    win._qa_check_same_as_source = True
    win._refresh_qa_for_current_file()
    win._left_qa_btn.click()

    assert any(f.code == "qa.same_source" for f in win._qa_findings)
    labels = [win._qa_results_list.item(i).text() for i in range(win._qa_results_list.count())]
    assert any("warning/content · qa.same_source" in label for label in labels)


def test_qa_next_prev_navigation_moves_between_findings(qtbot, tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    for loc in ("EN", "BE"):
        (root / loc).mkdir()
        (root / loc / "language.txt").write_text(
            f"text = {loc},\ncharset = UTF-8,\n",
            encoding="utf-8",
        )
    (root / "EN" / "qa.txt").write_text(
        'L1 = "Hello."\nL2 = "World!"\n',
        encoding="utf-8",
    )
    (root / "BE" / "qa.txt").write_text(
        'L1 = "Privet"\nL2 = "Svet"\n',
        encoding="utf-8",
    )

    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    ix = win.fs_model.index_for_path(root / "BE" / "qa.txt")
    win._file_chosen(ix)
    model = win.table.model()
    assert model is not None
    win._qa_check_trailing = True
    win._qa_check_newlines = False
    win._qa_check_escapes = False
    win._qa_check_same_as_source = False
    win._refresh_qa_for_current_file()
    assert len(win._qa_findings) >= 2

    win.table.setCurrentIndex(model.index(0, 2))
    win._qa_next_finding()
    assert win.table.currentIndex().row() == 1

    win._qa_prev_finding()
    assert win.table.currentIndex().row() == 0
    assert "QA " in win.statusBar().currentMessage()
