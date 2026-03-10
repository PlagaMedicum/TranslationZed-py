"""Regression coverage for release-evidence checker contracts."""

from __future__ import annotations

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


def _write_valid_manifest_set(repo_root: Path) -> Path:
    release_dir = repo_root / "tests" / "manual_scenarios" / "release_evidence"
    release_dir.mkdir(parents=True, exist_ok=True)

    checklist_rows = {
        "status-triage-mixed-indicator": {
            "version": 1,
            "scenario_id": "status-triage-mixed-indicator",
            "title": "Status triage mixed-selection status-bar indicator",
            "fixture_root": "conflict_manual",
            "project_root": "tests/fixtures/conflict_manual",
            "result": "passed",
            "checked_steps": ["step"],
            "all_steps": ["step"],
            "expected_checks": ["check"],
            "notes": "ok",
            "completed_at_ms": 1000,
        },
        "search-replace-sidebar-all-scopes": {
            "version": 1,
            "scenario_id": "search-replace-sidebar-all-scopes",
            "title": "Search+replace sidebar flow with all-scope confirmation",
            "fixture_root": "conflict_manual",
            "project_root": "tests/fixtures/conflict_manual",
            "result": "passed",
            "checked_steps": ["step"],
            "all_steps": ["step"],
            "expected_checks": ["check"],
            "notes": "ok",
            "completed_at_ms": 1001,
        },
    }
    run_rows = {
        "status-triage-mixed-indicator": {
            "version": 1,
            "scenario": {"id": "status-triage-mixed-indicator"},
            "mode": "manual",
            "manual_return_code": 0,
            "auto_return_code": None,
            "completed_at_ms": 2000,
        },
        "search-replace-sidebar-all-scopes": {
            "version": 1,
            "scenario": {"id": "search-replace-sidebar-all-scopes"},
            "mode": "manual+auto",
            "manual_return_code": 0,
            "auto_return_code": 0,
            "completed_at_ms": 2001,
        },
    }

    entries = []
    for scenario_id in (
        "status-triage-mixed-indicator",
        "search-replace-sidebar-all-scopes",
    ):
        checklist_path = release_dir / f"{scenario_id}-checklist.json"
        checklist_path.write_text(
            json.dumps(checklist_rows[scenario_id], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        run_path = release_dir / f"{scenario_id}-run.json"
        run_path.write_text(
            json.dumps(run_rows[scenario_id], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
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
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {
                "version": 1,
                "required_scenarios": [
                    "status-triage-mixed-indicator",
                    "search-replace-sidebar-all-scopes",
                ],
                "entries": entries,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest_path


def test_release_evidence_manifest_passes_for_valid_payload(tmp_path: Path) -> None:
    """Valid release-evidence payload should pass contract checks."""
    module = _load_module()
    repo_root = tmp_path / "repo"
    manifest = _write_valid_manifest_set(repo_root)
    errors = module.validate_release_evidence_manifest(
        repo_root=repo_root,
        manifest_path=manifest,
    )
    assert errors == []


def test_release_evidence_manifest_fails_when_required_scenario_missing(
    tmp_path: Path,
) -> None:
    """Missing required scenario entry should fail manifest contract."""
    module = _load_module()
    repo_root = tmp_path / "repo"
    manifest = _write_valid_manifest_set(repo_root)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["entries"] = payload["entries"][:1]
    manifest.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    errors = module.validate_release_evidence_manifest(
        repo_root=repo_root,
        manifest_path=manifest,
    )
    assert any("missing required scenario evidence entry" in item for item in errors)


def test_release_evidence_manifest_fails_for_headless_checklist(tmp_path: Path) -> None:
    """Checklist payload must not be marked headless."""
    module = _load_module()
    repo_root = tmp_path / "repo"
    manifest = _write_valid_manifest_set(repo_root)
    checklist = (
        repo_root
        / "tests"
        / "manual_scenarios"
        / "release_evidence"
        / "status-triage-mixed-indicator-checklist.json"
    )
    payload = json.loads(checklist.read_text(encoding="utf-8"))
    payload["headless"] = True
    checklist.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    errors = module.validate_release_evidence_manifest(
        repo_root=repo_root,
        manifest_path=manifest,
    )
    assert any("headless=false" in item for item in errors)


def test_release_evidence_manifest_fails_for_auto_only_mode(tmp_path: Path) -> None:
    """Run payload mode must stay manual/manual+auto (no auto-only/headless modes)."""
    module = _load_module()
    repo_root = tmp_path / "repo"
    manifest = _write_valid_manifest_set(repo_root)
    run_payload_path = (
        repo_root
        / "tests"
        / "manual_scenarios"
        / "release_evidence"
        / "search-replace-sidebar-all-scopes-run.json"
    )
    payload = json.loads(run_payload_path.read_text(encoding="utf-8"))
    payload["mode"] = "auto-only"
    run_payload_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    errors = module.validate_release_evidence_manifest(
        repo_root=repo_root,
        manifest_path=manifest,
    )
    assert any("run mode must be one of" in item for item in errors)
