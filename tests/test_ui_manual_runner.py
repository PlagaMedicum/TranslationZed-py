"""Tests for manual UI runner script orchestration helpers."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

from translationzed_py.gui.manual_scenario_runtime import (
    SCENARIO_ENV_RUN_TOKEN,
    parse_manual_scenario,
)


def _load_module() -> ModuleType:
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "ui_manual_runner.py"
    spec = importlib.util.spec_from_file_location("ui_manual_runner", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[misc]
    return module


def _make_fixture(repo_root: Path, fixture_name: str) -> None:
    path = repo_root / "tests" / "fixtures" / fixture_name / "EN"
    path.mkdir(parents=True, exist_ok=True)
    (path / "language.txt").write_text(
        "text = English,\ncharset = UTF-8,\n",
        encoding="utf-8",
    )
    (path / "ui.txt").write_text('A = "x"\n', encoding="utf-8")
    (repo_root / "tests").mkdir(parents=True, exist_ok=True)
    (repo_root / "tests" / "test_gui_smoke.py").write_text(
        "def test_stub() -> None:\n    assert True\n",
        encoding="utf-8",
    )


def _scenario_payload() -> dict[str, object]:
    return {
        "id": "demo",
        "title": "Demo",
        "workflow_family": "open_save",
        "manual_depth": "full_workflow",
        "goal": "Verify manual runner orchestration on a deterministic demo fixture.",
        "start_context": "Launch with EN selected and open EN/ui.txt from the Project tree.",
        "fixture_root": "demo",
        "focus_files": ["EN/ui.txt"],
        "finish_condition": "Leave EN/ui.txt active with the saved value visible.",
        "selected_locales": ["EN"],
        "steps": ["Open EN/ui.txt"],
        "expected_checks": ["EN/ui.txt stays editable"],
        "tracked_repo_files": ["tests/test_gui_smoke.py"],
        "env_overrides": {},
        "prefs_extras": {},
        "automation_pytest_selectors": ["tests/test_gui_smoke.py"],
    }


def _write_manual_checklist(
    *,
    results_dir: Path,
    scenario_id: str,
    result: str = "passed",
    run_token: str = "demo-run-token",
    notes: str = "",
) -> Path:
    results_dir.mkdir(parents=True, exist_ok=True)
    out = results_dir / f"{scenario_id}-{run_token}-9999999999999.json"
    payload = {
        "version": 1,
        "scenario_id": scenario_id,
        "title": "Demo",
        "fixture_root": "demo",
        "project_root": "/tmp/project",
        "run_token": run_token,
        "result": result,
        "checked_steps": ["one"],
        "checked_expected_checks": ["ok"],
        "all_steps": ["one"],
        "expected_checks": ["ok"],
        "notes": notes,
        "completed_at_ms": 9999999999999,
    }
    out.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return out


def test_materialize_fixture_copies_source_tree(tmp_path: Path) -> None:
    """Fixture materializer should copy source fixture to temp project root."""
    module = _load_module()
    repo_root = tmp_path / "repo"
    _make_fixture(repo_root, "demo")
    temp_root = tmp_path / "temp"
    temp_root.mkdir(parents=True, exist_ok=True)
    project = module._materialize_fixture(
        repo_root=repo_root,
        fixture_root="demo",
        temp_root=temp_root,
    )
    assert project.is_dir()
    assert (project / "EN" / "ui.txt").read_text(encoding="utf-8") == 'A = "x"\n'


def test_run_one_scenario_writes_artifact_and_runs_manual_and_auto(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """One scenario run should emit artifact and invoke manual+auto subprocesses."""
    module = _load_module()
    repo_root = tmp_path / "repo"
    _make_fixture(repo_root, "demo")
    scenario = parse_manual_scenario(
        {
            **_scenario_payload(),
            "env_overrides": {"TZP_DEMO": "1"},
        }
    )

    calls: list[list[str]] = []

    def _fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
        calls.append(list(cmd))
        if list(cmd[:3]) == [sys.executable, "-m", "translationzed_py"]:
            run_token = str(kwargs["env"][SCENARIO_ENV_RUN_TOKEN])
            _write_manual_checklist(
                results_dir=results_dir,
                scenario_id="demo",
                run_token=run_token,
                notes="manual pass",
            )
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(module.subprocess, "run", _fake_run)
    results_dir = tmp_path / "artifacts" / "manual-ui"
    rc = module._run_one_scenario(
        scenario=scenario,
        repo_root=repo_root,
        results_dir=results_dir,
        auto=True,
        auto_only=False,
        headless_result=None,
        headless_notes="",
    )
    assert rc == 0
    assert len(calls) == 2
    assert calls[0][:3] == [sys.executable, "-m", "translationzed_py"]
    assert calls[1][:3] == [sys.executable, "-m", "pytest"]
    artifacts = list(results_dir.glob("demo-run-*.json"))
    assert artifacts
    payload = json.loads(artifacts[0].read_text(encoding="utf-8"))
    assert payload["mode"] == "manual+auto"
    assert payload["manual_return_code"] == 0
    assert payload["manual_outcome"] == "passed"
    assert isinstance(payload["manual_checklist_artifact"], str)
    assert payload["manual_checked_steps"] == ["one"]
    assert payload["manual_checked_expected_checks"] == ["ok"]
    assert payload["manual_notes"] == "manual pass"
    assert payload["manual_run_token"]
    tracked_files = payload["tracked_files"]
    assert isinstance(tracked_files, list)
    assert tracked_files
    assert tracked_files[0]["path"] == "tests/test_gui_smoke.py"
    assert payload["auto_return_code"] == 0


def test_run_one_scenario_headless_manual_result_skips_gui_launch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Headless manual-result mode should write checklist artifact without GUI subprocess."""
    module = _load_module()
    repo_root = tmp_path / "repo"
    _make_fixture(repo_root, "demo")
    scenario = parse_manual_scenario(_scenario_payload())

    calls: list[list[str]] = []

    def _fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
        calls.append(list(cmd))
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(module.subprocess, "run", _fake_run)
    results_dir = tmp_path / "artifacts" / "manual-ui"
    rc = module._run_one_scenario(
        scenario=scenario,
        repo_root=repo_root,
        results_dir=results_dir,
        auto=True,
        auto_only=False,
        headless_result="passed",
        headless_notes="headless",
    )
    assert rc == 0
    assert len(calls) == 1
    assert calls[0][:3] == [sys.executable, "-m", "pytest"]

    run_artifacts = list(results_dir.glob("demo-run-*.json"))
    assert run_artifacts
    run_payload = json.loads(run_artifacts[0].read_text(encoding="utf-8"))
    assert run_payload["mode"] == "headless-manual+auto"
    assert run_payload["manual_return_code"] == 0
    assert run_payload["manual_outcome"] == "passed"
    assert run_payload["manual_run_token"]
    assert run_payload["tracked_files"][0]["path"] == "tests/test_gui_smoke.py"
    assert run_payload["auto_return_code"] == 0

    checklist_artifacts = [
        path for path in results_dir.glob("demo-*.json") if "-run-" not in path.name
    ]
    assert checklist_artifacts
    checklist_payload = json.loads(checklist_artifacts[0].read_text(encoding="utf-8"))
    assert checklist_payload["result"] == "passed"
    assert checklist_payload["headless"] is True
    assert checklist_payload["run_token"] == run_payload["manual_run_token"]
    assert checklist_payload["checked_expected_checks"] == []
    assert checklist_payload["notes"] == "headless"


def test_run_one_scenario_fails_when_manual_result_is_failed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Manual mode must return non-zero when checklist artifact result is failed."""
    module = _load_module()
    repo_root = tmp_path / "repo"
    _make_fixture(repo_root, "demo")
    scenario = parse_manual_scenario(
        {
            **_scenario_payload(),
            "automation_pytest_selectors": [],
        }
    )
    results_dir = tmp_path / "artifacts" / "manual-ui"

    def _fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
        if list(cmd[:3]) == [sys.executable, "-m", "translationzed_py"]:
            run_token = str(kwargs["env"][SCENARIO_ENV_RUN_TOKEN])
            _write_manual_checklist(
                results_dir=results_dir,
                scenario_id="demo",
                result="failed",
                run_token=run_token,
                notes="broken",
            )
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(module.subprocess, "run", _fake_run)
    rc = module._run_one_scenario(
        scenario=scenario,
        repo_root=repo_root,
        results_dir=results_dir,
        auto=False,
        auto_only=False,
        headless_result=None,
        headless_notes="",
    )
    assert rc != 0
    run_artifact = sorted(results_dir.glob("demo-run-*.json"))[-1]
    run_payload = json.loads(run_artifact.read_text(encoding="utf-8"))
    assert run_payload["manual_outcome"] == "failed"
    assert run_payload["manual_notes"] == "broken"


def test_run_one_scenario_fails_when_manual_artifact_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Manual mode must return non-zero when no checklist artifact is produced."""
    module = _load_module()
    repo_root = tmp_path / "repo"
    _make_fixture(repo_root, "demo")
    scenario = parse_manual_scenario(
        {
            **_scenario_payload(),
            "automation_pytest_selectors": [],
        }
    )
    results_dir = tmp_path / "artifacts" / "manual-ui"

    def _fake_run(_cmd, **_kwargs):  # type: ignore[no-untyped-def]
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(module.subprocess, "run", _fake_run)
    rc = module._run_one_scenario(
        scenario=scenario,
        repo_root=repo_root,
        results_dir=results_dir,
        auto=False,
        auto_only=False,
        headless_result=None,
        headless_notes="",
    )
    assert rc != 0
    run_artifact = sorted(results_dir.glob("demo-run-*.json"))[-1]
    run_payload = json.loads(run_artifact.read_text(encoding="utf-8"))
    assert run_payload["manual_outcome"] == "incomplete"
    assert run_payload["manual_checklist_artifact"] is None


def test_run_one_scenario_prints_failed_summary_with_note(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """Failed manual outcome summary should include checked counts and note preview."""
    module = _load_module()
    repo_root = tmp_path / "repo"
    _make_fixture(repo_root, "demo")
    scenario = parse_manual_scenario(
        {
            **_scenario_payload(),
            "automation_pytest_selectors": [],
        }
    )
    results_dir = tmp_path / "artifacts" / "manual-ui"

    def _fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
        if list(cmd[:3]) == [sys.executable, "-m", "translationzed_py"]:
            run_token = str(kwargs["env"][SCENARIO_ENV_RUN_TOKEN])
            _write_manual_checklist(
                results_dir=results_dir,
                scenario_id="demo",
                result="failed",
                run_token=run_token,
                notes="manual failure details",
            )
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(module.subprocess, "run", _fake_run)
    rc = module._run_one_scenario(
        scenario=scenario,
        repo_root=repo_root,
        results_dir=results_dir,
        auto=False,
        auto_only=False,
        headless_result=None,
        headless_notes="",
    )
    assert rc != 0
    output = capsys.readouterr().out
    assert "scenario-result id=demo result=failed" in output
    assert "checked_steps=1/1" in output
    assert "checked_expected=1/1" in output
    assert "note=manual failure details" in output


def test_run_one_scenario_prints_incomplete_summary(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """Incomplete manual outcome summary should print empty checklist path and note."""
    module = _load_module()
    repo_root = tmp_path / "repo"
    _make_fixture(repo_root, "demo")
    scenario = parse_manual_scenario(
        {
            **_scenario_payload(),
            "automation_pytest_selectors": [],
        }
    )
    results_dir = tmp_path / "artifacts" / "manual-ui"

    def _fake_run(_cmd, **_kwargs):  # type: ignore[no-untyped-def]
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(module.subprocess, "run", _fake_run)
    rc = module._run_one_scenario(
        scenario=scenario,
        repo_root=repo_root,
        results_dir=results_dir,
        auto=False,
        auto_only=False,
        headless_result=None,
        headless_notes="",
    )
    assert rc != 0
    output = capsys.readouterr().out
    assert "scenario-result id=demo result=incomplete" in output
    assert "checklist=-" in output
    assert "note=-" in output


def test_run_one_scenario_accepts_incomplete_artifact_without_run_token(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Checklist cancel/incomplete artifacts without run_token should still be correlated."""
    module = _load_module()
    repo_root = tmp_path / "repo"
    _make_fixture(repo_root, "demo")
    scenario = parse_manual_scenario(
        {
            **_scenario_payload(),
            "automation_pytest_selectors": [],
        }
    )
    results_dir = tmp_path / "artifacts" / "manual-ui"

    def _fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
        if list(cmd[:3]) == [sys.executable, "-m", "translationzed_py"]:
            out = results_dir / "demo-9999999999999.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "version": 1,
                "scenario_id": "demo",
                "title": "Demo",
                "fixture_root": "demo",
                "project_root": "/tmp/project",
                "run_token": "",
                "result": "incomplete",
                "checked_steps": ["one"],
                "checked_expected_checks": [],
                "all_steps": ["one"],
                "expected_checks": ["ok"],
                "notes": "cancelled in checklist",
                "completed_at_ms": 9999999999999,
            }
            out.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(module.subprocess, "run", _fake_run)
    rc = module._run_one_scenario(
        scenario=scenario,
        repo_root=repo_root,
        results_dir=results_dir,
        auto=False,
        auto_only=False,
        headless_result=None,
        headless_notes="",
    )
    assert rc != 0
    run_artifact = sorted(results_dir.glob("demo-run-*.json"))[-1]
    run_payload = json.loads(run_artifact.read_text(encoding="utf-8"))
    assert run_payload["manual_outcome"] == "incomplete"
    assert run_payload["manual_checklist_artifact"] is not None
    assert run_payload["manual_checked_steps"] == ["one"]
    assert run_payload["manual_notes"] == "cancelled in checklist"


def test_run_one_scenario_accepts_failed_artifact_without_run_token(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Failed checklist artifact without run_token should still be correlated."""
    module = _load_module()
    repo_root = tmp_path / "repo"
    _make_fixture(repo_root, "demo")
    scenario = parse_manual_scenario(
        {
            **_scenario_payload(),
            "automation_pytest_selectors": [],
        }
    )
    results_dir = tmp_path / "artifacts" / "manual-ui"

    def _fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
        if list(cmd[:3]) == [sys.executable, "-m", "translationzed_py"]:
            out = results_dir / "demo-9999999999999.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "version": 1,
                "scenario_id": "demo",
                "title": "Demo",
                "fixture_root": "demo",
                "project_root": "/tmp/project",
                "run_token": "",
                "result": "failed",
                "checked_steps": ["one"],
                "checked_expected_checks": [],
                "all_steps": ["one"],
                "expected_checks": ["ok"],
                "notes": "found blocker",
                "completed_at_ms": 9999999999999,
            }
            out.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(module.subprocess, "run", _fake_run)
    rc = module._run_one_scenario(
        scenario=scenario,
        repo_root=repo_root,
        results_dir=results_dir,
        auto=False,
        auto_only=False,
        headless_result=None,
        headless_notes="",
    )
    assert rc != 0
    run_artifact = sorted(results_dir.glob("demo-run-*.json"))[-1]
    run_payload = json.loads(run_artifact.read_text(encoding="utf-8"))
    assert run_payload["manual_outcome"] == "failed"
    assert run_payload["manual_checklist_artifact"] is not None
    assert run_payload["manual_checked_steps"] == ["one"]
    assert run_payload["manual_notes"] == "found blocker"


def test_run_one_scenario_detects_checklist_when_scenario_id_contains_run(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Scenario IDs containing '-run' must still match checklist artifacts correctly."""
    module = _load_module()
    repo_root = tmp_path / "repo"
    _make_fixture(repo_root, "demo")
    scenario = parse_manual_scenario(
        {
            **_scenario_payload(),
            "id": "qa-checklist-manual-run",
            "title": "Demo",
            "workflow_family": "qa_checklist",
            "manual_depth": "same_file_diagnostic",
            "goal": "Verify checklist correlation for scenario ids containing run.",
            "start_context": "Launch with EN selected and open EN/ui.txt.",
            "finish_condition": "Leave EN/ui.txt active after the failed QA run.",
            "automation_pytest_selectors": [],
        }
    )
    results_dir = tmp_path / "artifacts" / "manual-ui"

    def _fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
        if list(cmd[:3]) == [sys.executable, "-m", "translationzed_py"]:
            run_token = str(kwargs["env"][SCENARIO_ENV_RUN_TOKEN])
            _write_manual_checklist(
                results_dir=results_dir,
                scenario_id="qa-checklist-manual-run",
                result="failed",
                run_token=run_token,
                notes="detected",
            )
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(module.subprocess, "run", _fake_run)
    rc = module._run_one_scenario(
        scenario=scenario,
        repo_root=repo_root,
        results_dir=results_dir,
        auto=False,
        auto_only=False,
        headless_result=None,
        headless_notes="",
    )
    assert rc != 0
    run_artifact = sorted(results_dir.glob("qa-checklist-manual-run-run-*.json"))[-1]
    run_payload = json.loads(run_artifact.read_text(encoding="utf-8"))
    assert run_payload["manual_outcome"] == "failed"
    assert run_payload["manual_checklist_artifact"] is not None
    assert run_payload["manual_notes"] == "detected"


def test_run_one_scenario_ignores_checklist_from_other_run_token(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Manual outcome correlation must require matching run token."""
    module = _load_module()
    repo_root = tmp_path / "repo"
    _make_fixture(repo_root, "demo")
    scenario = parse_manual_scenario(
        {
            **_scenario_payload(),
            "automation_pytest_selectors": [],
        }
    )
    results_dir = tmp_path / "artifacts" / "manual-ui"

    def _fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
        if list(cmd[:3]) == [sys.executable, "-m", "translationzed_py"]:
            _write_manual_checklist(
                results_dir=results_dir,
                scenario_id="demo",
                result="passed",
                run_token="other-token",
            )
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(module.subprocess, "run", _fake_run)
    rc = module._run_one_scenario(
        scenario=scenario,
        repo_root=repo_root,
        results_dir=results_dir,
        auto=False,
        auto_only=False,
        headless_result=None,
        headless_notes="",
    )
    assert rc != 0
    run_artifact = sorted(results_dir.glob("demo-run-*.json"))[-1]
    run_payload = json.loads(run_artifact.read_text(encoding="utf-8"))
    assert run_payload["manual_outcome"] == "incomplete"


def test_main_list_uses_sorted_registry_order(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """`--list` should print sorted scenario IDs."""
    module = _load_module()
    repo_root = tmp_path / "repo"
    registry_path = repo_root / "tests" / "manual_scenarios"
    registry_path.mkdir(parents=True, exist_ok=True)
    (registry_path / "scenarios.json").write_text(
        json.dumps(
            {
                "version": 1,
                "scenarios": [
                    {
                        **_scenario_payload(),
                        "id": "z-last",
                        "title": "Z",
                    },
                    {
                        **_scenario_payload(),
                        "id": "a-first",
                        "title": "A",
                    },
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    _make_fixture(repo_root, "demo")
    monkeypatch.setattr(module, "_repo_root", lambda: repo_root)
    monkeypatch.setattr(
        module,
        "_parse_args",
        lambda: SimpleNamespace(
            registry="tests/manual_scenarios/scenarios.json",
            list=True,
            scenario="",
            batch="",
            results_dir="artifacts/manual-ui",
            auto=False,
            auto_only=False,
            headless_result="",
            headless_notes="",
        ),
    )
    assert module.main() == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert out[0].startswith("a-first\t")
    assert out[1].startswith("z-last\t")


def test_main_rejects_auto_only_with_headless_result(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """CLI should reject conflicting auto-only and headless-result flags."""
    module = _load_module()
    repo_root = tmp_path / "repo"
    registry_path = repo_root / "tests" / "manual_scenarios"
    registry_path.mkdir(parents=True, exist_ok=True)
    (registry_path / "scenarios.json").write_text(
        json.dumps(
            {
                "version": 1,
                "scenarios": [
                    {
                        **_scenario_payload(),
                    },
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    _make_fixture(repo_root, "demo")
    monkeypatch.setattr(module, "_repo_root", lambda: repo_root)
    monkeypatch.setattr(
        module,
        "_parse_args",
        lambda: SimpleNamespace(
            registry="tests/manual_scenarios/scenarios.json",
            list=False,
            scenario="demo",
            batch="",
            results_dir="artifacts/manual-ui",
            auto=False,
            auto_only=True,
            headless_result="passed",
            headless_notes="",
        ),
    )
    assert module.main() == 2
    assert (
        "--auto-only cannot be combined with --headless-result"
        in capsys.readouterr().out
    )
