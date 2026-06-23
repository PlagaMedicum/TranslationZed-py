"""Regression tests for release-evidence sync helper."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


def _load_module() -> ModuleType:
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "release_evidence_sync.py"
    spec = importlib.util.spec_from_file_location("release_evidence_sync", script_path)
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


def _scenario_row() -> dict[str, object]:
    return {
        "id": "demo",
        "title": "Demo",
        "workflow_family": "open_save",
        "manual_depth": "full_workflow",
        "goal": "Verify release evidence sync on a deterministic manual workflow fixture.",
        "start_context": "Launch with RU selected and open RU/ui.txt from the Project tree.",
        "fixture_root": "manual_workflow",
        "focus_files": ["RU/ui.txt"],
        "finish_condition": "Leave RU/ui.txt active after the synced manual run.",
        "selected_locales": ["RU"],
        "steps": ["Open RU/ui.txt from the Project tree."],
        "expected_checks": ["RU/ui.txt remains editable."],
        "tracked_repo_files": [
            "translationzed_py/gui/main_window.py",
            "tests/fixtures/manual_workflow/RU/ui.txt",
        ],
        "env_overrides": {},
        "prefs_extras": {},
        "automation_pytest_selectors": ["tests/test_gui_smoke.py"],
        "operator_hints": [],
        "inspection_paths": [],
    }


def _seed_registry(repo_root: Path) -> tuple[Path, Path]:
    tracked = repo_root / "translationzed_py" / "gui" / "main_window.py"
    tracked.parent.mkdir(parents=True, exist_ok=True)
    tracked.write_text("MAIN = 1\n", encoding="utf-8")
    fixture = repo_root / "tests" / "fixtures" / "manual_workflow" / "RU" / "ui.txt"
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text('A = "x"\n', encoding="utf-8")
    (
        repo_root / "tests" / "fixtures" / "manual_workflow" / "EN" / "ui.txt"
    ).parent.mkdir(parents=True, exist_ok=True)
    (repo_root / "tests" / "fixtures" / "manual_workflow" / "EN" / "ui.txt").write_text(
        'A = "source"\n', encoding="utf-8"
    )
    (repo_root / "tests" / "test_gui_smoke.py").write_text(
        "def test_stub() -> None:\n    assert True\n",
        encoding="utf-8",
    )
    registry = repo_root / "tests" / "manual_scenarios" / "scenarios.json"
    _write_json(
        registry,
        {
            "version": 1,
            "scenarios": [_scenario_row()],
        },
    )
    return tracked, fixture


def _write_manual_pass_artifacts(
    *, repo_root: Path, tracked: Path, fixture: Path, results_dir: Path
) -> tuple[Path, Path]:
    run_token = "demo-run-token"
    checklist = results_dir / f"demo-{run_token}-1000.json"
    _write_json(
        checklist,
        {
            "version": 1,
            "scenario_id": "demo",
            "title": "Demo",
            "fixture_root": "manual_workflow",
            "project_root": str((repo_root / "tmp-project").resolve()),
            "run_token": run_token,
            "result": "passed",
            "checked_steps": ["step"],
            "checked_expected_checks": ["check"],
            "all_steps": ["step"],
            "expected_checks": ["check"],
            "notes": "ok",
            "completed_at_ms": 1000,
            "headless": False,
        },
    )
    run = results_dir / "demo-run-2000.json"
    _write_json(
        run,
        {
            "version": 1,
            "scenario": _scenario_row(),
            "mode": "manual",
            "manual_return_code": 0,
            "manual_outcome": "passed",
            "manual_checklist_artifact": str(checklist),
            "manual_run_token": run_token,
            "tracked_files": [
                {
                    "path": "tests/fixtures/manual_workflow/RU/ui.txt",
                    "sha256": _sha256(fixture),
                },
                {
                    "path": "translationzed_py/gui/main_window.py",
                    "sha256": _sha256(tracked),
                },
            ],
            "auto_return_code": None,
            "completed_at_ms": 2000,
        },
    )
    return checklist, run


def test_release_evidence_sync_updates_manifest_and_records(tmp_path: Path) -> None:
    """Sync should copy canonical records and update manifest entry."""
    module = _load_module()
    repo_root = tmp_path / "repo"
    tracked, fixture = _seed_registry(repo_root)
    results_dir = repo_root / "artifacts" / "manual-ui"
    checklist_source, run_source = _write_manual_pass_artifacts(
        repo_root=repo_root,
        tracked=tracked,
        fixture=fixture,
        results_dir=results_dir,
    )

    synced, failures = module.sync_release_evidence(
        repo_root=repo_root,
        registry_path=(repo_root / "tests" / "manual_scenarios" / "scenarios.json"),
        manifest_path=(
            repo_root / "tests" / "manual_scenarios" / "release_evidence_manifest.json"
        ),
        release_dir=(repo_root / "tests" / "manual_scenarios" / "release_evidence"),
        results_dir=results_dir,
        selected_scenarios=("demo",),
    )
    assert failures == []
    assert synced == ["demo"]

    manifest = json.loads(
        (
            repo_root / "tests" / "manual_scenarios" / "release_evidence_manifest.json"
        ).read_text(encoding="utf-8")
    )
    assert manifest["required_scenarios"] == ["demo"]
    assert manifest["entries"][0]["scenario_id"] == "demo"
    assert manifest["entries"][0]["source_checklist_artifact"] == str(
        checklist_source.relative_to(repo_root)
    )
    assert manifest["entries"][0]["source_run_artifact"] == str(
        run_source.relative_to(repo_root)
    )
    assert (
        repo_root / "tests" / "manual_scenarios" / "release_evidence" / "demo-run.json"
    ).is_file()
    assert (
        repo_root
        / "tests"
        / "manual_scenarios"
        / "release_evidence"
        / "demo-checklist.json"
    ).is_file()


def test_release_evidence_sync_fails_without_syncable_artifact(tmp_path: Path) -> None:
    """Sync should fail when no passed interactive run/checklist pair exists."""
    module = _load_module()
    repo_root = tmp_path / "repo"
    _seed_registry(repo_root)
    synced, failures = module.sync_release_evidence(
        repo_root=repo_root,
        registry_path=(repo_root / "tests" / "manual_scenarios" / "scenarios.json"),
        manifest_path=(
            repo_root / "tests" / "manual_scenarios" / "release_evidence_manifest.json"
        ),
        release_dir=(repo_root / "tests" / "manual_scenarios" / "release_evidence"),
        results_dir=(repo_root / "artifacts" / "manual-ui"),
        selected_scenarios=("demo",),
    )
    assert synced == []
    assert failures
    assert "no run artifacts found" in failures[0]


def test_release_evidence_sync_skips_run_missing_tracked_files(tmp_path: Path) -> None:
    """Sync should fail when candidate run payload misses A41 tracked hash rows."""
    module = _load_module()
    repo_root = tmp_path / "repo"
    tracked, fixture = _seed_registry(repo_root)
    results_dir = repo_root / "artifacts" / "manual-ui"
    checklist_source, run_source = _write_manual_pass_artifacts(
        repo_root=repo_root,
        tracked=tracked,
        fixture=fixture,
        results_dir=results_dir,
    )
    run_source.unlink()
    bad_run = results_dir / "demo-run-3000.json"
    _write_json(
        bad_run,
        {
            "version": 1,
            "scenario": {
                **_scenario_row(),
                "goal": "stale old scenario payload",
            },
            "mode": "manual",
            "manual_return_code": 0,
            "manual_outcome": "passed",
            "manual_checklist_artifact": str(checklist_source),
            "manual_run_token": "demo-run-token",
            "auto_return_code": None,
            "completed_at_ms": 3000,
        },
    )
    synced, failures = module.sync_release_evidence(
        repo_root=repo_root,
        registry_path=(repo_root / "tests" / "manual_scenarios" / "scenarios.json"),
        manifest_path=(
            repo_root / "tests" / "manual_scenarios" / "release_evidence_manifest.json"
        ),
        release_dir=(repo_root / "tests" / "manual_scenarios" / "release_evidence"),
        results_dir=results_dir,
        selected_scenarios=("demo",),
    )
    assert synced == []
    assert failures
    assert "no syncable passed interactive run/checklist pair found" in failures[0]


def test_release_evidence_sync_preflight_reports_syncable_scenario(
    tmp_path: Path,
) -> None:
    """Preflight should report a scenario as syncable when artifacts already match."""
    module = _load_module()
    repo_root = tmp_path / "repo"
    tracked, fixture = _seed_registry(repo_root)
    results_dir = repo_root / "artifacts" / "manual-ui"
    _write_manual_pass_artifacts(
        repo_root=repo_root,
        tracked=tracked,
        fixture=fixture,
        results_dir=results_dir,
    )

    rows = module.preflight_release_evidence_sync(
        repo_root=repo_root,
        registry_path=(repo_root / "tests" / "manual_scenarios" / "scenarios.json"),
        results_dir=results_dir,
        selected_scenarios=("demo",),
    )
    assert rows == [
        {
            "scenario_id": "demo",
            "status": "syncable",
            "reason": "syncable from artifacts/manual-ui/demo-run-2000.json",
        }
    ]


def test_release_evidence_sync_preflight_reports_payload_drift(
    tmp_path: Path,
) -> None:
    """Preflight should explain scenario-payload drift from the latest local run."""
    module = _load_module()
    repo_root = tmp_path / "repo"
    tracked, fixture = _seed_registry(repo_root)
    results_dir = repo_root / "artifacts" / "manual-ui"
    checklist_source, _run_source = _write_manual_pass_artifacts(
        repo_root=repo_root,
        tracked=tracked,
        fixture=fixture,
        results_dir=results_dir,
    )
    drifted_run = results_dir / "demo-run-3000.json"
    _write_json(
        drifted_run,
        {
            "version": 1,
            "scenario": {
                **_scenario_row(),
                "goal": "stale local payload",
            },
            "mode": "manual",
            "manual_return_code": 0,
            "manual_outcome": "passed",
            "manual_checklist_artifact": str(checklist_source),
            "manual_run_token": "demo-run-token",
            "tracked_files": [
                {
                    "path": "tests/fixtures/manual_workflow/RU/ui.txt",
                    "sha256": _sha256(fixture),
                },
                {
                    "path": "translationzed_py/gui/main_window.py",
                    "sha256": _sha256(tracked),
                },
            ],
            "auto_return_code": None,
            "completed_at_ms": 3000,
        },
    )

    rows = module.preflight_release_evidence_sync(
        repo_root=repo_root,
        registry_path=(repo_root / "tests" / "manual_scenarios" / "scenarios.json"),
        results_dir=results_dir,
        selected_scenarios=("demo",),
    )
    assert rows == [
        {
            "scenario_id": "demo",
            "status": "rerun-needed",
            "reason": "demo-run-3000.json: scenario payload drift",
        }
    ]
