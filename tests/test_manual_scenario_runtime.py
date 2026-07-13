"""Contract tests for manual scenario runtime payload helpers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from translationzed_py.gui.manual_scenario_runtime import (
    ManualScenarioError,
    compute_tracked_file_hashes,
    load_manual_runtime,
    load_scenario_registry,
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
    normalized = runtime.to_payload()
    assert normalized["version"] == payload["version"]
    assert normalized["project_root"] == payload["project_root"]
    assert normalized["scenario"]["id"] == "rt"
    assert normalized["scenario"]["operator_hints"] == []


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (None, "scenario registry root must be an object"),
        ({"version": 2, "scenarios": []}, "scenario registry version must equal"),
        ({"version": 1, "scenarios": []}, "requires non-empty list"),
    ],
)
def test_parse_registry_rejects_invalid_root_contracts(
    payload: object, message: str
) -> None:
    """Registry roots should fail with specific errors before row parsing."""
    with pytest.raises(ManualScenarioError, match=message):
        parse_scenario_registry(payload)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("selected_locales", [""], r"selected_locales\[0\]"),
        ("operator_hints", "hint", "operator_hints must be a list"),
        ("env_overrides", [], "env_overrides must be an object"),
        ("env_overrides", {"": "1"}, "env_overrides keys"),
        ("env_overrides", {"TZP_A": 1}, "env_overrides.'TZP_A'"),
        ("focus_files", ["/RU/ui.txt"], "must be fixture-relative"),
        ("focus_files", ["RU/../ui.txt"], "must not contain"),
        ("focus_files", ["RU/ui.txt", "RU/ui.txt"], "duplicate path"),
        ("inspection_paths", "RU/ui.txt", "inspection_paths must be a list"),
    ],
)
def test_parse_registry_rejects_invalid_scenario_fields(
    field: str, value: object, message: str
) -> None:
    """Scenario fields should enforce their public type and path contracts."""
    row = _scenario_row(scenario_id=f"bad-{field}")
    row[field] = value
    with pytest.raises(ManualScenarioError, match=message):
        parse_scenario_registry({"version": 1, "scenarios": [row]})


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (None, "manual scenario runtime payload must be an object"),
        ({"version": 2}, "manual scenario runtime version must equal"),
    ],
)
def test_parse_runtime_rejects_invalid_root_contracts(
    payload: object, message: str
) -> None:
    """Runtime roots should reject invalid types and versions explicitly."""
    with pytest.raises(ManualScenarioError, match=message):
        parse_manual_runtime(payload)


def test_runtime_json_loaders_report_missing_and_invalid_files(tmp_path: Path) -> None:
    """JSON loaders should translate filesystem and decoding errors to contract errors."""
    missing = tmp_path / "missing.json"
    invalid = tmp_path / "invalid.json"
    invalid.write_text("{", encoding="utf-8")

    with pytest.raises(ManualScenarioError, match="missing scenario registry"):
        load_scenario_registry(missing)
    with pytest.raises(ManualScenarioError, match="invalid JSON in scenario registry"):
        load_scenario_registry(invalid)
    with pytest.raises(ManualScenarioError, match="missing manual runtime payload"):
        load_manual_runtime(missing)
    with pytest.raises(ManualScenarioError, match="invalid manual runtime JSON"):
        load_manual_runtime(invalid)


def test_compute_tracked_file_hashes_is_sorted_and_deterministic(
    tmp_path: Path,
) -> None:
    """Tracked evidence hashes should be repo-relative, sorted, and byte exact."""
    (tmp_path / "z.txt").write_bytes(b"z")
    (tmp_path / "a.txt").write_bytes(b"alpha")

    rows = compute_tracked_file_hashes(
        repo_root=tmp_path,
        tracked_repo_files=("z.txt", "a.txt"),
    )

    assert rows == [
        {"path": "a.txt", "sha256": hashlib.sha256(b"alpha").hexdigest()},
        {"path": "z.txt", "sha256": hashlib.sha256(b"z").hexdigest()},
    ]


@pytest.mark.parametrize(
    ("paths", "message"),
    [
        (("",), "must be a non-empty string"),
        (("/absolute.txt",), "must be repo-relative"),
        (("../outside.txt",), "escapes repo root"),
        (("missing.txt",), "must reference an existing file"),
        (("present.txt", "./present.txt"), "duplicate path"),
    ],
)
def test_compute_tracked_file_hashes_rejects_invalid_paths(
    tmp_path: Path, paths: tuple[str, ...], message: str
) -> None:
    """Tracked evidence paths should stay unique and contained by the repo root."""
    (tmp_path / "present.txt").write_text("present", encoding="utf-8")
    with pytest.raises(ManualScenarioError, match=message):
        compute_tracked_file_hashes(repo_root=tmp_path, tracked_repo_files=paths)


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
