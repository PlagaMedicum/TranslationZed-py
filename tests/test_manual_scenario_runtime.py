"""Contract tests for manual scenario runtime payload helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from translationzed_py.gui.manual_scenario_runtime import (
    ManualScenarioError,
    parse_manual_runtime,
    parse_scenario_registry,
    scenario_by_id,
)


def _scenario_row(*, scenario_id: str) -> dict[str, object]:
    return {
        "id": scenario_id,
        "title": "Scenario",
        "workflow_family": "open_save",
        "manual_depth": "full_workflow",
        "goal": "Verify the workflow.",
        "start_context": "Launch with RU selected.",
        "fixture_root": "manual_workflow",
        "focus_files": ["RU/ui.txt"],
        "finish_condition": "Leave RU/ui.txt active with the saved value visible.",
        "selected_locales": ["RU"],
        "steps": ["one"],
        "expected_checks": ["ok"],
        "tracked_repo_files": ["translationzed_py/gui/main_window.py"],
        "env_overrides": {"TZP_A": "1"},
        "prefs_extras": {"TZP_B": "2"},
        "automation_pytest_selectors": ["tests/test_gui_smoke.py"],
    }


def test_parse_registry_accepts_versioned_payload() -> None:
    """Registry parser should accept valid versioned payload."""
    payload = {"version": 1, "scenarios": [_scenario_row(scenario_id="one")]}
    scenarios = parse_scenario_registry(payload)
    assert len(scenarios) == 1
    assert scenarios[0].id == "one"
    assert scenarios[0].workflow_family == "open_save"
    assert scenarios[0].manual_depth == "full_workflow"
    assert scenarios[0].selected_locales == ("RU",)
    assert scenarios[0].focus_files == ("RU/ui.txt",)
    assert scenarios[0].tracked_repo_files == ("translationzed_py/gui/main_window.py",)
    assert scenarios[0].operator_hints == ()
    assert scenarios[0].inspection_paths == ()


def test_parse_registry_accepts_operator_hints_and_inspection_paths() -> None:
    """Scenario rows may include operator hints and inspection paths."""
    row = _scenario_row(scenario_id="guided")
    row["operator_hints"] = [
        "Copy the project root before opening an external file browser.",
    ]
    row["inspection_paths"] = ["RU/ui.txt"]
    payload = {"version": 1, "scenarios": [row]}
    scenarios = parse_scenario_registry(payload)
    assert scenarios[0].operator_hints == (
        "Copy the project root before opening an external file browser.",
    )
    assert scenarios[0].inspection_paths == ("RU/ui.txt",)


def test_manual_scenario_to_payload_is_json_shaped() -> None:
    """Scenario payload should round-trip with JSON-style lists, not tuples."""
    scenarios = parse_scenario_registry(
        {"version": 1, "scenarios": [_scenario_row(scenario_id="json-shape")]}
    )
    assert scenarios[0].to_payload()["focus_files"] == ["RU/ui.txt"]
    assert scenarios[0].to_payload()["selected_locales"] == ["RU"]
    assert scenarios[0].to_payload()["steps"] == ["one"]
    assert scenarios[0].to_payload()["expected_checks"] == ["ok"]
    assert scenarios[0].to_payload()["tracked_repo_files"] == [
        "translationzed_py/gui/main_window.py"
    ]
    assert scenarios[0].to_payload()["operator_hints"] == []
    assert scenarios[0].to_payload()["inspection_paths"] == []


def test_parse_registry_accepts_multiscript_locale_rows() -> None:
    """Registry parser should accept locale rows across non-Latin script families."""
    row = _scenario_row(scenario_id="multi")
    row["selected_locales"] = ["AR", "KO", "JP", "TH", "CN"]
    payload = {"version": 1, "scenarios": [row]}
    scenarios = parse_scenario_registry(payload)
    assert scenarios[0].selected_locales == ("AR", "KO", "JP", "TH", "CN")


def test_parse_registry_rejects_duplicate_ids() -> None:
    """Registry parser should reject duplicate scenario IDs."""
    payload = {
        "version": 1,
        "scenarios": [
            _scenario_row(scenario_id="dup"),
            _scenario_row(scenario_id="dup"),
        ],
    }
    with pytest.raises(ManualScenarioError, match="duplicate scenario ids"):
        parse_scenario_registry(payload)


def test_parse_runtime_accepts_runtime_shape() -> None:
    """Runtime parser should parse embedded scenario payload."""
    payload = {
        "version": 1,
        "scenario": _scenario_row(scenario_id="rt"),
        "project_root": "/tmp/project",
    }
    runtime = parse_manual_runtime(payload)
    assert runtime.version == 1
    assert runtime.project_root == "/tmp/project"
    assert runtime.scenario.id == "rt"


def test_scenario_by_id_requires_existing_id() -> None:
    """Scenario lookup should fail for unknown IDs."""
    scenarios = parse_scenario_registry(
        {"version": 1, "scenarios": [_scenario_row(scenario_id="present")]}
    )
    assert scenario_by_id(scenarios, "present").id == "present"
    with pytest.raises(ManualScenarioError, match="unknown scenario id"):
        scenario_by_id(scenarios, "missing")


def test_parse_registry_requires_non_empty_steps() -> None:
    """Scenario rows should require non-empty manual step list."""
    row = _scenario_row(scenario_id="broken")
    row["steps"] = []
    with pytest.raises(ManualScenarioError, match="steps must be a non-empty list"):
        parse_scenario_registry({"version": 1, "scenarios": [row]})


def test_parse_registry_requires_non_empty_tracked_repo_files() -> None:
    """Scenario rows should require non-empty tracked repo file list."""
    row = _scenario_row(scenario_id="broken-tracked")
    row["tracked_repo_files"] = []
    with pytest.raises(
        ManualScenarioError, match="tracked_repo_files must be a non-empty list"
    ):
        parse_scenario_registry({"version": 1, "scenarios": [row]})


def test_parse_registry_rejects_invalid_workflow_family() -> None:
    """Scenario rows should reject unknown workflow-family tokens."""
    row = _scenario_row(scenario_id="bad-family")
    row["workflow_family"] = "unknown_family"
    with pytest.raises(ManualScenarioError, match="workflow_family must be one of"):
        parse_scenario_registry({"version": 1, "scenarios": [row]})


def test_parse_registry_rejects_non_posix_focus_file_paths() -> None:
    """Focus files must be fixture-relative POSIX paths."""
    row = _scenario_row(scenario_id="bad-focus")
    row["focus_files"] = ["RU\\ui.txt"]
    with pytest.raises(
        ManualScenarioError, match="focus_files\\[0\\] must use POSIX-style"
    ):
        parse_scenario_registry({"version": 1, "scenarios": [row]})


def test_registry_fixture_file_is_valid_json_contract() -> None:
    """Committed registry fixture should remain valid contract JSON."""
    registry = Path("tests/manual_scenarios/scenarios.json")
    payload = json.loads(registry.read_text(encoding="utf-8"))
    scenarios = parse_scenario_registry(payload)
    assert len(scenarios) >= 6
    assert any(item.id == "qa-checklist-manual-run" for item in scenarios)
