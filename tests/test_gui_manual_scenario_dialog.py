"""GUI tests for manual scenario checklist dialog flow."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt

from translationzed_py.gui.manual_scenario_dialog import ManualScenarioChecklistDialog
from translationzed_py.gui.manual_scenario_runtime import (
    ManualScenario,
    ManualScenarioRuntime,
)


def _runtime(tmp_path: Path) -> ManualScenarioRuntime:
    scenario = ManualScenario(
        id="demo",
        title="Demo scenario",
        fixture_root="conflict_manual",
        selected_locales=("BE",),
        steps=("Open file", "Run action"),
        expected_checks=("No crash", "Output updated"),
        env_overrides={},
        prefs_extras={},
        automation_pytest_selectors=("tests/test_gui_smoke.py",),
    )
    return ManualScenarioRuntime(
        version=1,
        scenario=scenario,
        project_root=str((tmp_path / "project").resolve()),
    )


def test_manual_scenario_dialog_writes_pass_artifact(qtbot, tmp_path: Path) -> None:
    """Pass action should write artifact and close dialog."""
    dialog = ManualScenarioChecklistDialog(
        _runtime(tmp_path),
        results_dir=tmp_path / "results",
    )
    qtbot.addWidget(dialog)
    for idx in range(dialog._steps_list.count()):
        item = dialog._steps_list.item(idx)
        assert item is not None
        item.setCheckState(Qt.Checked)
    dialog._notes_edit.setPlainText("all good")
    dialog._mark_passed()
    assert dialog.final_result == "passed"
    artifacts = list((tmp_path / "results").glob("demo-*.json"))
    assert artifacts
    text = artifacts[0].read_text(encoding="utf-8")
    assert '"result": "passed"' in text
    assert '"notes": "all good"' in text


def test_manual_scenario_dialog_writes_failed_artifact(qtbot, tmp_path: Path) -> None:
    """Fail action should write artifact and keep unchecked steps visible in payload."""
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
    assert '"checked_steps": [' in text
