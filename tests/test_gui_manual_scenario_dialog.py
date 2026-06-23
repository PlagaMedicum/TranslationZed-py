"""GUI tests for manual scenario checklist dialog flow."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QLabel, QScrollArea

from translationzed_py.gui.manual_scenario_dialog import ManualScenarioChecklistDialog
from translationzed_py.gui.manual_scenario_runtime import (
    SCENARIO_ENV_RUN_TOKEN,
    ManualScenario,
    ManualScenarioRuntime,
)


def _runtime(tmp_path: Path) -> ManualScenarioRuntime:
    scenario = ManualScenario(
        id="demo",
        title="Demo scenario",
        workflow_family="open_save",
        manual_depth="full_workflow",
        goal="Verify save and switch workflow.",
        start_context="Launch with RU selected and use file switching.",
        fixture_root="manual_workflow",
        focus_files=("RU/ui.txt", "RU/menu.txt"),
        finish_condition="Leave RU/ui.txt active with saved value visible.",
        selected_locales=("RU",),
        steps=("Open file", "Run action"),
        expected_checks=("No crash", "Output updated"),
        tracked_repo_files=("translationzed_py/gui/main_window.py",),
        env_overrides={},
        prefs_extras={},
        automation_pytest_selectors=("tests/test_gui_smoke.py",),
        operator_hints=("Use save before opening another file.",),
        inspection_paths=("RU/ui.txt",),
    )
    return ManualScenarioRuntime(
        version=1,
        scenario=scenario,
        project_root=str((tmp_path / "project").resolve()),
    )


def test_manual_scenario_dialog_writes_pass_artifact(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    """Pass action should write artifact and close dialog."""
    monkeypatch.setenv(SCENARIO_ENV_RUN_TOKEN, "demo-run-token")
    dialog = ManualScenarioChecklistDialog(
        _runtime(tmp_path),
        results_dir=tmp_path / "results",
    )
    qtbot.addWidget(dialog)
    assert dialog._pass_btn.isEnabled() is False
    for idx in range(dialog._steps_list.count()):
        item = dialog._steps_list.item(idx)
        assert item is not None
        item.setCheckState(Qt.Checked)
    assert dialog._pass_btn.isEnabled() is False
    for idx in range(dialog._expected_list.count()):
        item = dialog._expected_list.item(idx)
        assert item is not None
        item.setCheckState(Qt.Checked)
    assert dialog._pass_btn.isEnabled() is True
    dialog._notes_edit.setPlainText("all good")
    dialog._mark_passed()
    assert dialog.final_result == "passed"
    artifacts = list((tmp_path / "results").glob("demo-*.json"))
    assert artifacts
    text = artifacts[0].read_text(encoding="utf-8")
    assert '"result": "passed"' in text
    assert '"run_token": "demo-run-token"' in text
    assert '"checked_expected_checks": [' in text
    assert '"notes": "all good"' in text


def test_manual_scenario_dialog_writes_failed_artifact(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    """Fail action should write artifact and keep unchecked steps visible in payload."""
    monkeypatch.setenv(SCENARIO_ENV_RUN_TOKEN, "demo-fail-token")
    dialog = ManualScenarioChecklistDialog(
        _runtime(tmp_path),
        results_dir=tmp_path / "results",
    )
    qtbot.addWidget(dialog)
    first = dialog._steps_list.item(0)
    assert first is not None
    first.setCheckState(Qt.Checked)
    dialog._mark_failed()
    assert dialog.final_result == "failed"
    artifacts = list((tmp_path / "results").glob("demo-*.json"))
    assert artifacts
    text = artifacts[-1].read_text(encoding="utf-8")
    assert '"result": "failed"' in text
    assert '"run_token": "demo-fail-token"' in text
    assert '"checked_steps": [' in text
    assert '"checked_expected_checks": [' in text


def test_manual_scenario_dialog_renders_structured_sections(
    qtbot, tmp_path: Path
) -> None:
    """Structured scenario metadata should be visible above the checklist lists."""
    dialog = ManualScenarioChecklistDialog(
        _runtime(tmp_path),
        results_dir=tmp_path / "results",
    )
    qtbot.addWidget(dialog)
    texts = [label.text() for label in dialog.findChildren(QLabel)]
    joined = "\n".join(texts)
    assert "Goal:" in joined
    assert "Workflow family:" in joined
    assert "Start context:" in joined
    assert "Focus files:" in joined
    assert "Finish condition:" in joined
    assert "Operator hints:" in joined
    assert "Inspection paths:" in joined
    assert "RU/ui.txt" in joined
    assert "RU/menu.txt" in joined


def test_manual_scenario_dialog_keeps_details_in_scroll_area(
    qtbot, tmp_path: Path
) -> None:
    """Scenario metadata should live in a bounded scroll area to free space for checklists."""
    dialog = ManualScenarioChecklistDialog(
        _runtime(tmp_path),
        results_dir=tmp_path / "results",
    )
    qtbot.addWidget(dialog)
    scroll = dialog.findChild(QScrollArea, "scenario_details_scroll")
    assert scroll is not None
    assert scroll.widget() is not None
    assert scroll.maximumHeight() == 190


def test_manual_scenario_dialog_wraps_checklist_rows_without_horizontal_scroll(
    qtbot, tmp_path: Path
) -> None:
    """Long checklist rows should wrap instead of requiring horizontal scrolling."""
    dialog = ManualScenarioChecklistDialog(
        _runtime(tmp_path),
        results_dir=tmp_path / "results",
    )
    qtbot.addWidget(dialog)
    for widget in (dialog._steps_list, dialog._expected_list):
        assert widget.wordWrap() is True
        assert widget.textElideMode() == Qt.TextElideMode.ElideNone
        assert (
            widget.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        first = widget.item(0)
        assert first is not None
        assert first.toolTip() == first.text()


def test_manual_scenario_dialog_copy_buttons_export_project_and_path_targets(
    qtbot, tmp_path: Path
) -> None:
    """Copy buttons should export absolute project-root and fixture-path targets."""
    dialog = ManualScenarioChecklistDialog(
        _runtime(tmp_path),
        results_dir=tmp_path / "results",
    )
    qtbot.addWidget(dialog)

    clipboard = QGuiApplication.clipboard()
    assert clipboard is not None
    project_button = dialog.findChild(
        type(dialog._pass_btn), "copy_project_root_button"
    )
    assert project_button is not None
    qtbot.mouseClick(project_button, Qt.LeftButton)
    assert clipboard.text() == str((tmp_path / "project").resolve())

    focus_button = dialog.findChild(type(dialog._pass_btn), "copy_focus_paths_button")
    assert focus_button is not None
    qtbot.mouseClick(focus_button, Qt.LeftButton)
    focus_text = clipboard.text()
    assert str((tmp_path / "project" / "RU" / "ui.txt").resolve()) in focus_text
    assert str((tmp_path / "project" / "RU" / "menu.txt").resolve()) in focus_text

    inspection_button = dialog.findChild(
        type(dialog._pass_btn), "copy_inspection_paths_button"
    )
    assert inspection_button is not None
    qtbot.mouseClick(inspection_button, Qt.LeftButton)
    assert clipboard.text() == str((tmp_path / "project" / "RU" / "ui.txt").resolve())


def test_manual_scenario_dialog_blocks_pass_until_all_checks(
    qtbot, tmp_path: Path
) -> None:
    """Pass should stay blocked until every step and expected-check item is ticked."""
    dialog = ManualScenarioChecklistDialog(
        _runtime(tmp_path),
        results_dir=tmp_path / "results",
    )
    qtbot.addWidget(dialog)

    dialog._mark_passed()
    assert dialog.final_result is None
    assert not list((tmp_path / "results").glob("demo-*.json"))

    step = dialog._steps_list.item(0)
    assert step is not None
    step.setCheckState(Qt.Checked)
    dialog._mark_passed()
    assert dialog.final_result is None
    assert not list((tmp_path / "results").glob("demo-*.json"))


def test_manual_scenario_dialog_cancel_writes_incomplete_artifact(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    """Cancel should persist incomplete artifact so runner can report summary details."""
    monkeypatch.setenv(SCENARIO_ENV_RUN_TOKEN, "demo-cancel-token")
    dialog = ManualScenarioChecklistDialog(
        _runtime(tmp_path),
        results_dir=tmp_path / "results",
    )
    qtbot.addWidget(dialog)
    dialog._notes_edit.setPlainText("cancelled during review")
    dialog._mark_incomplete()
    assert dialog.final_result == "incomplete"
    artifacts = list((tmp_path / "results").glob("demo-*.json"))
    assert artifacts
    text = artifacts[-1].read_text(encoding="utf-8")
    assert '"result": "incomplete"' in text
    assert '"run_token": "demo-cancel-token"' in text
    assert '"notes": "cancelled during review"' in text
