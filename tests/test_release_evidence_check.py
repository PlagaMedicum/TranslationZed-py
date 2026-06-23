"""Regression coverage for release-evidence checker contracts."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


def _load_module() -> ModuleType:
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "release_evidence_check.py"
    spec = importlib.util.spec_from_file_location("release_evidence_check", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[misc]
    return module


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _scenario_row(
    *,
    scenario_id: str,
    workflow_family: str,
    fixture_root: str,
    focus_files: list[str],
    tracked_repo_files: list[str],
    selected_locales: list[str],
) -> dict[str, object]:
    return {
        "id": scenario_id,
        "title": scenario_id,
        "workflow_family": workflow_family,
        "manual_depth": "full_workflow",
        "goal": f"Verify {scenario_id} on a deterministic fixture.",
        "start_context": (
            f"Launch with {', '.join(selected_locales)} selected "
            f"and use {focus_files[0]}."
        ),
        "fixture_root": fixture_root,
        "focus_files": focus_files,
        "finish_condition": f"Leave {focus_files[0]} active after completing {scenario_id}.",
        "selected_locales": selected_locales,
        "steps": [f"Open {focus_files[0]} from the Project tree."],
        "expected_checks": [f"{focus_files[0]} remains usable."],
        "tracked_repo_files": tracked_repo_files,
        "env_overrides": {},
        "prefs_extras": {},
        "automation_pytest_selectors": ["tests/test_gui_smoke.py"],
        "operator_hints": [],
        "inspection_paths": [],
    }


def _write_valid_manifest_set(repo_root: Path) -> tuple[Path, Path]:
    release_dir = repo_root / "tests" / "manual_scenarios" / "release_evidence"
    release_dir.mkdir(parents=True, exist_ok=True)

    (repo_root / "translationzed_py" / "gui").mkdir(parents=True, exist_ok=True)
    (repo_root / "translationzed_py" / "core").mkdir(parents=True, exist_ok=True)
    (repo_root / "tests" / "fixtures" / "manual_workflow" / "RU").mkdir(
        parents=True, exist_ok=True
    )
    (repo_root / "tests" / "fixtures" / "manual_workflow" / "KO").mkdir(
        parents=True, exist_ok=True
    )
    (repo_root / "tests" / "fixtures" / "manual_workflow" / "EN").mkdir(
        parents=True, exist_ok=True
    )
    (repo_root / "tests" / "test_gui_smoke.py").write_text(
        "def test_stub() -> None:\n    assert True\n",
        encoding="utf-8",
    )
    tracked_main = repo_root / "translationzed_py" / "gui" / "main_window.py"
    tracked_main.write_text("MAIN = 1\n", encoding="utf-8")
    tracked_search = (
        repo_root / "translationzed_py" / "core" / "search_replace_service.py"
    )
    tracked_search.write_text("SEARCH = 1\n", encoding="utf-8")
    tracked_fixture = (
        repo_root / "tests" / "fixtures" / "manual_workflow" / "RU" / "ui.txt"
    )
    tracked_fixture.write_text('A = "x"\n', encoding="utf-8")
    (repo_root / "tests" / "fixtures" / "manual_workflow" / "EN" / "ui.txt").write_text(
        'A = "source"\n', encoding="utf-8"
    )
    (repo_root / "tests" / "fixtures" / "manual_workflow" / "KO" / "ui.txt").write_text(
        'A = "대상"\n', encoding="utf-8"
    )

    registry = repo_root / "tests" / "manual_scenarios" / "scenarios.json"
    _write_json(
        registry,
        {
            "version": 1,
            "scenarios": [
                _scenario_row(
                    scenario_id="status-triage-mixed-indicator",
                    workflow_family="status_triage",
                    fixture_root="manual_workflow",
                    focus_files=["RU/ui.txt"],
                    selected_locales=["RU"],
                    tracked_repo_files=[
                        "translationzed_py/gui/main_window.py",
                        "tests/fixtures/manual_workflow/RU/ui.txt",
                    ],
                ),
                _scenario_row(
                    scenario_id="search-replace-sidebar-all-scopes",
                    workflow_family="search_replace",
                    fixture_root="manual_workflow",
                    focus_files=["RU/ui.txt"],
                    selected_locales=["RU", "KO"],
                    tracked_repo_files=[
                        "translationzed_py/core/search_replace_service.py",
                        "tests/fixtures/manual_workflow/RU/ui.txt",
                    ],
                ),
            ],
        },
    )

    checklist_rows = {
        "status-triage-mixed-indicator": {
            "version": 1,
            "scenario_id": "status-triage-mixed-indicator",
            "title": "Status triage mixed-selection status-bar indicator",
            "fixture_root": "manual_workflow",
            "project_root": "tests/fixtures/manual_workflow",
            "result": "passed",
            "checked_steps": ["step"],
            "checked_expected_checks": ["check"],
            "all_steps": ["step"],
            "expected_checks": ["check"],
            "notes": "ok",
            "completed_at_ms": 1000,
        },
        "search-replace-sidebar-all-scopes": {
            "version": 1,
            "scenario_id": "search-replace-sidebar-all-scopes",
            "title": "Search+replace sidebar flow with all-scope confirmation",
            "fixture_root": "manual_workflow",
            "project_root": "tests/fixtures/manual_workflow",
            "result": "passed",
            "checked_steps": ["step"],
            "checked_expected_checks": ["check"],
            "all_steps": ["step"],
            "expected_checks": ["check"],
            "notes": "ok",
            "completed_at_ms": 1001,
        },
    }
    run_rows = {
        "status-triage-mixed-indicator": {
            "version": 1,
            "scenario": _scenario_row(
                scenario_id="status-triage-mixed-indicator",
                workflow_family="status_triage",
                fixture_root="manual_workflow",
                focus_files=["RU/ui.txt"],
                selected_locales=["RU"],
                tracked_repo_files=[
                    "translationzed_py/gui/main_window.py",
                    "tests/fixtures/manual_workflow/RU/ui.txt",
                ],
            ),
            "mode": "manual",
            "manual_return_code": 0,
            "auto_return_code": None,
            "tracked_files": [
                {
                    "path": "tests/fixtures/manual_workflow/RU/ui.txt",
                    "sha256": _sha256(tracked_fixture),
                },
                {
                    "path": "translationzed_py/gui/main_window.py",
                    "sha256": _sha256(tracked_main),
                },
            ],
            "completed_at_ms": 2000,
        },
        "search-replace-sidebar-all-scopes": {
            "version": 1,
            "scenario": _scenario_row(
                scenario_id="search-replace-sidebar-all-scopes",
                workflow_family="search_replace",
                fixture_root="manual_workflow",
                focus_files=["RU/ui.txt"],
                selected_locales=["RU", "KO"],
                tracked_repo_files=[
                    "translationzed_py/core/search_replace_service.py",
                    "tests/fixtures/manual_workflow/RU/ui.txt",
                ],
            ),
            "mode": "manual+auto",
            "manual_return_code": 0,
            "auto_return_code": 0,
            "tracked_files": [
                {
                    "path": "tests/fixtures/manual_workflow/RU/ui.txt",
                    "sha256": _sha256(tracked_fixture),
                },
                {
                    "path": "translationzed_py/core/search_replace_service.py",
                    "sha256": _sha256(tracked_search),
                },
            ],
            "completed_at_ms": 2001,
        },
    }

    entries = []
    for scenario_id in (
        "status-triage-mixed-indicator",
        "search-replace-sidebar-all-scopes",
    ):
        checklist_path = release_dir / f"{scenario_id}-checklist.json"
        _write_json(checklist_path, checklist_rows[scenario_id])
        run_path = release_dir / f"{scenario_id}-run.json"
        _write_json(run_path, run_rows[scenario_id])
        entries.append(
            {
                "scenario_id": scenario_id,
                "result": "passed",
                "interactive": True,
                "recorded_at_ms": 3000,
                "checklist_record": str(checklist_path.relative_to(repo_root)),
                "run_record": str(run_path.relative_to(repo_root)),
                "source_checklist_artifact": (
                    f"artifacts/manual-ui/{scenario_id}-source-checklist.json"
                ),
                "source_run_artifact": f"artifacts/manual-ui/{scenario_id}-source-run.json",
            }
        )

    manifest_path = (
        repo_root / "tests" / "manual_scenarios" / "release_evidence_manifest.json"
    )
    _write_json(
        manifest_path,
        {
            "version": 1,
            "required_scenarios": [
                "status-triage-mixed-indicator",
                "search-replace-sidebar-all-scopes",
            ],
            "entries": entries,
        },
    )
    return manifest_path, registry


def test_release_evidence_manifest_passes_for_valid_payload(tmp_path: Path) -> None:
    """Valid release-evidence payload should pass contract checks."""
    module = _load_module()
    repo_root = tmp_path / "repo"
    manifest, registry = _write_valid_manifest_set(repo_root)
    errors = module.validate_release_evidence_manifest(
        repo_root=repo_root,
        manifest_path=manifest,
        registry_path=registry,
    )
    assert errors == []


def test_release_evidence_manifest_fails_when_required_scenario_missing(
    tmp_path: Path,
) -> None:
    """Missing required scenario entry should fail manifest contract."""
    module = _load_module()
    repo_root = tmp_path / "repo"
    manifest, registry = _write_valid_manifest_set(repo_root)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["entries"] = payload["entries"][:1]
    _write_json(manifest, payload)
    errors = module.validate_release_evidence_manifest(
        repo_root=repo_root,
        manifest_path=manifest,
        registry_path=registry,
    )
    assert any("missing required scenario evidence entry" in item for item in errors)


def test_release_evidence_manifest_fails_for_headless_checklist(tmp_path: Path) -> None:
    """Checklist payload must not be marked headless."""
    module = _load_module()
    repo_root = tmp_path / "repo"
    manifest, registry = _write_valid_manifest_set(repo_root)
    checklist = (
        repo_root
        / "tests"
        / "manual_scenarios"
        / "release_evidence"
        / "status-triage-mixed-indicator-checklist.json"
    )
    payload = json.loads(checklist.read_text(encoding="utf-8"))
    payload["headless"] = True
    _write_json(checklist, payload)
    errors = module.validate_release_evidence_manifest(
        repo_root=repo_root,
        manifest_path=manifest,
        registry_path=registry,
    )
    assert any("headless=false" in item for item in errors)


def test_release_evidence_manifest_fails_for_auto_only_mode(tmp_path: Path) -> None:
    """Run payload mode must stay manual/manual+auto (no auto-only/headless modes)."""
    module = _load_module()
    repo_root = tmp_path / "repo"
    manifest, registry = _write_valid_manifest_set(repo_root)
    run_payload_path = (
        repo_root
        / "tests"
        / "manual_scenarios"
        / "release_evidence"
        / "search-replace-sidebar-all-scopes-run.json"
    )
    payload = json.loads(run_payload_path.read_text(encoding="utf-8"))
    payload["mode"] = "auto-only"
    _write_json(run_payload_path, payload)
    errors = module.validate_release_evidence_manifest(
        repo_root=repo_root,
        manifest_path=manifest,
        registry_path=registry,
    )
    assert any("run mode must be one of" in item for item in errors)


def test_release_evidence_summary_reports_pass_status(tmp_path: Path) -> None:
    """Structured summary should be available for terminal and external consumers."""
    module = _load_module()
    repo_root = tmp_path / "repo"
    manifest, registry = _write_valid_manifest_set(repo_root)
    summary = module.build_release_evidence_summary(
        repo_root=repo_root,
        manifest_path=manifest,
        registry_path=registry,
    )
    assert summary["status"] == "passed"
    assert summary["error_count"] == 0
    assert summary["required_scenarios"] == [
        "status-triage-mixed-indicator",
        "search-replace-sidebar-all-scopes",
    ]


def test_release_evidence_manifest_fails_when_passed_missing_expected_checks(
    tmp_path: Path,
) -> None:
    """Passed checklist payload must include all expected-check acknowledgements."""
    module = _load_module()
    repo_root = tmp_path / "repo"
    manifest, registry = _write_valid_manifest_set(repo_root)
    checklist = (
        repo_root
        / "tests"
        / "manual_scenarios"
        / "release_evidence"
        / "status-triage-mixed-indicator-checklist.json"
    )
    payload = json.loads(checklist.read_text(encoding="utf-8"))
    payload["checked_expected_checks"] = []
    _write_json(checklist, payload)
    errors = module.validate_release_evidence_manifest(
        repo_root=repo_root,
        manifest_path=manifest,
        registry_path=registry,
    )
    assert any("tick all expected outcomes" in item for item in errors)


def test_release_evidence_manifest_fails_for_stale_tracked_hash(tmp_path: Path) -> None:
    """Tracked-file hash drift should fail and require rerun guidance."""
    module = _load_module()
    repo_root = tmp_path / "repo"
    manifest, registry = _write_valid_manifest_set(repo_root)
    tracked = repo_root / "translationzed_py" / "gui" / "main_window.py"
    tracked.write_text("MAIN = 2\n", encoding="utf-8")
    errors = module.validate_release_evidence_manifest(
        repo_root=repo_root,
        manifest_path=manifest,
        registry_path=registry,
    )
    assert any("stale tracked hash" in item for item in errors)
    assert any("make release-evidence-sync" in item for item in errors)


def test_release_evidence_manifest_fails_when_run_scenario_payload_drifts(
    tmp_path: Path,
) -> None:
    """Scenario payload drift should force a fresh manual rerun and sync."""
    module = _load_module()
    repo_root = tmp_path / "repo"
    manifest, registry = _write_valid_manifest_set(repo_root)
    run_payload_path = (
        repo_root
        / "tests"
        / "manual_scenarios"
        / "release_evidence"
        / "status-triage-mixed-indicator-run.json"
    )
    payload = json.loads(run_payload_path.read_text(encoding="utf-8"))
    payload["scenario"]["goal"] = "old goal"
    _write_json(run_payload_path, payload)
    errors = module.validate_release_evidence_manifest(
        repo_root=repo_root,
        manifest_path=manifest,
        registry_path=registry,
    )
    assert any(
        "scenario payload no longer matches the registry" in item for item in errors
    )


def test_release_evidence_manifest_fails_when_required_list_drifts_from_registry(
    tmp_path: Path,
) -> None:
    """Manifest required_scenarios must match registry IDs exactly."""
    module = _load_module()
    repo_root = tmp_path / "repo"
    manifest, registry = _write_valid_manifest_set(repo_root)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["required_scenarios"] = ["status-triage-mixed-indicator"]
    _write_json(manifest, payload)
    errors = module.validate_release_evidence_manifest(
        repo_root=repo_root,
        manifest_path=manifest,
        registry_path=registry,
    )
    assert any("must match scenario registry ids" in item for item in errors)
