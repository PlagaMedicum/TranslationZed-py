"""Tests for deprecated manual-artifact cleanup script."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


def _load_module() -> ModuleType:
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "clean_manual_artifacts.py"
    spec = importlib.util.spec_from_file_location("clean_manual_artifacts", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[misc]
    return module


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _valid_checklist_payload() -> dict[str, object]:
    return {
        "scenario_id": "demo",
        "result": "failed",
        "checked_steps": ["one"],
        "checked_expected_checks": [],
        "all_steps": ["one"],
        "expected_checks": ["ok"],
        "notes": "note",
        "completed_at_ms": 123,
        "run_token": "demo-token",
    }


def _valid_run_payload() -> dict[str, object]:
    return {
        "manual_outcome": "failed",
        "manual_checklist_artifact": "artifacts/manual-ui/demo-1.json",
        "manual_checked_steps": ["one"],
        "manual_checked_expected_checks": [],
        "manual_all_steps": ["one"],
        "manual_expected_checks": ["ok"],
        "manual_notes": "note",
        "manual_run_token": "demo-token",
    }


def test_clean_manual_artifacts_removes_legacy_and_keeps_current(
    tmp_path: Path, monkeypatch
) -> None:
    """Cleanup script should remove malformed/legacy files and keep current schema."""
    module = _load_module()
    artifacts = tmp_path / "manual-ui"
    artifacts.mkdir(parents=True, exist_ok=True)

    legacy_checklist = artifacts / "demo-1.json"
    _write_json(
        legacy_checklist,
        {
            "scenario_id": "demo",
            "result": "passed",
            "checked_steps": ["one"],
            "all_steps": ["one"],
            "expected_checks": ["ok"],
            "notes": "",
            "completed_at_ms": 1,
        },
    )
    legacy_run = artifacts / "demo-run-1.json"
    _write_json(legacy_run, {"scenario": {"id": "demo"}, "manual_return_code": 0})
    valid_checklist = artifacts / "demo-2.json"
    _write_json(valid_checklist, _valid_checklist_payload())
    valid_run = artifacts / "demo-run-2.json"
    _write_json(valid_run, _valid_run_payload())

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "clean_manual_artifacts.py",
            "--artifacts-dir",
            str(artifacts),
        ],
    )
    assert module.main() == 0

    assert not legacy_checklist.exists()
    assert not legacy_run.exists()
    assert valid_checklist.exists()
    assert valid_run.exists()


def test_clean_manual_artifacts_dry_run_keeps_files(
    tmp_path: Path, monkeypatch
) -> None:
    """Dry-run mode should not delete deprecated artifacts."""
    module = _load_module()
    artifacts = tmp_path / "manual-ui"
    artifacts.mkdir(parents=True, exist_ok=True)
    legacy = artifacts / "demo-run-legacy.json"
    _write_json(legacy, {"manual_return_code": 0})

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "clean_manual_artifacts.py",
            "--artifacts-dir",
            str(artifacts),
            "--dry-run",
        ],
    )
    assert module.main() == 0
    assert legacy.exists()
