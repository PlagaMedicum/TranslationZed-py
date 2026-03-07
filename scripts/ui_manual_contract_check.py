#!/usr/bin/env python3
"""Validate manual UI scenario and workflow test-surface contracts."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from translationzed_py.gui.manual_scenario_runtime import (
    SCENARIO_REGISTRY_DEFAULT,
    ManualScenarioError,
    load_scenario_registry,
)

REQUIRED_WORKFLOW_KEYS = (
    "open_save",
    "conflict_resolution",
    "qa_checklist",
    "tm_apply",
    "source_reference",
    "tzp_writeback",
)


def _selector_path(selector: str) -> Path:
    return Path(selector.split("::", 1)[0])


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ManualScenarioError(f"missing contract file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ManualScenarioError(f"invalid JSON in {path}: {exc}") from exc


def _validate_selector_exists(selector: str, *, repo_root: Path) -> list[str]:
    errors: list[str] = []
    if not isinstance(selector, str) or not selector.strip():
        return ["selector must be a non-empty string"]
    path = _selector_path(selector.strip())
    if path.suffix != ".py":
        errors.append(f"selector path must target a python test file: {selector!r}")
    if not (repo_root / path).is_file():
        errors.append(f"selector test path missing in repo: {path}")
    return errors


def _collect_selector(selector: str, *, repo_root: Path) -> list[str]:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-o",
        "addopts=",
        "--collect-only",
        selector,
    ]
    proc = subprocess.run(
        cmd,
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        detail = (proc.stdout or proc.stderr or "").strip()
        return [f"selector collect failed ({selector!r}): {detail}"]
    output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    if "collected 0 items" in output:
        return [f"selector collected zero tests: {selector!r}"]
    return []


def validate_manual_scenario_contracts(
    *,
    repo_root: Path,
    registry_path: Path,
    workflow_contract_path: Path,
    collect_selectors: bool,
) -> list[str]:
    """Return validation errors for scenario registry and workflow mapping contracts."""
    errors: list[str] = []
    try:
        scenarios = load_scenario_registry(registry_path)
    except ManualScenarioError as exc:
        return [str(exc)]

    for scenario in scenarios:
        fixture = repo_root / "tests" / "fixtures" / scenario.fixture_root
        if not fixture.is_dir():
            errors.append(
                f"scenario {scenario.id!r}: fixture_root does not exist under tests/fixtures: "
                f"{scenario.fixture_root}"
            )
        for selector in scenario.automation_pytest_selectors:
            errors.extend(
                [
                    f"scenario {scenario.id!r}: {msg}"
                    for msg in _validate_selector_exists(selector, repo_root=repo_root)
                ]
            )
            if collect_selectors:
                errors.extend(
                    [
                        f"scenario {scenario.id!r}: {msg}"
                        for msg in _collect_selector(selector, repo_root=repo_root)
                    ]
                )

    try:
        contract_payload = _load_json(workflow_contract_path)
    except ManualScenarioError as exc:
        return errors + [str(exc)]

    if not isinstance(contract_payload, dict):
        return errors + ["workflow contract root must be an object"]
    if contract_payload.get("version") != 1:
        errors.append("workflow contract `version` must equal 1")
    workflows = contract_payload.get("required_workflows")
    if not isinstance(workflows, dict):
        return errors + ["workflow contract requires object `required_workflows`"]

    for required_key in REQUIRED_WORKFLOW_KEYS:
        if required_key not in workflows:
            errors.append(
                f"workflow contract missing required workflow key: {required_key}"
            )

    for key, row in workflows.items():
        if not isinstance(row, dict):
            errors.append(f"workflow {key!r} contract row must be an object")
            continue
        selectors = row.get("selectors")
        if not isinstance(selectors, list) or not selectors:
            errors.append(f"workflow {key!r} must provide non-empty `selectors` list")
            continue
        for selector in selectors:
            errors.extend(
                [
                    f"workflow {key!r}: {msg}"
                    for msg in _validate_selector_exists(
                        str(selector), repo_root=repo_root
                    )
                ]
            )
            if collect_selectors:
                errors.extend(
                    [
                        f"workflow {key!r}: {msg}"
                        for msg in _collect_selector(str(selector), repo_root=repo_root)
                    ]
                )

    deprecated = contract_payload.get("deprecated_test_replacements", [])
    if deprecated is None:
        deprecated = []
    if not isinstance(deprecated, list):
        errors.append("deprecated_test_replacements must be a list")
        return errors
    for idx, item in enumerate(deprecated):
        if not isinstance(item, dict):
            errors.append(f"deprecated_test_replacements[{idx}] must be an object")
            continue
        deprecated_selector = item.get("deprecated_selector")
        replacement_selectors = item.get("replacement_selectors")
        if not isinstance(deprecated_selector, str) or not deprecated_selector.strip():
            errors.append(
                f"deprecated_test_replacements[{idx}].deprecated_selector must be non-empty"
            )
            continue
        if (
            not isinstance(replacement_selectors, list)
            or not replacement_selectors
            or any(
                not isinstance(sel, str) or not sel.strip()
                for sel in replacement_selectors
            )
        ):
            errors.append(
                "deprecated_test_replacements["
                f"{idx}].replacement_selectors must be non-empty string list"
            )
            continue
        # A deprecated selector may already be removed; replacements must stay valid.
        deprecated_exists = (
            repo_root / _selector_path(deprecated_selector.strip())
        ).is_file()
        if not deprecated_exists:
            for selector in replacement_selectors:
                errors.extend(
                    [
                        f"deprecated_test_replacements[{idx}]: {msg}"
                        for msg in _validate_selector_exists(
                            selector, repo_root=repo_root
                        )
                    ]
                )
                if collect_selectors:
                    errors.extend(
                        [
                            f"deprecated_test_replacements[{idx}]: {msg}"
                            for msg in _collect_selector(selector, repo_root=repo_root)
                        ]
                    )
    return errors


def main() -> int:
    """Run the manual scenario/workflow coverage contract checker CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--registry",
        default=SCENARIO_REGISTRY_DEFAULT,
        help="Manual scenario registry JSON path.",
    )
    parser.add_argument(
        "--workflow-contract",
        default="tests/manual_scenarios/workflow_test_surface_contract.json",
        help="Workflow no-shrink contract JSON path.",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root used for fixture/test-path checks.",
    )
    parser.add_argument(
        "--no-collect",
        action="store_true",
        help="Skip pytest --collect-only selector viability checks.",
    )
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()
    errors = validate_manual_scenario_contracts(
        repo_root=repo_root,
        registry_path=(repo_root / args.registry).resolve(),
        workflow_contract_path=(repo_root / args.workflow_contract).resolve(),
        collect_selectors=not bool(args.no_collect),
    )
    if errors:
        print("ui-manual-contract-check: FAIL")
        for err in errors:
            print(f" - {err}")
        return 1
    print("ui-manual-contract-check: PASS")
    print(f"validated registry: {args.registry}")
    print(f"validated workflow contract: {args.workflow_contract}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
