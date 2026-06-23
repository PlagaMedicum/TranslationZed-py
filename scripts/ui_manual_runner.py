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
    SCENARIO_ENV_RUN_TOKEN,
    SCENARIO_REGISTRY_DEFAULT,
    SCENARIO_REGISTRY_VERSION,
    ManualScenario,
    ManualScenarioError,
    ManualScenarioRuntime,
    compute_tracked_file_hashes,
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
    run_token: str,
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env[SCENARIO_ENV_FILE] = str(runtime_payload_path)
    env[SCENARIO_ENV_RESULTS_DIR] = str(results_dir.resolve())
    env[SCENARIO_ENV_RUN_TOKEN] = run_token
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
    manual_outcome: str,
    manual_checklist_artifact: str | None,
    manual_checked_steps: list[str],
    manual_checked_expected_checks: list[str],
    manual_all_steps: list[str],
    manual_expected_checks: list[str],
    manual_notes: str,
    manual_run_token: str,
    tracked_files: list[dict[str, str]],
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
        "manual_outcome": manual_outcome,
        "manual_checklist_artifact": manual_checklist_artifact,
        "manual_checked_steps": list(manual_checked_steps),
        "manual_checked_expected_checks": list(manual_checked_expected_checks),
        "manual_all_steps": list(manual_all_steps),
        "manual_expected_checks": list(manual_expected_checks),
        "manual_notes": str(manual_notes).strip(),
        "manual_run_token": str(manual_run_token).strip(),
        "tracked_files": list(tracked_files),
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
    run_token: str,
) -> Path:
    results_dir.mkdir(parents=True, exist_ok=True)
    stamp_ms = int(time.time() * 1000)
    safe_id = runtime.scenario.id.replace("/", "_")
    safe_token = _safe_token(run_token)
    if safe_token:
        out_path = results_dir / f"{safe_id}-{safe_token}-{stamp_ms}.json"
    else:
        out_path = results_dir / f"{safe_id}-{stamp_ms}.json"
    payload: dict[str, Any] = {
        "version": runtime.version,
        "scenario_id": runtime.scenario.id,
        "title": runtime.scenario.title,
        "fixture_root": runtime.scenario.fixture_root,
        "project_root": runtime.project_root,
        "run_token": run_token,
        "result": result,
        "checked_steps": [],
        "checked_expected_checks": [],
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


def _scenario_checklist_artifacts(
    *, results_dir: Path, scenario: ManualScenario, run_token: str = ""
) -> list[Path]:
    safe_id = scenario.id.replace("/", "_")
    safe_token = _safe_token(run_token)
    pattern = f"{safe_id}-{safe_token}-*.json" if safe_token else f"{safe_id}-*.json"
    run_prefix = f"{safe_id}-run-"
    artifacts = [
        path
        for path in results_dir.glob(pattern)
        if not path.name.startswith(run_prefix)
    ]
    return sorted(artifacts)


def _safe_token(raw: str) -> str:
    return "".join(
        ch if (ch.isalnum() or ch in {"-", "_", "."}) else "_"
        for ch in str(raw).strip()
    ).strip("_")


def _manual_payload_lists(payload: dict[str, Any], field: str) -> list[str]:
    raw = payload.get(field)
    if not isinstance(raw, list):
        return []
    items: list[str] = []
    for item in raw:
        text = str(item).strip()
        if text:
            items.append(text)
    return items


def _manual_details_from_payload(
    *,
    payload: dict[str, Any],
    scenario: ManualScenario,
    run_token: str,
) -> dict[str, Any]:
    return {
        "manual_checked_steps": _manual_payload_lists(payload, "checked_steps"),
        "manual_checked_expected_checks": _manual_payload_lists(
            payload, "checked_expected_checks"
        ),
        "manual_all_steps": _manual_payload_lists(payload, "all_steps")
        or list(scenario.steps),
        "manual_expected_checks": _manual_payload_lists(payload, "expected_checks")
        or list(scenario.expected_checks),
        "manual_notes": str(payload.get("notes", "")).strip(),
        "manual_run_token": str(payload.get("run_token", run_token)).strip()
        or run_token,
    }


def _empty_manual_details(
    *, scenario: ManualScenario, run_token: str
) -> dict[str, Any]:
    return {
        "manual_checked_steps": [],
        "manual_checked_expected_checks": [],
        "manual_all_steps": list(scenario.steps),
        "manual_expected_checks": list(scenario.expected_checks),
        "manual_notes": "",
        "manual_run_token": run_token,
    }


def _resolve_manual_outcome(
    *,
    results_dir: Path,
    scenario: ManualScenario,
    run_token: str,
    run_started_ms: int,
) -> tuple[str, int, Path | None, dict[str, Any]]:
    for _ in range(40):
        artifacts = _scenario_checklist_artifacts(
            results_dir=results_dir,
            scenario=scenario,
            run_token=run_token,
        )
        if not artifacts:
            artifacts = _scenario_checklist_artifacts(
                results_dir=results_dir,
                scenario=scenario,
            )
        if not artifacts:
            time.sleep(0.05)
            continue
        for path in sorted(
            artifacts,
            key=lambda item: item.stat().st_mtime_ns,
            reverse=True,
        ):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(payload, dict):
                continue
            if str(payload.get("scenario_id", "")).strip() != scenario.id:
                continue
            payload_run_token = str(payload.get("run_token", "")).strip()
            completed_at_ms = payload.get("completed_at_ms")
            if payload_run_token and payload_run_token != run_token:
                continue
            if not payload_run_token:
                if not isinstance(completed_at_ms, int):
                    continue
                if completed_at_ms < run_started_ms:
                    continue
            details = _manual_details_from_payload(
                payload=payload,
                scenario=scenario,
                run_token=run_token,
            )
            result = str(payload.get("result", "")).strip().lower()
            if result == "passed":
                return ("passed", 0, path, details)
            if result == "failed":
                return ("failed", 1, path, details)
            if result == "incomplete":
                return ("incomplete", 1, path, details)
            return ("invalid", 1, path, details)
        time.sleep(0.05)
    return (
        "incomplete",
        1,
        None,
        _empty_manual_details(scenario=scenario, run_token=run_token),
    )


def _manual_note_preview(note: str, *, max_chars: int = 160) -> str:
    single_line = " ".join(str(note).split()).strip()
    if not single_line:
        return "-"
    if len(single_line) <= max_chars:
        return single_line
    return f"{single_line[: max_chars - 3]}..."


def _print_manual_outcome_summary(
    *,
    scenario: ManualScenario,
    manual_outcome: str,
    manual_details: dict[str, Any],
    checklist_path: str | None,
) -> None:
    checked_steps = list(manual_details.get("manual_checked_steps", []))
    checked_expected = list(manual_details.get("manual_checked_expected_checks", []))
    all_steps = list(manual_details.get("manual_all_steps", []))
    all_expected = list(manual_details.get("manual_expected_checks", []))
    note = str(manual_details.get("manual_notes", "")).strip()
    print(
        "ui-manual-runner: scenario-result "
        f"id={scenario.id} "
        f"result={manual_outcome} "
        f"checked_steps={len(checked_steps)}/{len(all_steps)} "
        f"checked_expected={len(checked_expected)}/{len(all_expected)} "
        f"checklist={checklist_path or '-'} "
        f"note={_manual_note_preview(note)}"
    )


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
    run_started_ms = int(time.time() * 1000)
    with tempfile.TemporaryDirectory(prefix=f"tzp-manual-{scenario.id}-") as raw_temp:
        temp_root = Path(raw_temp)
        tracked_files = compute_tracked_file_hashes(
            repo_root=repo_root,
            tracked_repo_files=scenario.tracked_repo_files,
        )
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
        manual_outcome = "not-run"
        manual_checklist_artifact: str | None = None
        manual_details = _empty_manual_details(
            scenario=scenario,
            run_token=f"{scenario.id}-{int(time.time() * 1000)}",
        )
        run_token = str(manual_details["manual_run_token"])
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
                run_token=run_token,
            )
            print(f"ui-manual-runner: wrote headless checklist artifact {checklist}")
            manual_checklist_artifact = str(checklist)
            manual_outcome = str(headless_result).strip().lower()
            manual_details = _manual_details_from_payload(
                payload=json.loads(checklist.read_text(encoding="utf-8")),
                scenario=scenario,
                run_token=run_token,
            )
            manual_rc = 0 if manual_outcome == "passed" else 1
        elif not auto_only:
            manual_proc = _run_manual_app(
                project_root=project_root,
                runtime_payload_path=runtime_payload_path,
                scenario=scenario,
                results_dir=results_dir,
                run_token=run_token,
            )
            manual_rc = int(manual_proc.returncode)
            outcome, outcome_rc, checklist_path, resolved_details = (
                _resolve_manual_outcome(
                    results_dir=results_dir,
                    scenario=scenario,
                    run_token=run_token,
                    run_started_ms=run_started_ms,
                )
            )
            manual_outcome = outcome
            manual_details = dict(resolved_details)
            if checklist_path is not None:
                manual_checklist_artifact = str(checklist_path)
            if manual_rc == 0 and outcome_rc != 0:
                manual_rc = outcome_rc
        else:
            manual_outcome = "auto-only"

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
            manual_outcome=manual_outcome,
            manual_checklist_artifact=manual_checklist_artifact,
            manual_checked_steps=list(manual_details["manual_checked_steps"]),
            manual_checked_expected_checks=list(
                manual_details["manual_checked_expected_checks"]
            ),
            manual_all_steps=list(manual_details["manual_all_steps"]),
            manual_expected_checks=list(manual_details["manual_expected_checks"]),
            manual_notes=str(manual_details["manual_notes"]),
            manual_run_token=str(manual_details["manual_run_token"]),
            tracked_files=tracked_files,
            auto_rc=auto_rc,
            mode=mode,
        )
        _print_manual_outcome_summary(
            scenario=scenario,
            manual_outcome=manual_outcome,
            manual_details=manual_details,
            checklist_path=manual_checklist_artifact,
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
        try:
            rc = _run_one_scenario(
                scenario=scenario,
                repo_root=repo_root,
                results_dir=results_dir,
                auto=bool(args.auto),
                auto_only=bool(args.auto_only),
                headless_result=(str(args.headless_result).strip() or None),
                headless_notes=str(args.headless_notes),
            )
        except ManualScenarioError as exc:
            print(f"ui-manual-runner: FAIL {exc}")
            return 1
        exit_codes.append(rc)

    non_zero = [code for code in exit_codes if code != 0]
    if non_zero:
        print(f"ui-manual-runner: FAIL non-zero run codes: {non_zero}")
        return non_zero[-1]
    print("ui-manual-runner: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
