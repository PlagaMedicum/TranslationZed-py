#!/usr/bin/env python3
"""Validate docs/reference/review_queue.json contract."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

ALLOWED_STATUS = {"REVIEW_REQUIRED", "IN_REFACTOR", "CLOSED"}
ALLOWED_RISK = {"P0", "P1", "P2"}
ALLOWED_REASON_CODES = {
    "ARCH_BOUNDARY",
    "COMPLEXITY",
    "STATE_INCOHERENCE",
    "DUPLICATION",
    "ERROR_HANDLING",
    "TEST_GAP",
    "PERF_SMELL",
    "DOC_DRIFT",
}
REQUIRED_KEYS = {
    "module_path",
    "status",
    "risk_level",
    "reason_codes",
    "evidence",
    "refactor_scope",
    "required_tests",
    "owner",
    "opened_at",
    "closure_criteria",
    "closed_at",
}


def _is_iso_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _validate_entry(entry: Any, idx: int) -> list[str]:
    errors: list[str] = []
    if not isinstance(entry, dict):
        return [f"entry[{idx}] must be an object"]
    missing = sorted(REQUIRED_KEYS - set(entry))
    if missing:
        errors.append(f"entry[{idx}] missing required keys: {', '.join(missing)}")
        return errors

    module_path = entry["module_path"]
    if not isinstance(module_path, str) or not module_path.endswith(".py"):
        errors.append(f"entry[{idx}].module_path must be a python file path")

    status = entry["status"]
    if status not in ALLOWED_STATUS:
        errors.append(
            f"entry[{idx}].status must be one of: {', '.join(sorted(ALLOWED_STATUS))}"
        )

    risk = entry["risk_level"]
    if risk not in ALLOWED_RISK:
        errors.append(
            f"entry[{idx}].risk_level must be one of: {', '.join(sorted(ALLOWED_RISK))}"
        )

    reason_codes = entry["reason_codes"]
    if (
        not isinstance(reason_codes, list)
        or not reason_codes
        or any(code not in ALLOWED_REASON_CODES for code in reason_codes)
    ):
        errors.append(
            f"entry[{idx}].reason_codes must be a non-empty list of allowed codes"
        )

    evidence = entry["evidence"]
    if (
        not isinstance(evidence, list)
        or not evidence
        or any(not isinstance(item, str) or not item.strip() for item in evidence)
    ):
        errors.append(f"entry[{idx}].evidence must be a non-empty list of strings")

    required_tests = entry["required_tests"]
    if (
        not isinstance(required_tests, list)
        or not required_tests
        or any(not isinstance(item, str) or not item.strip() for item in required_tests)
    ):
        errors.append(
            f"entry[{idx}].required_tests must be a non-empty list of strings"
        )

    owner = entry["owner"]
    if not isinstance(owner, str) or not owner.strip():
        errors.append(f"entry[{idx}].owner must be a non-empty string")

    opened_at = entry["opened_at"]
    if not isinstance(opened_at, str) or not _is_iso_date(opened_at):
        errors.append(f"entry[{idx}].opened_at must be an ISO date (YYYY-MM-DD)")

    closure_criteria = entry["closure_criteria"]
    if (
        not isinstance(closure_criteria, list)
        or not closure_criteria
        or any(
            not isinstance(item, str) or not item.strip() for item in closure_criteria
        )
    ):
        errors.append(
            f"entry[{idx}].closure_criteria must be a non-empty list of strings"
        )

    closed_at = entry["closed_at"]
    if status == "CLOSED":
        if not isinstance(closed_at, str) or not _is_iso_date(closed_at):
            errors.append(
                f"entry[{idx}].closed_at must be an ISO date when status=CLOSED"
            )
        elif (
            isinstance(opened_at, str)
            and _is_iso_date(opened_at)
            and (date.fromisoformat(closed_at) < date.fromisoformat(opened_at))
        ):
            errors.append(
                f"entry[{idx}].closed_at must be >= opened_at when status=CLOSED"
            )
    else:
        if closed_at is not None:
            errors.append(f"entry[{idx}].closed_at must be null unless status=CLOSED")

    return errors


def validate_queue(path: Path, *, repo_root: Path | None = None) -> list[str]:
    """Return validation errors for a review queue JSON file."""
    errors: list[str] = []
    if not path.is_file():
        return [f"missing review queue file: {path}"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"invalid JSON: {path}: {exc}"]

    if not isinstance(payload, dict):
        return [f"queue root must be an object: {path}"]

    version = payload.get("version")
    if not isinstance(version, int) or version <= 0:
        errors.append("queue root requires positive integer `version`")

    entries = payload.get("entries")
    if not isinstance(entries, list):
        return errors + ["queue root requires list `entries`"]

    active_statuses = {"REVIEW_REQUIRED", "IN_REFACTOR"}
    active_modules: dict[str, int] = {}
    for idx, entry in enumerate(entries):
        errors.extend(_validate_entry(entry, idx))
        if not isinstance(entry, dict):
            continue
        module_path = entry.get("module_path")
        status = entry.get("status")
        if isinstance(module_path, str) and isinstance(status, str):
            if repo_root is not None and not (repo_root / module_path).is_file():
                errors.append(
                    f"entry[{idx}].module_path does not exist in repo: {module_path}"
                )
            required_tests = entry.get("required_tests")
            if repo_root is not None and isinstance(required_tests, list):
                for test_path in required_tests:
                    if (
                        isinstance(test_path, str)
                        and test_path.strip()
                        and not (repo_root / test_path).is_file()
                    ):
                        errors.append(
                            f"entry[{idx}].required_tests path missing in repo: {test_path}"
                        )
            if status in active_statuses:
                if module_path in active_modules:
                    errors.append(
                        "duplicate active queue entry for module_path: "
                        f"{module_path} (entries {active_modules[module_path]} and {idx})"
                    )
                active_modules[module_path] = idx

    return errors


def main() -> int:
    """Run queue schema checks and return process exit code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--queue",
        default="docs/reference/review_queue.json",
        help="Path to review queue JSON artifact",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repo root used for module/test path existence checks",
    )
    args = parser.parse_args()
    queue_path = Path(args.queue)
    repo_root = Path(args.repo_root).resolve()

    errors = validate_queue(queue_path, repo_root=repo_root)
    if errors:
        print("review-queue-check: FAIL")
        for err in errors:
            print(f" - {err}")
        return 1

    print("review-queue-check: PASS")
    print(f"validated queue: {queue_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
