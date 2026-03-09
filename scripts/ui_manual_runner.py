#!/usr/bin/env python3
"""Run declarative manual UI scenarios with optional automation bridge."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from translationzed_py.gui.manual_scenario_runtime import (
    SCENARIO_ENV_FILE,
    SCENARIO_ENV_RESULTS_DIR,
    SCENARIO_REGISTRY_DEFAULT,
    SCENARIO_REGISTRY_VERSION,
    ManualScenario,
    ManualScenarioError,
    ManualScenarioRuntime,
    load_scenario_registry,
    scenario_by_id,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _materialize_fixture(
    *, repo_root: Path, fixture_root: str, temp_root: Path
) -> Path:
    source = repo_root / "tests" / "fixtures" / fixture_root
    if not source.is_dir():
        raise ManualScenarioError(f"fixture root does not exist: {source}")
    target = temp_root / "project"
    shutil.copytree(source, target)
    return target


def _runtime_payload_path(
    *, scenario: ManualScenario, project_root: Path, temp_root: Path
) -> Path:
    payload = ManualScenarioRuntime(
        version=SCENARIO_REGISTRY_VERSION,
        scenario=scenario,
        project_root=str(project_root.resolve()),
    ).to_payload()
    path = temp_root / "manual_scenario_runtime.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _run_manual_app(
    *,
    project_root: Path,
    runtime_payload_path: Path,
    scenario: ManualScenario,
    results_dir: Path,
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env[SCENARIO_ENV_FILE] = str(runtime_payload_path)
    env[SCENARIO_ENV_RESULTS_DIR] = str(results_dir.resolve())
    for key, value in scenario.env_overrides.items():
        env[key] = value
    cmd = [sys.executable, "-m", "translationzed_py", str(project_root)]
    return subprocess.run(cmd, check=False, text=True, env=env)


def _run_auto_selectors(
    *,
    selectors: tuple[str, ...],
    repo_root: Path,
) -> subprocess.CompletedProcess[str] | None:
    if not selectors:
        return None
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-o",
        "addopts=",
        *selectors,
    ]
    return subprocess.run(cmd, check=False, text=True, cwd=repo_root)


def _write_run_artifact(
    *,
    results_dir: Path,
    scenario: ManualScenario,
    fixture_copy_root: Path,
    manual_rc: int | None,
    auto_rc: int | None,
    mode: str,
) -> Path:
    results_dir.mkdir(parents=True, exist_ok=True)
    stamp_ms = int(time.time() * 1000)
    safe_id = scenario.id.replace("/", "_")
    out_path = results_dir / f"{safe_id}-run-{stamp_ms}.json"
    payload: dict[str, Any] = {
        "version": SCENARIO_REGISTRY_VERSION,
        "scenario": asdict(scenario),
        "fixture_copy_root": str(fixture_copy_root),
        "mode": mode,
        "manual_return_code": manual_rc,
        "auto_return_code": auto_rc,
        "completed_at_ms": stamp_ms,
    }
    out_path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return out_path


def _write_headless_manual_artifact(
    *,
    results_dir: Path,
    runtime: ManualScenarioRuntime,
    result: str,
    notes: str,
) -> Path:
    results_dir.mkdir(parents=True, exist_ok=True)
    stamp_ms = int(time.time() * 1000)
    safe_id = runtime.scenario.id.replace("/", "_")
    out_path = results_dir / f"{safe_id}-{stamp_ms}.json"
    payload: dict[str, Any] = {
        "version": runtime.version,
        "scenario_id": runtime.scenario.id,
        "title": runtime.scenario.title,
        "fixture_root": runtime.scenario.fixture_root,
        "project_root": runtime.project_root,
        "result": result,
        "checked_steps": [],
        "all_steps": list(runtime.scenario.steps),
        "expected_checks": list(runtime.scenario.expected_checks),
        "notes": notes.strip(),
        "completed_at_ms": stamp_ms,
        "headless": True,
    }
    out_path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return out_path


def _run_one_scenario(
    *,
    scenario: ManualScenario,
    repo_root: Path,
    results_dir: Path,
    auto: bool,
    auto_only: bool,
    headless_result: str | None,
    headless_notes: str,
) -> int:
    with tempfile.TemporaryDirectory(prefix=f"tzp-manual-{scenario.id}-") as raw_temp:
        temp_root = Path(raw_temp)
        project_root = _materialize_fixture(
            repo_root=repo_root,
            fixture_root=scenario.fixture_root,
            temp_root=temp_root,
        )
        runtime_payload_path = _runtime_payload_path(
            scenario=scenario,
            project_root=project_root,
            temp_root=temp_root,
        )
        manual_rc: int | None = None
        auto_rc: int | None = None
        mode = "manual"
        if headless_result is not None:
            mode = "headless-manual"
            if auto:
                mode = "headless-manual+auto"
        elif auto_only:
            mode = "auto-only"
        elif auto:
            mode = "manual+auto"

        if headless_result is not None:
            checklist = _write_headless_manual_artifact(
                results_dir=results_dir,
                runtime=ManualScenarioRuntime(
                    version=SCENARIO_REGISTRY_VERSION,
                    scenario=scenario,
                    project_root=str(project_root.resolve()),
                ),
                result=headless_result,
                notes=headless_notes,
            )
            print(f"ui-manual-runner: wrote headless checklist artifact {checklist}")
            manual_rc = 0
        elif not auto_only:
            manual_proc = _run_manual_app(
                project_root=project_root,
                runtime_payload_path=runtime_payload_path,
                scenario=scenario,
                results_dir=results_dir,
            )
            manual_rc = int(manual_proc.returncode)

        if auto or auto_only:
            auto_proc = _run_auto_selectors(
                selectors=scenario.automation_pytest_selectors,
                repo_root=repo_root,
            )
            auto_rc = int(auto_proc.returncode) if auto_proc is not None else 0

        artifact = _write_run_artifact(
            results_dir=results_dir,
            scenario=scenario,
            fixture_copy_root=project_root,
            manual_rc=manual_rc,
            auto_rc=auto_rc,
            mode=mode,
        )
        print(f"ui-manual-runner: wrote artifact {artifact}")
        rc = 0
        if manual_rc not in (None, 0):
            rc = manual_rc
        if auto_rc not in (None, 0):
            rc = auto_rc
        return rc


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--registry",
        default=SCENARIO_REGISTRY_DEFAULT,
        help="Scenario registry JSON path.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List registered scenario IDs and titles.",
    )
    parser.add_argument(
        "--scenario",
        default="",
        help="Run one scenario ID.",
    )
    parser.add_argument(
        "--batch",
        default="",
        help="Comma-separated scenario IDs to run sequentially.",
    )
    parser.add_argument(
        "--results-dir",
        default="artifacts/manual-ui",
        help="Output directory for manual run artifacts.",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Also execute declared automation selectors after manual run.",
    )
    parser.add_argument(
        "--auto-only",
        action="store_true",
        help="Skip manual app launch and execute automation selectors only.",
    )
    parser.add_argument(
        "--headless-result",
        choices=("passed", "failed"),
        default="",
        help="Write checklist-style manual artifact without launching GUI.",
    )
    parser.add_argument(
        "--headless-notes",
        default="",
        help="Optional notes stored in headless checklist artifact.",
    )
    return parser.parse_args()


def main() -> int:
    """Run manual UI scenario list/run/batch flow."""
    args = _parse_args()
    repo_root = _repo_root()
    try:
        scenarios = load_scenario_registry((repo_root / args.registry).resolve())
    except ManualScenarioError as exc:
        print(f"ui-manual-runner: FAIL {exc}")
        return 1

    ordered = tuple(sorted(scenarios, key=lambda item: item.id))
    if args.list:
        for scenario in ordered:
            print(f"{scenario.id}\t{scenario.title}")
        return 0

    if not args.scenario and not args.batch:
        print("ui-manual-runner: provide --list, --scenario <id>, or --batch <id,...>")
        return 2

    selected_ids: list[str] = []
    if args.scenario:
        selected_ids.append(args.scenario.strip())
    if args.batch:
        selected_ids.extend(
            [item.strip() for item in args.batch.split(",") if item.strip()]
        )

    if not selected_ids:
        print("ui-manual-runner: no valid scenario IDs provided")
        return 2

    if args.auto_only and args.headless_result:
        print("ui-manual-runner: --auto-only cannot be combined with --headless-result")
        return 2

    results_dir = (repo_root / args.results_dir).resolve()
    exit_codes: list[int] = []
    for scenario_id in selected_ids:
        try:
            scenario = scenario_by_id(ordered, scenario_id)
        except ManualScenarioError as exc:
            print(f"ui-manual-runner: FAIL {exc}")
            return 1
        print(f"ui-manual-runner: running {scenario.id}")
        rc = _run_one_scenario(
            scenario=scenario,
            repo_root=repo_root,
            results_dir=results_dir,
            auto=bool(args.auto),
            auto_only=bool(args.auto_only),
            headless_result=(str(args.headless_result).strip() or None),
            headless_notes=str(args.headless_notes),
        )
        exit_codes.append(rc)

    non_zero = [code for code in exit_codes if code != 0]
    if non_zero:
        print(f"ui-manual-runner: FAIL non-zero run codes: {non_zero}")
        return non_zero[-1]
    print("ui-manual-runner: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
