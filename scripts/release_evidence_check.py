#!/usr/bin/env python3
"""Validate tracked manual release-evidence manifest contracts."""

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
)

MANIFEST_DEFAULT = "tests/manual_scenarios/release_evidence_manifest.json"
ALLOWED_INTERACTIVE_MODES = frozenset({"manual", "manual+auto"})


class ReleaseEvidenceError(ValueError):
    """Raised when release-evidence payloads violate required contracts."""


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ReleaseEvidenceError(f"missing JSON file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ReleaseEvidenceError(f"invalid JSON file {path}: {exc}") from exc


def _resolve_repo_path(repo_root: Path, rel_path: Any, *, field: str) -> Path:
    if not isinstance(rel_path, str) or not rel_path.strip():
        raise ReleaseEvidenceError(f"{field} must be a non-empty string path")
    candidate = (repo_root / rel_path.strip()).resolve()
    try:
        candidate.relative_to(repo_root)
    except ValueError as exc:
        raise ReleaseEvidenceError(
            f"{field} must stay under repo root: {rel_path}"
        ) from exc
    return candidate


def _load_required_scenarios(
    *, repo_root: Path, registry_path: Path
) -> tuple[ManualScenario, ...]:
    try:
        return load_scenario_registry(registry_path)
    except ManualScenarioError as exc:
        raise ReleaseEvidenceError(str(exc)) from exc


def _validate_checklist_payload(
    payload: Any, *, scenario_id: str, source_path: Path
) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return [f"{source_path}: checklist payload must be an object"]
    if payload.get("scenario_id") != scenario_id:
        errors.append(
            f"{source_path}: checklist scenario_id mismatch "
            f"(expected {scenario_id!r}, got {payload.get('scenario_id')!r})"
        )
    if payload.get("result") != "passed":
        errors.append(
            f"{source_path}: checklist result must be 'passed' "
            f"(got {payload.get('result')!r})"
        )
    if bool(payload.get("headless", False)):
        errors.append(
            f"{source_path}: checklist evidence must be interactive (headless=false)"
        )
    checked_steps = payload.get("checked_steps")
    if not isinstance(checked_steps, list):
        errors.append(f"{source_path}: checklist must provide list `checked_steps`")
    all_steps = payload.get("all_steps")
    if not isinstance(all_steps, list) or not all_steps:
        errors.append(
            f"{source_path}: checklist must provide non-empty list `all_steps`"
        )
    expected_checks = payload.get("expected_checks")
    if not isinstance(expected_checks, list) or not expected_checks:
        errors.append(
            f"{source_path}: checklist must provide non-empty list `expected_checks`"
        )
    checked_expected_checks = payload.get("checked_expected_checks")
    if not isinstance(checked_expected_checks, list):
        errors.append(
            f"{source_path}: checklist must provide list `checked_expected_checks`"
        )
    completed = payload.get("completed_at_ms")
    if not isinstance(completed, int) or completed <= 0:
        errors.append(
            f"{source_path}: checklist completed_at_ms must be positive integer"
        )
    if payload.get("result") == "passed":
        if isinstance(all_steps, list) and isinstance(checked_steps, list):
            required_steps = {
                str(item).strip()
                for item in all_steps
                if isinstance(item, str) and str(item).strip()
            }
            done_steps = {
                str(item).strip()
                for item in checked_steps
                if isinstance(item, str) and str(item).strip()
            }
            if required_steps - done_steps:
                errors.append(
                    f"{source_path}: passed checklist must tick all manual steps"
                )
        if isinstance(expected_checks, list) and isinstance(
            checked_expected_checks, list
        ):
            required_checks = {
                str(item).strip()
                for item in expected_checks
                if isinstance(item, str) and str(item).strip()
            }
            done_checks = {
                str(item).strip()
                for item in checked_expected_checks
                if isinstance(item, str) and str(item).strip()
            }
            if required_checks - done_checks:
                errors.append(
                    f"{source_path}: passed checklist must tick all expected outcomes"
                )
    return errors


def _validate_tracked_files(
    *,
    payload: dict[str, Any],
    scenario: ManualScenario,
    repo_root: Path,
    source_path: Path,
) -> list[str]:
    errors: list[str] = []
    tracked_rows = payload.get("tracked_files")
    if not isinstance(tracked_rows, list) or not tracked_rows:
        return [
            f"{source_path}: run payload must include non-empty list `tracked_files`"
        ]

    recorded: dict[str, str] = {}
    for idx, row in enumerate(tracked_rows):
        if not isinstance(row, dict):
            errors.append(f"{source_path}: tracked_files[{idx}] must be an object")
            continue
        path = str(row.get("path", "")).strip()
        sha256 = str(row.get("sha256", "")).strip().lower()
        if not path:
            errors.append(f"{source_path}: tracked_files[{idx}].path must be non-empty")
            continue
        if len(sha256) != 64 or any(ch not in "0123456789abcdef" for ch in sha256):
            errors.append(
                f"{source_path}: tracked_files[{idx}].sha256 must be 64-char lowercase hex"
            )
            continue
        if path in recorded:
            errors.append(f"{source_path}: tracked_files has duplicate path: {path}")
            continue
        recorded[path] = sha256

    try:
        current_rows = compute_tracked_file_hashes(
            repo_root=repo_root,
            tracked_repo_files=scenario.tracked_repo_files,
        )
    except ManualScenarioError as exc:
        errors.append(f"{source_path}: unable to hash scenario tracked files: {exc}")
        return errors

    current = {str(row["path"]): str(row["sha256"]) for row in current_rows}
    missing_paths = sorted(set(current) - set(recorded))
    extra_paths = sorted(set(recorded) - set(current))
    for path in missing_paths:
        errors.append(
            f"{source_path}: missing tracked hash row for {path}; "
            f"rerun `make ui-manual-run SCENARIO={scenario.id}` and "
            f"`make release-evidence-sync SCENARIO={scenario.id}`"
        )
    for path in extra_paths:
        errors.append(
            f"{source_path}: unexpected tracked hash row {path}; "
            f"rerun `make ui-manual-run SCENARIO={scenario.id}` and "
            f"`make release-evidence-sync SCENARIO={scenario.id}`"
        )
    for path, current_sha in current.items():
        recorded_sha = recorded.get(path)
        if recorded_sha is None:
            continue
        if recorded_sha != current_sha:
            errors.append(
                f"{source_path}: stale tracked hash for {path}; "
                f"rerun `make ui-manual-run SCENARIO={scenario.id}` and "
                f"`make release-evidence-sync SCENARIO={scenario.id}`"
            )
    return errors


def _validate_run_payload(
    payload: Any,
    *,
    scenario: ManualScenario,
    repo_root: Path,
    source_path: Path,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return [f"{source_path}: run payload must be an object"]
    scenario_payload = payload.get("scenario")
    run_scenario_id = None
    if isinstance(scenario_payload, dict):
        run_scenario_id = scenario_payload.get("id")
    if run_scenario_id != scenario.id:
        errors.append(
            f"{source_path}: run scenario.id mismatch "
            f"(expected {scenario.id!r}, got {run_scenario_id!r})"
        )
    elif scenario_payload != scenario.to_payload():
        errors.append(
            f"{source_path}: run scenario payload no longer matches the registry; "
            f"rerun `make ui-manual-run SCENARIO={scenario.id}` and "
            f"`make release-evidence-sync SCENARIO={scenario.id}`"
        )
    mode = payload.get("mode")
    if mode not in ALLOWED_INTERACTIVE_MODES:
        errors.append(
            f"{source_path}: run mode must be one of {sorted(ALLOWED_INTERACTIVE_MODES)} "
            f"(got {mode!r})"
        )
    if payload.get("manual_return_code") != 0:
        errors.append(f"{source_path}: run manual_return_code must equal 0")
    auto_rc = payload.get("auto_return_code")
    if auto_rc not in (None, 0):
        errors.append(f"{source_path}: run auto_return_code must be null or 0")
    completed = payload.get("completed_at_ms")
    if not isinstance(completed, int) or completed <= 0:
        errors.append(f"{source_path}: run completed_at_ms must be positive integer")
    errors.extend(
        _validate_tracked_files(
            payload=payload,
            scenario=scenario,
            repo_root=repo_root,
            source_path=source_path,
        )
    )
    return errors


def validate_release_evidence_manifest(
    *, repo_root: Path, manifest_path: Path, registry_path: Path
) -> list[str]:
    """Return release-evidence contract violations for the provided manifest."""
    errors: list[str] = []
    try:
        payload = _load_json(manifest_path)
    except ReleaseEvidenceError as exc:
        return [str(exc)]

    try:
        required_scenarios = _load_required_scenarios(
            repo_root=repo_root,
            registry_path=registry_path,
        )
    except ReleaseEvidenceError as exc:
        return [str(exc)]

    required_ids = [item.id for item in required_scenarios]
    by_required_id = {item.id: item for item in required_scenarios}

    if not isinstance(payload, dict):
        return [f"{manifest_path}: manifest root must be an object"]
    if payload.get("version") != 1:
        errors.append(f"{manifest_path}: `version` must equal 1")

    required = payload.get("required_scenarios")
    if not isinstance(required, list) or not all(
        isinstance(item, str) for item in required
    ):
        errors.append(
            f"{manifest_path}: `required_scenarios` must be a list of strings"
        )
    else:
        normalized_required = [item.strip() for item in required]
        if normalized_required != required_ids:
            errors.append(
                f"{manifest_path}: `required_scenarios` must match "
                f"scenario registry ids: {required_ids!r}"
            )

    entries = payload.get("entries")
    if not isinstance(entries, list):
        return errors + [f"{manifest_path}: `entries` must be a list"]

    by_scenario: dict[str, dict[str, Any]] = {}
    for idx, row in enumerate(entries):
        if not isinstance(row, dict):
            errors.append(f"{manifest_path}: entries[{idx}] must be an object")
            continue
        scenario_id = row.get("scenario_id")
        if not isinstance(scenario_id, str) or not scenario_id.strip():
            errors.append(
                f"{manifest_path}: entries[{idx}].scenario_id must be non-empty"
            )
            continue
        scenario_id = scenario_id.strip()
        if scenario_id in by_scenario:
            errors.append(
                f"{manifest_path}: duplicate entry for scenario {scenario_id!r}"
            )
            continue
        by_scenario[scenario_id] = row

    for scenario_id in required_ids:
        scenario = by_required_id[scenario_id]
        if scenario_id not in by_scenario:
            errors.append(
                f"{manifest_path}: missing required scenario evidence entry: {scenario_id}"
            )
            continue
        row = by_scenario[scenario_id]
        if row.get("result") != "passed":
            errors.append(
                f"{manifest_path}: scenario {scenario_id!r} must have result='passed'"
            )
        if row.get("interactive") is not True:
            errors.append(
                f"{manifest_path}: scenario {scenario_id!r} must set interactive=true"
            )

        try:
            checklist_path = _resolve_repo_path(
                repo_root,
                row.get("checklist_record"),
                field=f"entries[{scenario_id}].checklist_record",
            )
        except ReleaseEvidenceError as exc:
            errors.append(str(exc))
            checklist_path = None
        try:
            run_path = _resolve_repo_path(
                repo_root,
                row.get("run_record"),
                field=f"entries[{scenario_id}].run_record",
            )
        except ReleaseEvidenceError as exc:
            errors.append(str(exc))
            run_path = None

        for field_name in ("source_checklist_artifact", "source_run_artifact"):
            value = row.get(field_name)
            if not isinstance(value, str) or not value.strip():
                errors.append(
                    f"{manifest_path}: scenario {scenario_id!r} "
                    f"must provide non-empty {field_name!r}"
                )

        if checklist_path is not None:
            try:
                checklist_payload = _load_json(checklist_path)
            except ReleaseEvidenceError as exc:
                errors.append(str(exc))
            else:
                errors.extend(
                    _validate_checklist_payload(
                        checklist_payload,
                        scenario_id=scenario_id,
                        source_path=checklist_path,
                    )
                )
        if run_path is not None:
            try:
                run_payload = _load_json(run_path)
            except ReleaseEvidenceError as exc:
                errors.append(str(exc))
            else:
                errors.extend(
                    _validate_run_payload(
                        run_payload,
                        scenario=scenario,
                        repo_root=repo_root,
                        source_path=run_path,
                    )
                )

    return errors


def build_release_evidence_summary(
    *,
    repo_root: Path,
    manifest_path: Path,
    registry_path: Path,
) -> dict[str, Any]:
    """Return structured release-evidence summary for CLI/report consumers."""
    try:
        scenarios = load_scenario_registry(registry_path)
        required_ids = [scenario.id for scenario in scenarios]
    except ManualScenarioError:
        required_ids = []
    errors = validate_release_evidence_manifest(
        repo_root=repo_root,
        manifest_path=manifest_path,
        registry_path=registry_path,
    )
    return {
        "version": 1,
        "manifest": str(manifest_path),
        "registry": str(registry_path),
        "required_scenarios": required_ids,
        "error_count": len(errors),
        "errors": errors,
        "status": "failed" if errors else "passed",
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    """Run release-evidence checker CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        default=MANIFEST_DEFAULT,
        help="Tracked release-evidence manifest path.",
    )
    parser.add_argument(
        "--registry",
        default=SCENARIO_REGISTRY_DEFAULT,
        help="Manual scenario registry used to resolve required scenario ids.",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root used for path resolution.",
    )
    parser.add_argument(
        "--json-out",
        default="",
        help="Optional JSON summary output path.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print full structured summary after human-readable output.",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    summary = build_release_evidence_summary(
        repo_root=repo_root,
        manifest_path=(repo_root / args.manifest).resolve(),
        registry_path=(repo_root / args.registry).resolve(),
    )
    if args.json_out:
        _write_json(Path(args.json_out).resolve(), summary)
    if summary["errors"]:
        print("release-evidence-check: FAIL")
        for err in summary["errors"]:
            print(f" - {err}")
        if args.verbose:
            print(json.dumps(summary, indent=2, sort_keys=True))
        return 1
    print("release-evidence-check: PASS")
    print(f"validated manifest: {args.manifest}")
    if args.verbose:
        print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
