"""Regression tests for manual UI scenario contract checker."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


def _load_module() -> ModuleType:
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "ui_manual_contract_check.py"
    spec = importlib.util.spec_from_file_location(
        "ui_manual_contract_check", script_path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[misc]
    return module


def _seed_repo_paths(repo_root: Path) -> None:
    (repo_root / "tests" / "fixtures" / "demo" / "EN").mkdir(
        parents=True, exist_ok=True
    )
    (repo_root / "tests" / "fixtures" / "demo" / "EN" / "language.txt").write_text(
        "text = English,\ncharset = UTF-8,\n",
        encoding="utf-8",
    )
    (repo_root / "tests" / "fixtures" / "demo" / "EN" / "ui.txt").write_text(
        'A = "x"\n',
        encoding="utf-8",
    )
    for rel in (
        "tests/test_gui_edit_save.py",
        "tests/test_gui_save_prompt.py",
        "tests/test_gui_conflicts.py",
        "tests/test_conflict_service.py",
        "tests/test_qa_async.py",
        "tests/test_gui_qa_panel.py",
        "tests/test_tm_workflow_service.py",
        "tests/test_gui_tm_preferences.py",
        "tests/test_source_reference_state.py",
        "tests/test_source_reference_ui.py",
        "tests/test_search_replace_service.py",
        "tests/test_main_window_replace_merge_clipboard.py",
        "tests/test_gui_service_adapters.py",
        "tests/test_tzp_comment_policy.py",
        "tests/test_saver.py",
    ):
        path = repo_root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("def test_stub() -> None:\n    assert True\n", encoding="utf-8")


def _write_registry(path: Path) -> None:
    payload = {
        "version": 1,
        "scenarios": [
            {
                "id": "demo",
                "title": "Demo",
                "fixture_root": "demo",
                "selected_locales": ["EN"],
                "steps": ["one"],
                "expected_checks": ["ok"],
                "automation_pytest_selectors": ["tests/test_gui_edit_save.py"],
            }
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_contract(path: Path, *, missing_key: str | None = None) -> None:
    workflows = {
        "open_save": {
            "description": "x",
            "selectors": ["tests/test_gui_edit_save.py"],
        },
        "conflict_resolution": {
            "description": "x",
            "selectors": ["tests/test_gui_conflicts.py"],
        },
        "qa_checklist": {
            "description": "x",
            "selectors": ["tests/test_qa_async.py"],
        },
        "tm_apply": {
            "description": "x",
            "selectors": ["tests/test_tm_workflow_service.py"],
        },
        "source_reference": {
            "description": "x",
            "selectors": ["tests/test_source_reference_ui.py"],
        },
        "search_replace": {
            "description": "x",
            "selectors": ["tests/test_search_replace_service.py"],
        },
        "tzp_writeback": {
            "description": "x",
            "selectors": ["tests/test_tzp_comment_policy.py"],
        },
    }
    if missing_key:
        workflows.pop(missing_key, None)
    payload = {
        "version": 1,
        "required_workflows": workflows,
        "deprecated_test_replacements": [],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_contract_check_passes_for_valid_payloads(tmp_path: Path) -> None:
    """Contract checker should pass for valid registry/workflow payloads."""
    module = _load_module()
    repo = tmp_path / "repo"
    _seed_repo_paths(repo)
    registry = repo / "tests" / "manual_scenarios" / "scenarios.json"
    contract = repo / "tests" / "manual_scenarios" / "workflow.json"
    _write_registry(registry)
    _write_contract(contract)
    errors = module.validate_manual_scenario_contracts(
        repo_root=repo,
        registry_path=registry,
        workflow_contract_path=contract,
        collect_selectors=False,
    )
    assert errors == []


def test_contract_check_detects_missing_required_workflow_key(tmp_path: Path) -> None:
    """Missing required workflow key should fail no-shrink contract."""
    module = _load_module()
    repo = tmp_path / "repo"
    _seed_repo_paths(repo)
    registry = repo / "tests" / "manual_scenarios" / "scenarios.json"
    contract = repo / "tests" / "manual_scenarios" / "workflow.json"
    _write_registry(registry)
    _write_contract(contract, missing_key="qa_checklist")
    errors = module.validate_manual_scenario_contracts(
        repo_root=repo,
        registry_path=registry,
        workflow_contract_path=contract,
        collect_selectors=False,
    )
    assert any("missing required workflow key: qa_checklist" in item for item in errors)


def test_contract_check_requires_replacements_for_removed_deprecated_selector(
    tmp_path: Path,
) -> None:
    """Removed deprecated selector should require valid replacement selectors."""
    module = _load_module()
    repo = tmp_path / "repo"
    _seed_repo_paths(repo)
    registry = repo / "tests" / "manual_scenarios" / "scenarios.json"
    contract = repo / "tests" / "manual_scenarios" / "workflow.json"
    _write_registry(registry)
    _write_contract(contract)
    payload = json.loads(contract.read_text(encoding="utf-8"))
    payload["deprecated_test_replacements"] = [
        {
            "deprecated_selector": "tests/test_removed_case.py::test_old_path",
            "replacement_selectors": [],
        }
    ]
    contract.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    errors = module.validate_manual_scenario_contracts(
        repo_root=repo,
        registry_path=registry,
        workflow_contract_path=contract,
        collect_selectors=False,
    )
    assert any(
        "replacement_selectors must be non-empty string list" in item for item in errors
    )
