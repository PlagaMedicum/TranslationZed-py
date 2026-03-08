"""Tests for manual UI runner script orchestration helpers."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

from translationzed_py.gui.manual_scenario_runtime import parse_manual_scenario


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
            "id": "demo",
            "title": "Demo",
            "fixture_root": "demo",
            "selected_locales": ["EN"],
            "steps": ["one"],
            "expected_checks": ["ok"],
            "env_overrides": {"TZP_DEMO": "1"},
            "prefs_extras": {},
            "automation_pytest_selectors": ["tests/test_gui_smoke.py"],
        }
    )

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
    assert payload["auto_return_code"] == 0


def test_run_one_scenario_headless_manual_result_skips_gui_launch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Headless manual-result mode should write checklist artifact without GUI subprocess."""
    module = _load_module()
    repo_root = tmp_path / "repo"
    _make_fixture(repo_root, "demo")
    scenario = parse_manual_scenario(
        {
            "id": "demo",
            "title": "Demo",
            "fixture_root": "demo",
            "selected_locales": ["EN"],
            "steps": ["one"],
            "expected_checks": ["ok"],
            "env_overrides": {},
            "prefs_extras": {},
            "automation_pytest_selectors": ["tests/test_gui_smoke.py"],
        }
    )

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
    assert run_payload["auto_return_code"] == 0

    checklist_artifacts = [
        path for path in results_dir.glob("demo-*.json") if "-run-" not in path.name
    ]
    assert checklist_artifacts
    checklist_payload = json.loads(
        checklist_artifacts[0].read_text(encoding="utf-8")
    )
    assert checklist_payload["result"] == "passed"
    assert checklist_payload["headless"] is True
    assert checklist_payload["notes"] == "headless"


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
                        "id": "z-last",
                        "title": "Z",
                        "fixture_root": "demo",
                        "selected_locales": ["EN"],
                        "steps": ["one"],
                        "expected_checks": ["ok"],
                    },
                    {
                        "id": "a-first",
                        "title": "A",
                        "fixture_root": "demo",
                        "selected_locales": ["EN"],
                        "steps": ["one"],
                        "expected_checks": ["ok"],
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
                        "id": "demo",
                        "title": "Demo",
                        "fixture_root": "demo",
                        "selected_locales": ["EN"],
                        "steps": ["one"],
                        "expected_checks": ["ok"],
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
    assert "--auto-only cannot be combined with --headless-result" in capsys.readouterr().out
