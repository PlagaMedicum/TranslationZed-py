#!/usr/bin/env python3
"""Prune deprecated manual UI artifact payloads under artifacts/manual-ui."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REQUIRED_RUN_FIELDS = frozenset(
    {
        "manual_outcome",
        "manual_checklist_artifact",
        "manual_checked_steps",
        "manual_checked_expected_checks",
        "manual_all_steps",
        "manual_expected_checks",
        "manual_notes",
        "manual_run_token",
    }
)
REQUIRED_CHECKLIST_FIELDS = frozenset(
    {
        "scenario_id",
        "result",
        "checked_steps",
        "checked_expected_checks",
        "all_steps",
        "expected_checks",
        "notes",
        "completed_at_ms",
        "run_token",
    }
)


def _is_json_object(payload: Any) -> bool:
    return isinstance(payload, dict)


def _is_deprecated_run_payload(payload: Any) -> bool:
    if not _is_json_object(payload):
        return True
    return any(field not in payload for field in REQUIRED_RUN_FIELDS)


def _is_deprecated_checklist_payload(payload: Any) -> bool:
    if not _is_json_object(payload):
        return True
    return any(field not in payload for field in REQUIRED_CHECKLIST_FIELDS)


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def main() -> int:
    """Run cleanup CLI for deprecated manual artifacts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifacts-dir",
        default="artifacts/manual-ui",
        help="Manual artifacts directory to scan.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List deprecated files without deleting them.",
    )
    args = parser.parse_args()

    artifacts_dir = Path(args.artifacts_dir).resolve()
    if not artifacts_dir.exists():
        print(f"clean-manual-artifacts: no directory at {artifacts_dir}")
        return 0
    if not artifacts_dir.is_dir():
        print(f"clean-manual-artifacts: not a directory: {artifacts_dir}")
        return 2

    removed = 0
    deprecated_count = 0
    scanned = 0
    for path in sorted(artifacts_dir.glob("*.json")):
        scanned += 1
        payload = _load_json(path)
        is_run = "-run-" in path.name
        deprecated = (
            _is_deprecated_run_payload(payload)
            if is_run
            else _is_deprecated_checklist_payload(payload)
        )
        if not deprecated:
            continue
        deprecated_count += 1
        if args.dry_run:
            print(f"clean-manual-artifacts: deprecated {path}")
            continue
        path.unlink(missing_ok=True)
        removed += 1
        print(f"clean-manual-artifacts: removed {path}")

    kept = scanned - removed
    if args.dry_run:
        print(
            f"clean-manual-artifacts: scanned={scanned} deprecated_listed={deprecated_count}"
        )
    else:
        print(
            f"clean-manual-artifacts: scanned={scanned} removed={removed} kept={kept}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
