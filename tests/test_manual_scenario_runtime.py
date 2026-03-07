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
        "fixture_root": "conflict_manual",
        "selected_locales": ["BE"],
        "steps": ["one"],
        "expected_checks": ["ok"],
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
    assert scenarios[0].selected_locales == ("BE",)


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


def test_registry_fixture_file_is_valid_json_contract() -> None:
    """Committed registry fixture should remain valid contract JSON."""
    registry = Path("tests/manual_scenarios/scenarios.json")
    payload = json.loads(registry.read_text(encoding="utf-8"))
    scenarios = parse_scenario_registry(payload)
    assert len(scenarios) >= 6
    assert any(item.id == "qa-checklist-manual-run" for item in scenarios)
