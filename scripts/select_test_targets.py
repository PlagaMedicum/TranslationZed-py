#!/usr/bin/env python3
"""Resolve changed-file-aware packet test targets from a routing map."""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RoutingRule:
    """One changed-file routing rule for packet tests."""

    id: str
    description: str
    match_globs: tuple[str, ...]
    targets_fast: tuple[str, ...]
    targets_full: tuple[str, ...]


@dataclass(frozen=True)
class RoutingMap:
    """Parsed routing map contract payload."""

    version: int
    default_fast_targets: tuple[str, ...]
    full_targets: tuple[str, ...]
    rules: tuple[RoutingRule, ...]


class RoutingMapError(ValueError):
    """Raised when routing map payload is invalid."""


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RoutingMapError(f"missing routing map: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RoutingMapError(f"invalid routing map JSON: {path}: {exc}") from exc


def _require_str_list(
    payload: Any, *, field: str, allow_empty: bool = False
) -> tuple[str, ...]:
    if not isinstance(payload, list):
        raise RoutingMapError(f"{field} must be a string list")
    if not payload and allow_empty:
        return ()
    if not payload or not all(
        isinstance(item, str) and item.strip() for item in payload
    ):
        raise RoutingMapError(f"{field} must be a non-empty-string list")
    return tuple(item.strip() for item in payload)


def load_routing_map(path: Path) -> RoutingMap:
    """Load and validate routing map JSON payload."""
    payload = _load_json(path)
    if not isinstance(payload, dict):
        raise RoutingMapError("routing map root must be an object")
    version = payload.get("version")
    if version != 1:
        raise RoutingMapError("routing map version must equal 1")

    default_fast = _require_str_list(
        payload.get("default_fast_targets", []),
        field="default_fast_targets",
        allow_empty=True,
    )
    full_targets = _require_str_list(
        payload.get("full_targets", []), field="full_targets"
    )

    raw_rules = payload.get("rules")
    if not isinstance(raw_rules, list):
        raise RoutingMapError("rules must be a list")

    rules: list[RoutingRule] = []
    seen_ids: set[str] = set()
    for idx, row in enumerate(raw_rules):
        if not isinstance(row, dict):
            raise RoutingMapError(f"rules[{idx}] must be an object")
        rule_id = row.get("id")
        if not isinstance(rule_id, str) or not rule_id.strip():
            raise RoutingMapError(f"rules[{idx}].id must be a non-empty string")
        rule_id = rule_id.strip()
        if rule_id in seen_ids:
            raise RoutingMapError(f"duplicate rule id: {rule_id}")
        seen_ids.add(rule_id)

        description = row.get("description")
        if not isinstance(description, str) or not description.strip():
            raise RoutingMapError(
                f"rules[{idx}].description must be a non-empty string"
            )
        match_globs = _require_str_list(
            row.get("match_globs"), field=f"rules[{idx}].match_globs"
        )
        targets_fast = _require_str_list(
            row.get("targets_fast"), field=f"rules[{idx}].targets_fast"
        )
        targets_full = _require_str_list(
            row.get("targets_full"), field=f"rules[{idx}].targets_full"
        )

        rules.append(
            RoutingRule(
                id=rule_id,
                description=description.strip(),
                match_globs=match_globs,
                targets_fast=targets_fast,
                targets_full=targets_full,
            )
        )

    return RoutingMap(
        version=version,
        default_fast_targets=default_fast,
        full_targets=full_targets,
        rules=tuple(rules),
    )


def _git_changed_paths(repo_root: Path) -> list[str]:
    commands = [
        ["git", "diff", "--name-only", "--diff-filter=ACMRTUXB"],
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMRTUXB"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    ]
    collected: set[str] = set()
    for cmd in commands:
        proc = subprocess.run(
            cmd,
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            continue
        for raw in proc.stdout.splitlines():
            rel = raw.strip().replace("\\", "/")
            if rel:
                collected.add(rel)
    return sorted(collected)


def _dedupe(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def select_targets(
    *,
    routing_map: RoutingMap,
    changed_paths: list[str],
    mode: str,
) -> list[str]:
    """Return deduplicated packet targets for the requested selection mode."""
    if mode not in {"fast", "full"}:
        raise RoutingMapError(f"unsupported mode: {mode}")

    normalized = [
        path.replace("\\", "/").strip() for path in changed_paths if path.strip()
    ]

    if mode == "full":
        return _dedupe(list(routing_map.full_targets))

    selected: list[str] = list(routing_map.default_fast_targets)
    for rule in routing_map.rules:
        matched = any(
            any(fnmatch(path, pattern) for pattern in rule.match_globs)
            for path in normalized
        )
        if matched:
            selected.extend(rule.targets_fast)
    return _dedupe(selected)


def _print_targets(targets: list[str], *, fmt: str) -> None:
    if fmt == "json":
        print(
            json.dumps(
                {"targets": targets}, ensure_ascii=True, indent=2, sort_keys=True
            )
        )
        return
    if fmt == "shell":
        print(" ".join(targets))
        return
    if fmt == "lines":
        for target in targets:
            print(target)
        return
    raise RoutingMapError(f"unsupported output format: {fmt}")


def main() -> int:
    """Run CLI for changed-file packet test selection."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--map",
        default="scripts/test_routing_map.json",
        help="Routing map JSON path.",
    )
    parser.add_argument(
        "--mode",
        choices=("fast", "full"),
        default="fast",
        help="Selection mode.",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root for changed-file discovery.",
    )
    parser.add_argument(
        "--path",
        action="append",
        default=[],
        help="Explicit changed path override (repeatable).",
    )
    parser.add_argument(
        "--output",
        choices=("lines", "shell", "json"),
        default="lines",
        help="Output format.",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    try:
        routing_map = load_routing_map((repo_root / args.map).resolve())
        changed_paths = list(args.path) if args.path else _git_changed_paths(repo_root)
        targets = select_targets(
            routing_map=routing_map,
            changed_paths=changed_paths,
            mode=args.mode,
        )
        _print_targets(targets, fmt=args.output)
        return 0
    except RoutingMapError as exc:
        print(f"test-target-selector: FAIL\n - {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
