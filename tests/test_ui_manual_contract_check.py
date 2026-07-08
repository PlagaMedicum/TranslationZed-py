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


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _seed_repo_paths(repo_root: Path) -> None:
    for locale in ("EN", "RU", "KO"):
        _write_text(
            repo_root
            / "tests"
            / "fixtures"
            / "manual_workflow"
            / locale
            / "language.txt",
            f"text = {locale},\ncharset = UTF-8,\n",
        )
    _write_text(
        repo_root / "tests" / "fixtures" / "manual_workflow" / "EN" / "ui.txt",
        'UI_HELLO = "Hello"\n',
    )
    _write_text(
        repo_root / "tests" / "fixtures" / "manual_workflow" / "RU" / "ui.txt",
        'UI_HELLO = "Привет"\n',
    )
    _write_text(
        repo_root / "tests" / "fixtures" / "manual_workflow" / "KO" / "ui.txt",
        'UI_HELLO = "안녕"\n',
    )
    _write_text(
        repo_root / "tests" / "fixtures" / "manual_workflow" / "EN" / "menu.txt",
        'MENU_START = "Start"\n',
    )
    _write_text(
        repo_root / "tests" / "fixtures" / "manual_workflow" / "RU" / "menu.txt",
        'MENU_START = "Старт"\n',
    )
    _write_text(
        repo_root / "tests" / "fixtures" / "manual_workflow" / "RU" / "tm_memory.txt",
        'TM_KEY = "Память"\n',
    )
    _write_text(
        repo_root
        / "tests"
        / "fixtures"
        / "manual_workflow"
        / "RU"
        / "search_scope.txt",
        'SEARCH_ONE = "alpha"\n',
    )
    _write_text(
        repo_root
        / "tests"
        / "fixtures"
        / "manual_workflow"
        / "RU"
        / "search_scope_extra.txt",
        'SEARCH_TWO = "alpha"\n',
    )
    _write_text(
        repo_root
        / "tests"
        / "fixtures"
        / "manual_workflow"
        / "KO"
        / "search_scope.txt",
        'SEARCH_KO = "알파"\n',
    )
    _write_text(
        repo_root / "tests" / "fixtures" / "manual_workflow" / "RU" / "tzp_status.txt",
        'STATUS = "Черновик"\n',
    )

    for locale in ("EN", "RU"):
        _write_text(
            repo_root
            / "tests"
            / "fixtures"
            / "conflict_manual"
            / locale
            / "language.txt",
            f"text = {locale},\ncharset = UTF-8,\n",
        )
        _write_text(
            repo_root / "tests" / "fixtures" / "conflict_manual" / locale / "ui.txt",
            'UI_OK = "ok"\n',
        )
    for name in (
        "conflict_drop_cache.txt",
        "conflict_drop_original.txt",
        "conflict_merge_mixed.txt",
    ):
        _write_text(
            repo_root / "tests" / "fixtures" / "conflict_manual" / "EN" / name,
            'A = "file"\n',
        )
        _write_text(
            repo_root / "tests" / "fixtures" / "conflict_manual" / "RU" / name,
            'A = "target"\n',
        )

    for locale in ("EN", "RU"):
        _write_text(
            repo_root / "tests" / "fixtures" / "qa_manual" / locale / "language.txt",
            f"text = {locale},\ncharset = UTF-8,\n",
        )
    _write_text(
        repo_root / "tests" / "fixtures" / "qa_manual" / "EN" / "ui.txt",
        'HELLO = "Hello"\n',
    )
    _write_text(
        repo_root / "tests" / "fixtures" / "qa_manual" / "RU" / "ui.txt",
        'HELLO = "Привет"\n',
    )

    for locale in ("RU", "KO", "PTBR"):
        _write_text(
            repo_root / "tests" / "fixtures" / "prod_like" / locale / "language.txt",
            f"text = {locale},\ncharset = UTF-8,\n",
        )
    _write_text(
        repo_root / "tests" / "fixtures" / "prod_like" / "RU" / "IG_UI_RU.txt",
        'RU_KEY = "Привет"\n',
    )
    _write_text(
        repo_root / "tests" / "fixtures" / "prod_like" / "KO" / "IG_UI_KO.txt",
        'KO_KEY = "안녕"\n',
    )
    _write_text(
        repo_root / "tests" / "fixtures" / "prod_like" / "PTBR" / "IG_UI_PTBR.txt",
        'PT_KEY = "Olá"\n',
    )

    _write_text(
        repo_root / "translationzed_py" / "gui" / "main_window.py",
        "MAIN = 1\n",
    )
    _write_text(
        repo_root / "translationzed_py" / "gui" / "preferences_dialog.py",
        "PREFS = 1\n",
    )
    _write_text(
        repo_root / "translationzed_py" / "gui" / "main_window_panel_helpers.py",
        "PANELS = 1\n",
    )
    _write_text(
        repo_root / "translationzed_py" / "gui" / "source_reference_ui.py",
        "SRC_UI = 1\n",
    )
    _write_text(
        repo_root / "translationzed_py" / "gui" / "source_reference_state.py",
        "SRC_STATE = 1\n",
    )
    _write_text(
        repo_root / "translationzed_py" / "core" / "file_workflow.py",
        "FILE = 1\n",
    )
    _write_text(
        repo_root / "translationzed_py" / "core" / "conflict_service.py",
        "CONFLICT = 1\n",
    )
    _write_text(
        repo_root / "translationzed_py" / "core" / "search_replace_service.py",
        "SEARCH = 1\n",
    )
    _write_text(
        repo_root / "translationzed_py" / "core" / "tm_workflow_service.py",
        "TM = 1\n",
    )
    _write_text(
        repo_root / "translationzed_py" / "core" / "source_reference_service.py",
        "SRC = 1\n",
    )
    _write_text(
        repo_root / "translationzed_py" / "core" / "tzp_comment_policy.py",
        "TZP = 1\n",
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
        "tests/test_gui_save_encoding.py",
        "tests/test_encoding_diagnostics.py",
    ):
        _write_text(
            repo_root / rel,
            "def test_stub() -> None:\n    assert True\n",
        )


def _scenario_rows() -> list[dict[str, object]]:
    return [
        {
            "id": "open-edit-save-basic",
            "title": "Open save",
            "workflow_family": "open_save",
            "manual_depth": "full_workflow",
            "goal": "Verify open/edit/save on RU/ui.txt and RU/menu.txt.",
            "start_context": "Launch with RU selected and use RU/ui.txt first.",
            "fixture_root": "manual_workflow",
            "focus_files": ["RU/ui.txt", "RU/menu.txt"],
            "finish_condition": "Leave RU/ui.txt active after switching through RU/menu.txt.",
            "selected_locales": ["RU"],
            "steps": [
                "Open RU/ui.txt from the Project tree.",
                "Switch to RU/menu.txt and then back to RU/ui.txt.",
            ],
            "expected_checks": ["RU/ui.txt remains stable after save."],
            "tracked_repo_files": [
                "translationzed_py/gui/main_window.py",
                "translationzed_py/core/file_workflow.py",
            ],
            "env_overrides": {},
            "prefs_extras": {},
            "automation_pytest_selectors": [
                "tests/test_gui_edit_save.py",
                "tests/test_gui_save_prompt.py",
            ],
        },
        {
            "id": "conflict-resolution-flow",
            "title": "Conflict flow",
            "workflow_family": "conflict_resolution",
            "manual_depth": "full_workflow",
            "goal": (
                "Verify RU/conflict_drop_cache.txt, RU/conflict_drop_original.txt, "
                "and RU/conflict_merge_mixed.txt in one guided conflict run."
            ),
            "start_context": (
                "Launch with RU selected and switch between RU/conflict_drop_cache.txt, "
                "RU/conflict_drop_original.txt, RU/conflict_merge_mixed.txt, and RU/ui.txt."
            ),
            "fixture_root": "conflict_manual",
            "focus_files": [
                "RU/conflict_drop_cache.txt",
                "RU/conflict_drop_original.txt",
                "RU/conflict_merge_mixed.txt",
                "RU/ui.txt",
            ],
            "finish_condition": (
                "Leave RU/conflict_merge_mixed.txt active after saving each conflict path, "
                "switching through RU/ui.txt, and completing all three conflict paths."
            ),
            "selected_locales": ["RU"],
            "operator_hints": [
                "After Drop cache, choose Cache only if only later conflict files are listed.",
                "Do not write later conflict files before their own steps.",
            ],
            "steps": [
                "Open RU/conflict_drop_cache.txt from the Project tree.",
                "Open RU/conflict_drop_original.txt from the Project tree.",
                "Open RU/conflict_merge_mixed.txt from the Project tree.",
                (
                    "Save each resolved file and switch through RU/ui.txt after each "
                    "conflict path. Write only RU/conflict_drop_original.txt for Drop "
                    "original and only RU/conflict_merge_mixed.txt for Merge."
                ),
            ],
            "expected_checks": [
                "RU/conflict_drop_cache.txt, RU/conflict_drop_original.txt, and "
                "RU/conflict_merge_mixed.txt all resolve without repeat prompts."
            ],
            "tracked_repo_files": [
                "translationzed_py/gui/main_window.py",
                "translationzed_py/core/conflict_service.py",
            ],
            "env_overrides": {},
            "prefs_extras": {},
            "automation_pytest_selectors": [
                "tests/test_gui_conflicts.py",
                "tests/test_conflict_service.py",
            ],
        },
        {
            "id": "qa-checklist-manual-run",
            "title": "QA",
            "workflow_family": "qa_checklist",
            "manual_depth": "same_file_diagnostic",
            "goal": "Verify manual QA on RU/ui.txt.",
            "start_context": "Launch with RU selected and open RU/ui.txt.",
            "fixture_root": "qa_manual",
            "focus_files": ["RU/ui.txt"],
            "finish_condition": "Leave RU/ui.txt active after the QA rerun.",
            "selected_locales": ["RU"],
            "steps": ["Open RU/ui.txt from the Project tree."],
            "expected_checks": ["RU/ui.txt shows QA output."],
            "tracked_repo_files": [
                "translationzed_py/gui/main_window_panel_helpers.py",
            ],
            "env_overrides": {},
            "prefs_extras": {},
            "automation_pytest_selectors": [
                "tests/test_qa_async.py",
                "tests/test_gui_qa_panel.py",
            ],
        },
        {
            "id": "encoding-charsets-manual-roundtrip",
            "title": "Encoding",
            "workflow_family": "encoding_charsets",
            "manual_depth": "multi_file_roundtrip",
            "goal": "Verify RU/IG_UI_RU.txt, KO/IG_UI_KO.txt, and PTBR/IG_UI_PTBR.txt roundtrip.",
            "start_context": "Launch with RU, KO, and PTBR selected.",
            "fixture_root": "prod_like",
            "focus_files": [
                "RU/IG_UI_RU.txt",
                "KO/IG_UI_KO.txt",
                "PTBR/IG_UI_PTBR.txt",
            ],
            "finish_condition": (
                "Leave PTBR/IG_UI_PTBR.txt active after saving and switching "
                "through all three files."
            ),
            "selected_locales": ["RU", "KO", "PTBR"],
            "steps": [
                "Open RU/IG_UI_RU.txt from the Project tree and save one edited value.",
                (
                    "Switch through KO/IG_UI_KO.txt and PTBR/IG_UI_PTBR.txt, "
                    "saving one edited value in each file."
                ),
            ],
            "expected_checks": ["RU/IG_UI_RU.txt remains readable."],
            "tracked_repo_files": [
                "translationzed_py/core/file_workflow.py",
            ],
            "env_overrides": {},
            "prefs_extras": {},
            "automation_pytest_selectors": [
                "tests/test_gui_save_encoding.py",
                "tests/test_encoding_diagnostics.py",
            ],
        },
        {
            "id": "tm-apply-triage-flow",
            "title": "TM",
            "workflow_family": "tm_apply",
            "manual_depth": "full_workflow",
            "goal": "Verify RU/ui.txt uses RU/tm_memory.txt for TM workflow checks.",
            "start_context": "Launch with RU selected and use RU/ui.txt first.",
            "fixture_root": "manual_workflow",
            "focus_files": ["RU/ui.txt", "RU/tm_memory.txt"],
            "finish_condition": "Leave RU/ui.txt active after switching through RU/tm_memory.txt.",
            "selected_locales": ["RU"],
            "steps": [
                "Open RU/ui.txt from the Project tree.",
                "Switch to RU/tm_memory.txt and back to RU/ui.txt.",
            ],
            "expected_checks": ["RU/ui.txt keeps the TM-applied value."],
            "tracked_repo_files": [
                "translationzed_py/core/tm_workflow_service.py",
            ],
            "env_overrides": {},
            "prefs_extras": {},
            "automation_pytest_selectors": [
                "tests/test_tm_workflow_service.py",
                "tests/test_gui_tm_preferences.py",
            ],
        },
        {
            "id": "source-reference-fallback-flow",
            "title": "Source reference",
            "workflow_family": "source_reference",
            "manual_depth": "full_workflow",
            "goal": (
                "Verify RU/ui.txt uses requested KO source and RU/menu.txt stays "
                "empty when KO is missing."
            ),
            "start_context": "Launch with RU and KO selected and use RU/ui.txt first.",
            "fixture_root": "manual_workflow",
            "focus_files": ["RU/ui.txt", "RU/menu.txt"],
            "finish_condition": (
                "Leave RU/menu.txt active after confirming requested-source-or-empty behavior."
            ),
            "selected_locales": ["RU", "KO"],
            "steps": [
                "Open RU/ui.txt from the Project tree.",
                "Switch to RU/menu.txt to observe the empty Source column.",
            ],
            "expected_checks": ["RU/menu.txt keeps an empty Source column."],
            "tracked_repo_files": [
                "translationzed_py/core/source_reference_service.py",
                "translationzed_py/gui/source_reference_state.py",
                "translationzed_py/gui/source_reference_ui.py",
                "translationzed_py/gui/preferences_dialog.py",
            ],
            "env_overrides": {},
            "prefs_extras": {},
            "automation_pytest_selectors": [
                "tests/test_source_reference_state.py",
                "tests/test_source_reference_ui.py",
            ],
        },
        {
            "id": "tzp-writeback-opt-in",
            "title": "Status-comment writeback (opt-in)",
            "workflow_family": "tzp_writeback",
            "manual_depth": "full_workflow",
            "goal": "Verify RU/tzp_status.txt keeps TZP comments under opt-in writeback.",
            "start_context": "Launch with RU selected and use RU/tzp_status.txt first.",
            "fixture_root": "manual_workflow",
            "focus_files": ["RU/tzp_status.txt", "RU/ui.txt"],
            "finish_condition": (
                "Leave RU/tzp_status.txt active after saving RU/tzp_status.txt and "
                "switching through RU/ui.txt."
            ),
            "selected_locales": ["RU"],
            "steps": [
                "Open RU/tzp_status.txt from the Project tree and save the edited status row.",
                "Switch to RU/ui.txt and back to RU/tzp_status.txt.",
            ],
            "expected_checks": [
                "RU/tzp_status.txt keeps opt-in TZP comments coherent."
            ],
            "tracked_repo_files": [
                "translationzed_py/core/tzp_comment_policy.py",
            ],
            "env_overrides": {},
            "prefs_extras": {},
            "automation_pytest_selectors": [
                "tests/test_tzp_comment_policy.py",
                "tests/test_saver.py",
            ],
        },
        {
            "id": "search-replace-sidebar-all-scopes",
            "title": "Search replace",
            "workflow_family": "search_replace",
            "manual_depth": "full_workflow",
            "goal": (
                "Verify RU/search_scope.txt, RU/search_scope_extra.txt, "
                "and KO/search_scope.txt cover search scopes."
            ),
            "start_context": "Launch with RU and KO selected and use RU/search_scope.txt first.",
            "fixture_root": "manual_workflow",
            "focus_files": [
                "RU/search_scope.txt",
                "RU/search_scope_extra.txt",
                "KO/search_scope.txt",
            ],
            "finish_condition": (
                "Leave RU/search_scope.txt active after switching "
                "through RU/search_scope_extra.txt and KO/search_scope.txt."
            ),
            "selected_locales": ["RU", "KO"],
            "steps": [
                "Open RU/search_scope.txt from the Project tree.",
                "Switch through RU/search_scope_extra.txt and KO/search_scope.txt.",
            ],
            "expected_checks": [
                "RU/search_scope.txt keeps replace scope behavior coherent."
            ],
            "tracked_repo_files": [
                "translationzed_py/core/search_replace_service.py",
            ],
            "env_overrides": {},
            "prefs_extras": {},
            "automation_pytest_selectors": [
                "tests/test_search_replace_service.py",
                "tests/test_main_window_replace_merge_clipboard.py",
            ],
        },
    ]


def test_manual_contract_summary_reports_registry_shape(tmp_path: Path) -> None:
    """Structured summary should expose registry/workflow details for tooling."""
    module = _load_module()
    repo_root = tmp_path / "repo"
    _seed_repo_paths(repo_root)
    registry_path = repo_root / "tests" / "manual_scenarios" / "scenarios.json"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps({"version": 1, "scenarios": _scenario_rows()}, indent=2) + "\n",
        encoding="utf-8",
    )
    workflow_path = (
        repo_root / "tests" / "manual_scenarios" / "workflow_test_surface_contract.json"
    )
    workflow_path.write_text(
        json.dumps(
            {
                "version": 1,
                "required_workflows": {
                    "open_save": {"selectors": ["tests/test_gui_edit_save.py"]},
                    "conflict_resolution": {
                        "selectors": ["tests/test_gui_conflicts.py"],
                        "required_scenario_ids": ["conflict-resolution-flow"],
                    },
                    "qa_checklist": {"selectors": ["tests/test_gui_qa_panel.py"]},
                    "encoding_charsets": {
                        "selectors": ["tests/test_gui_save_encoding.py"]
                    },
                    "tm_apply": {"selectors": ["tests/test_tm_workflow_service.py"]},
                    "source_reference": {
                        "selectors": ["tests/test_source_reference_ui.py"]
                    },
                    "search_replace": {
                        "selectors": ["tests/test_search_replace_service.py"]
                    },
                    "tzp_writeback": {
                        "selectors": ["tests/test_tzp_comment_policy.py"]
                    },
                },
                "deprecated_test_replacements": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    summary = module.build_manual_contract_summary(
        repo_root=repo_root,
        registry_path=registry_path,
        workflow_contract_path=workflow_path,
        collect_selectors=False,
    )

    assert summary["status"] == "passed"
    assert summary["scenario_count"] == len(_scenario_rows())
    assert "conflict_resolution" in summary["workflow_keys"]


def _write_registry(path: Path) -> None:
    payload = {"version": 1, "scenarios": _scenario_rows()}
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
            "required_scenario_ids": ["conflict-resolution-flow"],
            "selectors": ["tests/test_gui_conflicts.py"],
        },
        "qa_checklist": {
            "description": "x",
            "selectors": ["tests/test_qa_async.py"],
        },
        "encoding_charsets": {
            "description": "x",
            "selectors": [
                "tests/test_gui_save_encoding.py",
                "tests/test_encoding_diagnostics.py",
            ],
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


def test_contract_check_requires_conflict_flow_mapping(tmp_path: Path) -> None:
    """Conflict workflow must keep explicit single-scenario mapping contract."""
    module = _load_module()
    repo = tmp_path / "repo"
    _seed_repo_paths(repo)
    registry = repo / "tests" / "manual_scenarios" / "scenarios.json"
    contract = repo / "tests" / "manual_scenarios" / "workflow.json"
    _write_registry(registry)
    _write_contract(contract)
    payload = json.loads(contract.read_text(encoding="utf-8"))
    payload["required_workflows"]["conflict_resolution"]["required_scenario_ids"] = []
    contract.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    errors = module.validate_manual_scenario_contracts(
        repo_root=repo,
        registry_path=registry,
        workflow_contract_path=contract,
        collect_selectors=False,
    )
    assert any("required_scenario_ids must equal" in item for item in errors)


def test_contract_check_rejects_missing_tracked_repo_file(tmp_path: Path) -> None:
    """Scenario tracked file contract should fail when tracked path is missing."""
    module = _load_module()
    repo = tmp_path / "repo"
    _seed_repo_paths(repo)
    registry = repo / "tests" / "manual_scenarios" / "scenarios.json"
    contract = repo / "tests" / "manual_scenarios" / "workflow.json"
    _write_registry(registry)
    payload = json.loads(registry.read_text(encoding="utf-8"))
    payload["scenarios"][0]["tracked_repo_files"] = ["tests/test_missing_case.py"]
    registry.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    _write_contract(contract)
    errors = module.validate_manual_scenario_contracts(
        repo_root=repo,
        registry_path=registry,
        workflow_contract_path=contract,
        collect_selectors=False,
    )
    assert any("must reference an existing file" in item for item in errors)


def test_contract_check_rejects_missing_focus_file(tmp_path: Path) -> None:
    """Scenario focus files must exist under the declared fixture root."""
    module = _load_module()
    repo = tmp_path / "repo"
    _seed_repo_paths(repo)
    registry = repo / "tests" / "manual_scenarios" / "scenarios.json"
    contract = repo / "tests" / "manual_scenarios" / "workflow.json"
    _write_registry(registry)
    payload = json.loads(registry.read_text(encoding="utf-8"))
    payload["scenarios"][0]["focus_files"] = ["RU/missing.txt"]
    registry.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    _write_contract(contract)
    errors = module.validate_manual_scenario_contracts(
        repo_root=repo,
        registry_path=registry,
        workflow_contract_path=contract,
        collect_selectors=False,
    )
    assert any(
        "focus_files entry missing under fixture root" in item for item in errors
    )


def test_contract_check_rejects_missing_inspection_path(tmp_path: Path) -> None:
    """Scenario inspection paths must exist under the declared fixture root."""
    module = _load_module()
    repo = tmp_path / "repo"
    _seed_repo_paths(repo)
    registry = repo / "tests" / "manual_scenarios" / "scenarios.json"
    contract = repo / "tests" / "manual_scenarios" / "workflow.json"
    _write_registry(registry)
    payload = json.loads(registry.read_text(encoding="utf-8"))
    payload["scenarios"][6]["inspection_paths"] = ["RU/missing.txt"]
    registry.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    _write_contract(contract)
    errors = module.validate_manual_scenario_contracts(
        repo_root=repo,
        registry_path=registry,
        workflow_contract_path=contract,
        collect_selectors=False,
    )
    assert any(
        "inspection_paths entry missing under fixture root" in item for item in errors
    )


def test_contract_check_rejects_banned_impossible_wording(tmp_path: Path) -> None:
    """Scenario authoring text must not require non-existent file-close semantics."""
    module = _load_module()
    repo = tmp_path / "repo"
    _seed_repo_paths(repo)
    registry = repo / "tests" / "manual_scenarios" / "scenarios.json"
    contract = repo / "tests" / "manual_scenarios" / "workflow.json"
    _write_registry(registry)
    payload = json.loads(registry.read_text(encoding="utf-8"))
    payload["scenarios"][0]["steps"] = ["Close file RU/ui.txt and reopen it."]
    registry.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    _write_contract(contract)
    errors = module.validate_manual_scenario_contracts(
        repo_root=repo,
        registry_path=registry,
        workflow_contract_path=contract,
        collect_selectors=False,
    )
    assert any(
        "must not require a non-existent close-file action" in item for item in errors
    )


def test_contract_check_rejects_vague_copied_file_wording(tmp_path: Path) -> None:
    """Scenarios must name inspection paths instead of vague copied-file prose."""
    module = _load_module()
    repo = tmp_path / "repo"
    _seed_repo_paths(repo)
    registry = repo / "tests" / "manual_scenarios" / "scenarios.json"
    contract = repo / "tests" / "manual_scenarios" / "workflow.json"
    _write_registry(registry)
    payload = json.loads(registry.read_text(encoding="utf-8"))
    payload["scenarios"][6]["steps"] = [
        "Inspect the copied file under the shown project root."
    ]
    registry.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    _write_contract(contract)
    errors = module.validate_manual_scenario_contracts(
        repo_root=repo,
        registry_path=registry,
        workflow_contract_path=contract,
        collect_selectors=False,
    )
    assert any("must name concrete inspection_paths" in item for item in errors)


def test_contract_check_requires_explicit_save_for_save_workflows(
    tmp_path: Path,
) -> None:
    """Save-dependent workflows must mention save explicitly."""
    module = _load_module()
    repo = tmp_path / "repo"
    _seed_repo_paths(repo)
    registry = repo / "tests" / "manual_scenarios" / "scenarios.json"
    contract = repo / "tests" / "manual_scenarios" / "workflow.json"
    _write_registry(registry)
    payload = json.loads(registry.read_text(encoding="utf-8"))
    payload["scenarios"][0]["goal"] = "Verify ordinary file switching on RU/ui.txt."
    payload["scenarios"][0]["steps"] = ["Open RU/ui.txt and edit one value."]
    payload["scenarios"][0][
        "finish_condition"
    ] = "Leave RU/ui.txt active after editing."
    payload["scenarios"][0]["expected_checks"] = [
        "RU/ui.txt remains stable after switching."
    ]
    registry.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    _write_contract(contract)
    errors = module.validate_manual_scenario_contracts(
        repo_root=repo,
        registry_path=registry,
        workflow_contract_path=contract,
        collect_selectors=False,
    )
    assert any(
        "save-dependent workflow must mention save explicitly" in item
        for item in errors
    )


def test_contract_check_rejects_conflict_cache_on_neutral_switch_file(
    tmp_path: Path,
) -> None:
    """Conflict flow must keep ui.txt as a neutral switch target."""
    module = _load_module()
    repo = tmp_path / "repo"
    _seed_repo_paths(repo)
    registry = repo / "tests" / "manual_scenarios" / "scenarios.json"
    contract = repo / "tests" / "manual_scenarios" / "workflow.json"
    _write_registry(registry)
    _write_contract(contract)
    stale_ui_cache = (
        repo
        / "tests"
        / "fixtures"
        / "conflict_manual"
        / ".tzp"
        / "cache"
        / "RU"
        / "ui.bin"
    )
    stale_ui_cache.parent.mkdir(parents=True, exist_ok=True)
    stale_ui_cache.write_bytes(b"stale")
    errors = module.validate_manual_scenario_contracts(
        repo_root=repo,
        registry_path=registry,
        workflow_contract_path=contract,
        collect_selectors=False,
    )
    assert any(
        "neutral switch file must not keep conflict cache artifact" in item
        for item in errors
    )


def test_contract_check_requires_precise_conflict_save_decisions(
    tmp_path: Path,
) -> None:
    """Conflict flow must explain cache-only and exact write-file decisions."""
    module = _load_module()
    repo = tmp_path / "repo"
    _seed_repo_paths(repo)
    registry = repo / "tests" / "manual_scenarios" / "scenarios.json"
    contract = repo / "tests" / "manual_scenarios" / "workflow.json"
    _write_registry(registry)
    payload = json.loads(registry.read_text(encoding="utf-8"))
    payload["scenarios"][1]["operator_hints"] = []
    payload["scenarios"][1]["steps"] = [
        "Open RU/conflict_drop_cache.txt from the Project tree.",
        "Save each resolved file and switch through RU/ui.txt after each conflict path.",
    ]
    registry.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    _write_contract(contract)
    errors = module.validate_manual_scenario_contracts(
        repo_root=repo,
        registry_path=registry,
        workflow_contract_path=contract,
        collect_selectors=False,
    )
    assert any("Drop cache should choose Cache only" in item for item in errors)
    assert any(
        "not to write unresolved future conflict files" in item for item in errors
    )
    assert any("exact Drop original write target" in item for item in errors)
    assert any("exact Merge write target" in item for item in errors)


def test_contract_check_requires_workflow_family_coverage(tmp_path: Path) -> None:
    """Registry must keep at least one scenario for each required workflow family."""
    module = _load_module()
    repo = tmp_path / "repo"
    _seed_repo_paths(repo)
    registry = repo / "tests" / "manual_scenarios" / "scenarios.json"
    contract = repo / "tests" / "manual_scenarios" / "workflow.json"
    _write_registry(registry)
    payload = json.loads(registry.read_text(encoding="utf-8"))
    payload["scenarios"] = [
        row for row in payload["scenarios"] if row["workflow_family"] != "qa_checklist"
    ]
    registry.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    _write_contract(contract)
    errors = module.validate_manual_scenario_contracts(
        repo_root=repo,
        registry_path=registry,
        workflow_contract_path=contract,
        collect_selectors=False,
    )
    assert any(
        "missing scenario for workflow_family: qa_checklist" in item for item in errors
    )


def test_contract_check_rejects_manual_workflow_be_bias(tmp_path: Path) -> None:
    """Generic manual_workflow scenarios must stay locale-diverse and not BE-centric."""
    module = _load_module()
    repo = tmp_path / "repo"
    _seed_repo_paths(repo)
    registry = repo / "tests" / "manual_scenarios" / "scenarios.json"
    contract = repo / "tests" / "manual_scenarios" / "workflow.json"
    _write_registry(registry)
    payload = json.loads(registry.read_text(encoding="utf-8"))
    payload["scenarios"][0]["selected_locales"] = ["BE"]
    payload["scenarios"][0]["focus_files"] = ["BE/ui.txt"]
    registry.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    _write_contract(contract)
    errors = module.validate_manual_scenario_contracts(
        repo_root=repo,
        registry_path=registry,
        workflow_contract_path=contract,
        collect_selectors=False,
    )
    assert any(
        "manual_workflow fixture must not use BE as a generic target locale" in item
        for item in errors
    )
