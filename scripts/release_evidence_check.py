#!/usr/bin/env python3
"""Validate tracked manual release-evidence manifest contracts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

MANIFEST_DEFAULT = "tests/manual_scenarios/release_evidence_manifest.json"
REQUIRED_SCENARIOS = (
    "status-triage-mixed-indicator",
    "search-replace-sidebar-all-scopes",
)
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
    if not isinstance(payload.get("checked_steps"), list):
        errors.append(f"{source_path}: checklist must provide list `checked_steps`")
    if not isinstance(payload.get("all_steps"), list) or not payload.get("all_steps"):
        errors.append(
            f"{source_path}: checklist must provide non-empty list `all_steps`"
        )
    if not isinstance(payload.get("expected_checks"), list) or not payload.get(
        "expected_checks"
    ):
        errors.append(
            f"{source_path}: checklist must provide non-empty list `expected_checks`"
        )
    completed = payload.get("completed_at_ms")
    if not isinstance(completed, int) or completed <= 0:
        errors.append(
            f"{source_path}: checklist completed_at_ms must be positive integer"
        )
    return errors


def _validate_run_payload(
    payload: Any, *, scenario_id: str, source_path: Path
) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return [f"{source_path}: run payload must be an object"]
    scenario = payload.get("scenario")
    run_scenario_id = None
    if isinstance(scenario, dict):
        run_scenario_id = scenario.get("id")
    if run_scenario_id != scenario_id:
        errors.append(
            f"{source_path}: run scenario.id mismatch "
            f"(expected {scenario_id!r}, got {run_scenario_id!r})"
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
    return errors


def validate_release_evidence_manifest(
    *, repo_root: Path, manifest_path: Path
) -> list[str]:
    """Return release-evidence contract violations for the provided manifest."""
    errors: list[str] = []
    try:
        payload = _load_json(manifest_path)
    except ReleaseEvidenceError as exc:
        return [str(exc)]

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
        if tuple(required) != REQUIRED_SCENARIOS:
            errors.append(
                f"{manifest_path}: `required_scenarios` must equal {list(REQUIRED_SCENARIOS)!r}"
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

    for scenario_id in REQUIRED_SCENARIOS:
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
                        scenario_id=scenario_id,
                        source_path=run_path,
                    )
                )
    return errors


def main() -> int:
    """Run release-evidence checker CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        default=MANIFEST_DEFAULT,
        help="Tracked release-evidence manifest path.",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root used for path resolution.",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    errors = validate_release_evidence_manifest(
        repo_root=repo_root,
        manifest_path=(repo_root / args.manifest).resolve(),
    )
    if errors:
        print("release-evidence-check: FAIL")
        for err in errors:
            print(f" - {err}")
        return 1
    print("release-evidence-check: PASS")
    print(f"validated manifest: {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
