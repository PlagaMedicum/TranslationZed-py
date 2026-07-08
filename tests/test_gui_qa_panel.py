"""Test module for gui qa panel."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSizePolicy

from translationzed_py.core.model import Status
from translationzed_py.core.qa_service import (
    QA_RULE_ORDER,
    QAFinding,
    QARuleState,
    QAService,
)
from translationzed_py.gui import MainWindow


def _make_basic_qa_project(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "proj"
    root.mkdir()
    for loc in ("EN", "BE"):
        (root / loc).mkdir()
        (root / loc / "language.txt").write_text(
            f"text = {loc},\ncharset = UTF-8,\n",
            encoding="utf-8",
        )
    target_path = root / "BE" / "qa.txt"
    (root / "EN" / "qa.txt").write_text('L1 = "Hello."\n', encoding="utf-8")
    target_path.write_text('L1 = "Privet"\n', encoding="utf-8")
    return root, target_path


def _build_snapshot(
    *,
    run_id: str,
    file_path: Path,
    summary: str,
    state_by_rule: dict[str, QARuleState] | None = None,
    note_by_rule: dict[str, str] | None = None,
):
    service = QAService()
    records = service.build_progress_records(run_id=run_id)
    target_states = state_by_rule or {}
    notes = note_by_rule or {}
    timestamp = 100
    for rule_id in QA_RULE_ORDER:
        target_state = target_states.get(rule_id, QARuleState.QUEUED)
        if target_state == QARuleState.QUEUED:
            continue
        records = service.transition_rule_state(
            records=records,
            run_id=run_id,
            rule_id=rule_id,
            new_state=QARuleState.RUNNING,
            timestamp_ms=timestamp,
        )
        timestamp += 1
        if target_state == QARuleState.RUNNING:
            continue
        records = service.transition_rule_state(
            records=records,
            run_id=run_id,
            rule_id=rule_id,
            new_state=target_state,
            timestamp_ms=timestamp,
            note=notes.get(rule_id, ""),
        )
        timestamp += 1
    return service.build_progress_snapshot(
        run_id=run_id,
        file_path=file_path,
        ordered_rules=records,
        final_summary=summary,
    )


def test_qa_side_panel_lists_findings_and_navigates(qtbot, tmp_path: Path) -> None:
    """Verify qa side panel lists findings and navigates."""
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
    assert "#1 trailing" in item.text()
    assert "second.txt" in item.text()
    assert "Missing trailing" in item.text()

    win._open_qa_result_item(item)
    qtbot.waitUntil(
        lambda: win._current_pf and win._current_pf.path == root / "BE" / "second.txt",
        timeout=1000,
    )


def test_qa_side_panel_refreshes_trailing_and_newline_findings(
    qtbot, tmp_path: Path
) -> None:
    """Verify qa side panel refreshes trailing and newline findings."""
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
    win._qa_auto_refresh = False
    win._qa_check_trailing = True
    win._qa_check_newlines = True
    ix = win.fs_model.index_for_path(root / "BE" / "qa.txt")
    win._file_chosen(ix)
    win._left_qa_btn.click()
    assert win._qa_results_list.count() == 0
    assert win._qa_results_list.isVisible() is False
    assert "QA is manual." in win._qa_results_placeholder.text()
    win._qa_refresh_btn.click()

    def _labels() -> list[str]:
        return [
            win._qa_results_list.item(i).text()
            for i in range(win._qa_results_list.count())
        ]

    qtbot.waitUntil(
        lambda: any("trailing" in label for label in _labels())
        and any("newlines" in label for label in _labels()),
        timeout=3000,
    )
    labels = _labels()
    assert any("trailing" in label for label in labels)
    assert any("newlines" in label for label in labels)


def test_qa_placeholder_is_plain_text_not_fake_result_item(
    qtbot, tmp_path: Path
) -> None:
    """QA placeholder must render as plain text while list remains empty."""
    root, target_path = _make_basic_qa_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    win._left_qa_btn.click()
    win._file_chosen(win.fs_model.index_for_path(target_path))

    win._set_qa_panel_message("QA is manual. Click Run QA for this file.")

    assert win._qa_results_list.count() == 0
    assert win._qa_results_list.isVisible() is False
    assert "QA is manual." in win._qa_results_placeholder.text()


def test_edit_marks_only_row_qa_findings_stale(qtbot, tmp_path: Path) -> None:
    """Editing one row should not clear unrelated manual QA findings."""
    root = tmp_path / "proj"
    root.mkdir()
    for loc in ("EN", "BE"):
        (root / loc).mkdir()
        (root / loc / "language.txt").write_text(
            f"text = {loc},\ncharset = UTF-8,\n",
            encoding="utf-8",
        )
    target_path = root / "BE" / "qa.txt"
    (root / "EN" / "qa.txt").write_text(
        'L1 = "Hello."\nL2 = "Bye."\n',
        encoding="utf-8",
    )
    target_path.write_text(
        'L1 = "Privet"\nL2 = "Paka"\n',
        encoding="utf-8",
    )
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    win._qa_auto_refresh = False
    win._left_qa_btn.click()
    win._file_chosen(win.fs_model.index_for_path(target_path))
    snapshot = _build_snapshot(
        run_id="run-1",
        file_path=target_path,
        summary="QA completed: 2 finding(s) across 5/5 rules.",
        state_by_rule=dict.fromkeys(QA_RULE_ORDER, QARuleState.DONE),
    )
    win._set_qa_progress_snapshots((snapshot,))
    win._set_qa_findings(
        [
            QAFinding(
                file=target_path,
                row=0,
                code="qa.trailing",
                excerpt="Row one stale",
            ),
            QAFinding(
                file=target_path,
                row=1,
                code="qa.newlines",
                excerpt="Row two still active",
            ),
        ]
    )
    assert win._qa_results_list.count() == 2

    win.table.setCurrentIndex(win._current_model.index(0, 2))
    win._current_model.setData(win._current_model.index(0, 2), "Edited", Qt.EditRole)

    assert [finding.row for finding in win._qa_findings] == [1]
    assert win._qa_results_list.count() == 1
    assert "Row two still active" in win._qa_results_list.item(0).text()
    assert win._qa_results_list.isHidden() is False
    assert win._qa_scan_note == ""
    assert (
        win._qa_checklist_label.text()
        == "QA completed: 2 finding(s) across 5/5 rules."
    )
    assert win._qa_stale_notice_label.isHidden() is False
    assert (
        win._qa_stale_notice_label.text()
        == (
            "1 edited row needs QA again. "
            "Old findings are hidden until you rerun QA."
        )
    )

    win._set_qa_findings(
        [
            QAFinding(
                file=target_path,
                row=1,
                code="qa.newlines",
                excerpt="Fresh row two",
            )
        ]
    )

    assert win._qa_stale_hidden_rows == set()
    assert win._qa_stale_notice_label.isHidden() is True


def test_qa_panel_labels_use_compact_top_aligned_layout(qtbot, tmp_path: Path) -> None:
    """QA checklist/placeholder labels should stay compact and top-aligned."""
    root, target_path = _make_basic_qa_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    win._left_qa_btn.click()
    win._file_chosen(win.fs_model.index_for_path(target_path))
    win._set_qa_panel_message("QA is manual. Click Run QA for this file.")

    checklist_policy = win._qa_checklist_label.sizePolicy()
    stale_notice_policy = win._qa_stale_notice_label.sizePolicy()
    placeholder_policy = win._qa_results_placeholder.sizePolicy()
    assert checklist_policy.verticalPolicy() == QSizePolicy.Policy.Minimum
    assert stale_notice_policy.verticalPolicy() == QSizePolicy.Policy.Preferred
    assert placeholder_policy.verticalPolicy() == QSizePolicy.Policy.Minimum
    assert win._qa_checklist_label.alignment() == (
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
    )
    assert win._qa_stale_notice_label.alignment() == (
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
    )
    assert win._qa_results_placeholder.alignment() == (
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
    )
    checklist_height = win._qa_checklist_label.height()
    placeholder_height = win._qa_results_placeholder.height()
    line_height = win._qa_checklist_label.fontMetrics().lineSpacing()
    assert checklist_height <= (line_height * 2) + 4
    assert placeholder_height <= (line_height * 2) + 4
    gap = win._qa_results_placeholder.y() - (
        win._qa_checklist_label.y() + win._qa_checklist_label.height()
    )
    assert gap <= 12


def test_qa_auto_mark_for_review_toggle_controls_status_mutation(
    qtbot, tmp_path: Path
) -> None:
    """Verify qa auto mark for review toggle controls status mutation."""
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
    win._qa_auto_refresh = False
    win._qa_auto_mark_for_review = False
    win._qa_auto_mark_translated_for_review = False
    win._qa_auto_mark_proofread_for_review = False
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

    # Default auto-mark updates Untouched rows only.
    model.setData(status_index, Status.TRANSLATED, Qt.EditRole)
    win._refresh_qa_for_current_file()
    assert model.data(status_index, Qt.EditRole) == Status.TRANSLATED

    # Optional translated setting allows auto-marking translated statuses.
    win._qa_auto_mark_translated_for_review = True
    win._refresh_qa_for_current_file()
    assert model.data(status_index, Qt.EditRole) == Status.FOR_REVIEW

    # Proofread rows are controlled independently.
    model.setData(status_index, Status.PROOFREAD, Qt.EditRole)
    win._qa_auto_mark_translated_for_review = False
    win._qa_auto_mark_proofread_for_review = False
    win._refresh_qa_for_current_file()
    assert model.data(status_index, Qt.EditRole) == Status.PROOFREAD

    win._qa_auto_mark_proofread_for_review = True
    win._refresh_qa_for_current_file()
    assert model.data(status_index, Qt.EditRole) == Status.FOR_REVIEW


def test_qa_token_check_toggle_controls_placeholder_tag_findings(
    qtbot, tmp_path: Path
) -> None:
    """Verify qa token check toggle controls placeholder tag findings."""
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
    """Verify qa same as source toggle adds content group finding."""
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
    labels = [
        win._qa_results_list.item(i).text() for i in range(win._qa_results_list.count())
    ]
    assert any("same-src W/C" in label for label in labels)


def test_qa_next_prev_navigation_moves_between_findings(qtbot, tmp_path: Path) -> None:
    """Verify qa next prev navigation moves between findings."""
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


def test_qa_refresh_does_not_mutate_file_bytes_without_save(
    qtbot, tmp_path: Path
) -> None:
    """Verify qa refresh does not mutate file bytes without save."""
    root = tmp_path / "proj"
    root.mkdir()
    for loc in ("EN", "BE"):
        (root / loc).mkdir()
        (root / loc / "language.txt").write_text(
            f"text = {loc},\ncharset = UTF-8,\n",
            encoding="utf-8",
        )
    (root / "EN" / "qa.txt").write_text('L1 = "Hello."\n', encoding="utf-8")
    be_path = root / "BE" / "qa.txt"
    be_path.write_text('L1 = "Hello."\n', encoding="utf-8")
    before = be_path.read_bytes()

    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    win._qa_check_trailing = True
    win._qa_check_newlines = True
    win._qa_check_escapes = True
    win._qa_check_same_as_source = True
    win._qa_auto_mark_for_review = True
    ix = win.fs_model.index_for_path(be_path)
    win._file_chosen(ix)
    win._refresh_qa_for_current_file()

    assert be_path.read_bytes() == before


def test_qa_checklist_renders_fixed_order_state_text_and_notes(
    qtbot, tmp_path: Path
) -> None:
    """Verify checklist text renders in fixed order with state/note mapping."""
    root, target_path = _make_basic_qa_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    win._left_qa_btn.click()
    win._file_chosen(win.fs_model.index_for_path(target_path))

    snapshot = _build_snapshot(
        run_id="run-1",
        file_path=target_path,
        summary="Running QA checks...",
        state_by_rule={
            "trailing": QARuleState.DONE,
            "newlines": QARuleState.RUNNING,
            "tokens": QARuleState.SKIPPED,
            "same_source": QARuleState.FAILED,
            "languagetool": QARuleState.QUEUED,
        },
        note_by_rule={
            "tokens": "Rule disabled in settings.",
            "same_source": "Rule exception.",
        },
    )
    win._qa_scan_busy = True
    win._set_qa_progress_snapshots((snapshot,))

    lines = win._qa_checklist_label.text().splitlines()
    assert lines[0] == "Missing trailing characters: Completed"
    assert lines[1] == "Missing/extra newlines: Running…"
    assert (
        lines[2]
        == "Protected tokens / placeholders: Skipped (Rule disabled in settings.)"
    )
    assert lines[3] == "Translation equals source: Failed (Rule exception.)"
    assert lines[4] == "LanguageTool: Queued"
    assert lines[-1] == "Running QA checks..."


def test_qa_checklist_resets_to_queued_on_new_run_snapshot(
    qtbot, tmp_path: Path
) -> None:
    """Verify a new QA run snapshot resets checklist rows to queued states."""
    root, target_path = _make_basic_qa_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    win._left_qa_btn.click()
    win._file_chosen(win.fs_model.index_for_path(target_path))

    first_snapshot = _build_snapshot(
        run_id="run-1",
        file_path=target_path,
        summary="QA completed: 1 finding(s) across 5/5 rules.",
        state_by_rule=dict.fromkeys(QA_RULE_ORDER, QARuleState.DONE),
    )
    win._set_qa_progress_snapshots((first_snapshot,))
    assert (
        win._qa_checklist_label.text() == "QA completed: 1 finding(s) across 5/5 rules."
    )

    second_snapshot = _build_snapshot(
        run_id="run-2",
        file_path=target_path,
        summary="Running QA checks...",
    )
    win._qa_scan_busy = True
    win._set_qa_progress_snapshots((second_snapshot,))

    checklist_text = win._qa_checklist_label.text()
    assert win._qa_progress_snapshot is not None
    assert win._qa_progress_snapshot.run_id == "run-2"
    assert "Missing trailing characters: Queued" in checklist_text
    assert "Running QA checks..." in checklist_text
    assert "Completed" not in "\n".join(checklist_text.splitlines()[:5])
