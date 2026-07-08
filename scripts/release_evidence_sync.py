#!/usr/bin/env python3
"""Sync tracked release-evidence records from manual run artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from translationzed_py.gui.manual_scenario_runtime import (
    SCENARIO_REGISTRY_DEFAULT,
    ManualScenario,
    ManualScenarioError,
    compute_tracked_file_hashes,
    load_scenario_registry,
    scenario_by_id,
)

MANIFEST_DEFAULT = "tests/manual_scenarios/release_evidence_manifest.json"
RELEASE_DIR_DEFAULT = "tests/manual_scenarios/release_evidence"
RESULTS_DIR_DEFAULT = "artifacts/manual-ui"
ALLOWED_INTERACTIVE_MODES = frozenset({"manual", "manual+auto"})
SCENARIO_METADATA_COMPAT_FIELDS = frozenset(
    {"tracked_repo_files", "automation_pytest_selectors"}
)


class ReleaseEvidenceSyncError(ValueError):
    """Raised when release-evidence sync input artifacts are invalid."""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _safe_id(scenario_id: str) -> str:
    return scenario_id.replace("/", "_")


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ReleaseEvidenceSyncError(f"missing JSON file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ReleaseEvidenceSyncError(f"invalid JSON file {path}: {exc}") from exc


def _repo_relative_or_absolute(repo_root: Path, path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(repo_root).as_posix()
    except ValueError:
        return str(resolved)


def _checklist_artifacts_for_run(
    *, results_dir: Path, scenario: ManualScenario, run_token: str
) -> list[Path]:
    safe_id = _safe_id(scenario.id)
    pattern = f"{safe_id}-{run_token}-*.json" if run_token else f"{safe_id}-*.json"
    rows = [path for path in results_dir.glob(pattern) if "-run-" not in path.name]
    return sorted(rows, key=lambda item: item.stat().st_mtime_ns, reverse=True)


def _resolve_artifact_path(repo_root: Path, raw_path: str) -> Path:
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = (repo_root / candidate).resolve()
    else:
        candidate = candidate.resolve()
    return candidate


def _is_valid_tracked_files(rows: Any) -> bool:
    if not isinstance(rows, list) or not rows:
        return False
    seen: set[str] = set()
    for item in rows:
        if not isinstance(item, dict):
            return False
        path = str(item.get("path", "")).strip()
        sha256 = str(item.get("sha256", "")).strip().lower()
        if not path or not sha256:
            return False
        if len(sha256) != 64 or any(ch not in "0123456789abcdef" for ch in sha256):
            return False
        if path in seen:
            return False
        seen.add(path)
    return True


def _manual_workflow_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in payload.items()
        if key not in SCENARIO_METADATA_COMPAT_FIELDS
    }


def _scenario_payload_matches_manual_workflow(
    payload: Any, *, scenario: ManualScenario
) -> bool:
    if not isinstance(payload, dict):
        return False
    return _manual_workflow_payload(payload) == _manual_workflow_payload(
        scenario.to_payload()
    )


def _tracked_file_sync_error(
    *, repo_root: Path, scenario: ManualScenario, run_payload: dict[str, Any]
) -> str:
    tracked_rows = run_payload.get("tracked_files")
    if not _is_valid_tracked_files(tracked_rows):
        return "tracked file hashes missing or invalid"
    recorded = {
        str(row["path"]).strip(): str(row["sha256"]).strip().lower()
        for row in tracked_rows
    }
    try:
        current_rows = compute_tracked_file_hashes(
            repo_root=repo_root,
            tracked_repo_files=scenario.tracked_repo_files,
        )
    except ManualScenarioError as exc:
        return f"unable to hash scenario tracked files: {exc}"
    current = {str(row["path"]): str(row["sha256"]) for row in current_rows}
    missing_paths = sorted(set(current) - set(recorded))
    if missing_paths:
        return f"missing tracked hash row for {missing_paths[0]}"
    for path, current_sha in current.items():
        if recorded.get(path) != current_sha:
            return f"stale tracked hash for {path}"
    return ""


def _validate_checklist_payload(
    payload: Any, *, scenario: ManualScenario, run_token: str, source: Path
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ReleaseEvidenceSyncError(f"{source}: checklist payload must be an object")
    if str(payload.get("scenario_id", "")).strip() != scenario.id:
        raise ReleaseEvidenceSyncError(
            f"{source}: checklist scenario_id mismatch for {scenario.id!r}"
        )
    if str(payload.get("result", "")).strip().lower() != "passed":
        raise ReleaseEvidenceSyncError(
            f"{source}: checklist result must be 'passed' for sync"
        )
    if bool(payload.get("headless", False)):
        raise ReleaseEvidenceSyncError(f"{source}: checklist must be interactive")
    if run_token and str(payload.get("run_token", "")).strip() != run_token:
        raise ReleaseEvidenceSyncError(
            f"{source}: checklist run_token mismatch (expected {run_token!r})"
        )
    if not isinstance(payload.get("completed_at_ms"), int):
        raise ReleaseEvidenceSyncError(
            f"{source}: checklist completed_at_ms must be an integer"
        )
    return payload


def _checklist_candidates_for_run(
    *,
    repo_root: Path,
    results_dir: Path,
    scenario: ManualScenario,
    run_payload: dict[str, Any],
) -> tuple[str, list[Path]]:
    run_token = str(run_payload.get("manual_run_token", "")).strip()
    raw_checklist = str(run_payload.get("manual_checklist_artifact", "")).strip()
    candidates: list[Path] = []
    if raw_checklist:
        candidates.append(_resolve_artifact_path(repo_root, raw_checklist))
    candidates.extend(
        _checklist_artifacts_for_run(
            results_dir=results_dir,
            scenario=scenario,
            run_token=run_token,
        )
    )
    return run_token, candidates


def _reason_for_unsyncable_run(
    *,
    repo_root: Path,
    results_dir: Path,
    scenario: ManualScenario,
    run_path: Path,
    run_payload: Any,
) -> str:
    if not isinstance(run_payload, dict):
        return f"{run_path.name}: run payload must be an object"

    scenario_payload = run_payload.get("scenario")
    run_scenario_id = ""
    if isinstance(scenario_payload, dict):
        run_scenario_id = str(scenario_payload.get("id", "")).strip()
    if run_scenario_id != scenario.id:
        return f"{run_path.name}: scenario id mismatch"
    if not _scenario_payload_matches_manual_workflow(
        scenario_payload, scenario=scenario
    ):
        return f"{run_path.name}: scenario payload drift"

    manual_outcome = str(run_payload.get("manual_outcome", "")).strip().lower()
    if manual_outcome != "passed":
        return (
            f"{run_path.name}: latest local run outcome: {manual_outcome or 'unknown'}"
        )
    if run_payload.get("manual_return_code") != 0:
        return f"{run_path.name}: manual_return_code must equal 0"

    mode = str(run_payload.get("mode", "")).strip()
    if mode not in ALLOWED_INTERACTIVE_MODES:
        return f"{run_path.name}: interactive mode missing or invalid"
    tracked_error = _tracked_file_sync_error(
        repo_root=repo_root,
        scenario=scenario,
        run_payload=run_payload,
    )
    if tracked_error:
        return f"{run_path.name}: {tracked_error}"

    run_token, checklist_candidates = _checklist_candidates_for_run(
        repo_root=repo_root,
        results_dir=results_dir,
        scenario=scenario,
        run_payload=run_payload,
    )
    if not checklist_candidates:
        return f"{run_path.name}: missing checklist artifact"

    seen: set[Path] = set()
    first_checklist_error: str | None = None
    for checklist_path in checklist_candidates:
        if checklist_path in seen:
            continue
        seen.add(checklist_path)
        if not checklist_path.is_file():
            if first_checklist_error is None:
                first_checklist_error = (
                    f"{run_path.name}: missing checklist artifact {checklist_path}"
                )
            continue
        checklist_payload = _load_json(checklist_path)
        try:
            _validate_checklist_payload(
                checklist_payload,
                scenario=scenario,
                run_token=run_token,
                source=checklist_path,
            )
        except ReleaseEvidenceSyncError as exc:
            if first_checklist_error is None:
                first_checklist_error = str(exc)
            continue
        return ""
    return first_checklist_error or f"{run_path.name}: no syncable checklist artifact"


def preflight_release_evidence_sync(
    *,
    repo_root: Path,
    registry_path: Path,
    results_dir: Path,
    selected_scenarios: tuple[str, ...],
) -> list[dict[str, str]]:
    """Report which scenarios are syncable now and which still need reruns."""
    try:
        scenarios = load_scenario_registry(registry_path)
    except ManualScenarioError as exc:
        raise ReleaseEvidenceSyncError(str(exc)) from exc

    if selected_scenarios:
        selected_rows: list[ManualScenario] = []
        for scenario_id in selected_scenarios:
            try:
                selected_rows.append(scenario_by_id(scenarios, scenario_id))
            except ManualScenarioError as exc:
                raise ReleaseEvidenceSyncError(str(exc)) from exc
        selected = tuple(selected_rows)
    else:
        selected = tuple(scenarios)

    rows: list[dict[str, str]] = []
    for scenario in selected:
        run_pattern = f"{_safe_id(scenario.id)}-run-*.json"
        run_candidates = sorted(
            results_dir.glob(run_pattern),
            key=lambda item: item.stat().st_mtime_ns,
            reverse=True,
        )
        if not run_candidates:
            rows.append(
                {
                    "scenario_id": scenario.id,
                    "status": "rerun-needed",
                    "reason": "no local run artifacts found",
                }
            )
            continue

        latest_run = run_candidates[0]
        latest_payload = _load_json(latest_run)
        reason = _reason_for_unsyncable_run(
            repo_root=repo_root,
            results_dir=results_dir,
            scenario=scenario,
            run_path=latest_run,
            run_payload=latest_payload,
        )
        if not reason:
            rows.append(
                {
                    "scenario_id": scenario.id,
                    "status": "syncable",
                    "reason": (
                        f"syncable from {latest_run.relative_to(repo_root).as_posix()}"
                    ),
                }
            )
        else:
            rows.append(
                {
                    "scenario_id": scenario.id,
                    "status": "rerun-needed",
                    "reason": reason,
                }
            )
    return rows


def _resolve_run_and_checklist(
    *, repo_root: Path, results_dir: Path, scenario: ManualScenario
) -> tuple[Path, dict[str, Any], Path, dict[str, Any]]:
    run_pattern = f"{_safe_id(scenario.id)}-run-*.json"
    run_candidates = sorted(
        results_dir.glob(run_pattern),
        key=lambda item: item.stat().st_mtime_ns,
        reverse=True,
    )
    if not run_candidates:
        raise ReleaseEvidenceSyncError(
            f"no run artifacts found for scenario {scenario.id!r} in {results_dir}"
        )

    for run_path in run_candidates:
        run_payload = _load_json(run_path)
        if not isinstance(run_payload, dict):
            continue
        scenario_payload = run_payload.get("scenario")
        run_scenario_id = ""
        if isinstance(scenario_payload, dict):
            run_scenario_id = str(scenario_payload.get("id", "")).strip()
        if run_scenario_id != scenario.id:
            continue
        if not _scenario_payload_matches_manual_workflow(
            scenario_payload, scenario=scenario
        ):
            continue
        if str(run_payload.get("manual_outcome", "")).strip().lower() != "passed":
            continue
        if run_payload.get("manual_return_code") != 0:
            continue
        mode = str(run_payload.get("mode", "")).strip()
        if mode not in ALLOWED_INTERACTIVE_MODES:
            continue
        if _tracked_file_sync_error(
            repo_root=repo_root,
            scenario=scenario,
            run_payload=run_payload,
        ):
            continue

        run_token = str(run_payload.get("manual_run_token", "")).strip()
        raw_checklist = str(run_payload.get("manual_checklist_artifact", "")).strip()
        checklist_candidates: list[Path] = []
        if raw_checklist:
            checklist_candidates.append(
                _resolve_artifact_path(repo_root, raw_checklist)
            )
        checklist_candidates.extend(
            _checklist_artifacts_for_run(
                results_dir=results_dir,
                scenario=scenario,
                run_token=run_token,
            )
        )
        seen: set[Path] = set()
        for checklist_path in checklist_candidates:
            if checklist_path in seen:
                continue
            seen.add(checklist_path)
            if not checklist_path.is_file():
                continue
            checklist_payload = _load_json(checklist_path)
            try:
                valid_checklist = _validate_checklist_payload(
                    checklist_payload,
                    scenario=scenario,
                    run_token=run_token,
                    source=checklist_path,
                )
            except ReleaseEvidenceSyncError:
                continue
            return run_path, run_payload, checklist_path, valid_checklist

    raise ReleaseEvidenceSyncError(
        f"no syncable passed interactive run/checklist pair found for scenario {scenario.id!r}"
    )


def _load_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"version": 1, "required_scenarios": [], "entries": []}
    payload = _load_json(path)
    if not isinstance(payload, dict):
        raise ReleaseEvidenceSyncError(f"{path}: manifest root must be an object")
    return payload


def _dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def sync_release_evidence(
    *,
    repo_root: Path,
    registry_path: Path,
    manifest_path: Path,
    release_dir: Path,
    results_dir: Path,
    selected_scenarios: tuple[str, ...],
) -> tuple[list[str], list[str]]:
    """Sync selected scenario evidence into tracked release records."""
    try:
        scenarios = load_scenario_registry(registry_path)
    except ManualScenarioError as exc:
        raise ReleaseEvidenceSyncError(str(exc)) from exc

    required_ids = [item.id for item in scenarios]
    manifest = _load_manifest(manifest_path)
    entries_raw = manifest.get("entries", [])
    entries_map: dict[str, dict[str, Any]] = {}
    if isinstance(entries_raw, list):
        for row in entries_raw:
            if not isinstance(row, dict):
                continue
            scenario_id = str(row.get("scenario_id", "")).strip()
            if scenario_id:
                entries_map[scenario_id] = dict(row)

    selected: tuple[ManualScenario, ...]
    if selected_scenarios:
        selected_rows: list[ManualScenario] = []
        for scenario_id in selected_scenarios:
            try:
                selected_rows.append(scenario_by_id(scenarios, scenario_id))
            except ManualScenarioError as exc:
                raise ReleaseEvidenceSyncError(str(exc)) from exc
        selected = tuple(selected_rows)
    else:
        selected = tuple(scenarios)

    synced_ids: list[str] = []
    failures: list[str] = []
    pending_updates: dict[str, dict[str, Any]] = {}
    for scenario in selected:
        try:
            run_source, run_payload, checklist_source, checklist_payload = (
                _resolve_run_and_checklist(
                    repo_root=repo_root,
                    results_dir=results_dir,
                    scenario=scenario,
                )
            )
        except ReleaseEvidenceSyncError as exc:
            failures.append(str(exc))
            continue
        safe_id = _safe_id(scenario.id)
        checklist_record_path = release_dir / f"{safe_id}-checklist.json"
        run_record_path = release_dir / f"{safe_id}-run.json"
        pending_updates[scenario.id] = {
            "scenario": scenario,
            "run_source": run_source,
            "run_payload": run_payload,
            "checklist_source": checklist_source,
            "checklist_payload": checklist_payload,
            "checklist_record_path": checklist_record_path,
            "run_record_path": run_record_path,
        }
        synced_ids.append(scenario.id)

    if failures:
        return synced_ids, failures

    for row in pending_updates.values():
        _dump_json(row["checklist_record_path"], row["checklist_payload"])
        _dump_json(row["run_record_path"], row["run_payload"])
        scenario = row["scenario"]
        recorded_at = max(
            int(row["checklist_payload"].get("completed_at_ms", 0) or 0),
            int(row["run_payload"].get("completed_at_ms", 0) or 0),
        )
        existing = entries_map.get(scenario.id, {})
        notes = str(existing.get("notes", "")).strip() or (
            "Synced from artifacts/manual-ui via release-evidence-sync."
        )
        entries_map[scenario.id] = {
            "scenario_id": scenario.id,
            "result": "passed",
            "interactive": True,
            "recorded_at_ms": recorded_at,
            "checklist_record": _repo_relative_or_absolute(
                repo_root, row["checklist_record_path"]
            ),
            "run_record": _repo_relative_or_absolute(repo_root, row["run_record_path"]),
            "source_checklist_artifact": _repo_relative_or_absolute(
                repo_root, row["checklist_source"]
            ),
            "source_run_artifact": _repo_relative_or_absolute(
                repo_root, row["run_source"]
            ),
            "notes": notes,
        }

    manifest_payload: dict[str, Any] = {
        "version": 1,
        "required_scenarios": required_ids,
        "entries": [entries_map[item] for item in required_ids if item in entries_map],
    }
    _dump_json(manifest_path, manifest_payload)
    return synced_ids, []


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--registry",
        default=SCENARIO_REGISTRY_DEFAULT,
        help="Manual scenario registry JSON path.",
    )
    parser.add_argument(
        "--manifest",
        default=MANIFEST_DEFAULT,
        help="Tracked release-evidence manifest JSON path.",
    )
    parser.add_argument(
        "--release-dir",
        default=RELEASE_DIR_DEFAULT,
        help="Tracked release-evidence records directory.",
    )
    parser.add_argument(
        "--results-dir",
        default=RESULTS_DIR_DEFAULT,
        help="Manual run artifacts directory.",
    )
    parser.add_argument(
        "--scenario",
        default="",
        help="Sync one scenario id.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Sync all scenarios from the registry.",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root used for relative path resolution.",
    )
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="Report syncable vs rerun-needed scenarios without writing tracked records.",
    )
    return parser.parse_args()


def main() -> int:
    """Run release-evidence sync CLI."""
    args = _parse_args()
    if bool(args.scenario) == bool(args.all):
        print("release-evidence-sync: provide exactly one of --scenario or --all")
        return 2

    repo_root = Path(args.repo_root).resolve()
    selected = (str(args.scenario).strip(),) if args.scenario else ()
    if args.preflight:
        try:
            rows = preflight_release_evidence_sync(
                repo_root=repo_root,
                registry_path=(repo_root / args.registry).resolve(),
                results_dir=(repo_root / args.results_dir).resolve(),
                selected_scenarios=selected,
            )
        except ReleaseEvidenceSyncError as exc:
            print(f"release-evidence-sync: FAIL {exc}")
            return 1
        print("release-evidence-sync: PREFLIGHT")
        for row in rows:
            print(f" - {row['scenario_id']}: {row['status']} - {row['reason']}")
        return 0
    try:
        synced, failures = sync_release_evidence(
            repo_root=repo_root,
            registry_path=(repo_root / args.registry).resolve(),
            manifest_path=(repo_root / args.manifest).resolve(),
            release_dir=(repo_root / args.release_dir).resolve(),
            results_dir=(repo_root / args.results_dir).resolve(),
            selected_scenarios=selected,
        )
    except ReleaseEvidenceSyncError as exc:
        print(f"release-evidence-sync: FAIL {exc}")
        return 1

    if failures:
        print("release-evidence-sync: FAIL")
        for msg in failures:
            print(f" - {msg}")
        return 1

    print("release-evidence-sync: PASS")
    if synced:
        print(f"synced scenarios: {', '.join(synced)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
