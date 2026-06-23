#!/usr/bin/env python3
"""Validate manual UI scenario and workflow test-surface contracts."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from contextlib import suppress
from pathlib import Path
from typing import Any

from translationzed_py.gui.manual_scenario_runtime import (
    SCENARIO_REGISTRY_DEFAULT,
    ManualScenarioError,
    compute_tracked_file_hashes,
    load_scenario_registry,
)

REQUIRED_WORKFLOW_KEYS = (
    "open_save",
    "conflict_resolution",
    "qa_checklist",
    "encoding_charsets",
    "tm_apply",
    "source_reference",
    "search_replace",
    "status_triage",
    "tzp_writeback",
)

REQUIRED_WORKFLOW_SCENARIO_IDS: dict[str, tuple[str, ...]] = {
    "conflict_resolution": ("conflict-resolution-flow",)
}

MANUAL_WORKFLOW_FIXTURE_ROOT = "manual_workflow"
MANUAL_WORKFLOW_REQUIRED_LOCALES = ("EN", "RU", "KO")
SCENARIO_TEXT_BANNED_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"\bclose file\b", re.IGNORECASE),
        "scenario text must not require a non-existent close-file action",
    ),
    (
        re.compile(r"\bre-?open\b", re.IGNORECASE),
        "scenario text must not rely on reopen wording; use file switching or exit flow",
    ),
    (
        re.compile(r"\bopen a file\b", re.IGNORECASE),
        "scenario text must name concrete files, not generic file wording",
    ),
    (
        re.compile(r"\bopen one file\b", re.IGNORECASE),
        "scenario text must name concrete files, not generic file wording",
    ),
    (
        re.compile(r"\binspect (?:the )?copied file\b", re.IGNORECASE),
        "scenario text must name concrete inspection_paths instead of vague copied-file wording",
    ),
    (
        re.compile(r"\bshown project root\b", re.IGNORECASE),
        "scenario text must name concrete inspection_paths "
        "instead of referring to a shown project root",
    ),
)
CONFLICT_NEUTRAL_SWITCH_CACHE_PATHS: tuple[str, ...] = (
    "tests/fixtures/conflict_manual/.tzp/cache/BE/ui.bin",
    "tests/fixtures/conflict_manual/.tzp/cache/RU/ui.bin",
)
SAVE_EXPLICIT_WORKFLOWS = frozenset(
    {"open_save", "conflict_resolution", "encoding_charsets", "tzp_writeback"}
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


def _scenario_authoring_text(scenario: Any) -> str:
    parts = [
        str(getattr(scenario, "goal", "")),
        str(getattr(scenario, "start_context", "")),
        str(getattr(scenario, "finish_condition", "")),
        *tuple(getattr(scenario, "steps", ())),
        *tuple(getattr(scenario, "expected_checks", ())),
        *tuple(getattr(scenario, "operator_hints", ())),
        *tuple(getattr(scenario, "inspection_paths", ())),
    ]
    return "\n".join(part.strip() for part in parts if str(part).strip())


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
    scenario_ids = {scenario.id for scenario in scenarios}
    family_counts = dict.fromkeys(REQUIRED_WORKFLOW_KEYS, 0)
    manual_workflow_root = (
        repo_root / "tests" / "fixtures" / MANUAL_WORKFLOW_FIXTURE_ROOT
    )
    if manual_workflow_root.is_dir():
        available_locales = {
            path.name for path in manual_workflow_root.iterdir() if path.is_dir()
        }
        for locale in MANUAL_WORKFLOW_REQUIRED_LOCALES:
            if locale not in available_locales:
                errors.append(
                    f"{manual_workflow_root}: missing required locale directory {locale}"
                )

    for scenario in scenarios:
        fixture = repo_root / "tests" / "fixtures" / scenario.fixture_root
        if not fixture.is_dir():
            errors.append(
                f"scenario {scenario.id!r}: fixture_root does not exist under tests/fixtures: "
                f"{scenario.fixture_root}"
            )
        if scenario.workflow_family not in REQUIRED_WORKFLOW_KEYS:
            errors.append(
                f"scenario {scenario.id!r}: workflow_family not covered by workflow contract: "
                f"{scenario.workflow_family!r}"
            )
        else:
            family_counts[scenario.workflow_family] += 1
        for focus_file in scenario.focus_files:
            focus_path = fixture / focus_file
            if not focus_path.is_file():
                errors.append(
                    f"scenario {scenario.id!r}: focus_files entry missing under fixture root: "
                    f"{focus_file}"
                )
        for inspection_path in scenario.inspection_paths:
            inspection_target = fixture / inspection_path
            if not inspection_target.is_file():
                errors.append(
                    "scenario "
                    f"{scenario.id!r}: inspection_paths entry missing under fixture "
                    f"root: {inspection_path}"
                )
        scenario_text = _scenario_authoring_text(scenario)
        for pattern, message in SCENARIO_TEXT_BANNED_PATTERNS:
            if pattern.search(scenario_text):
                errors.append(f"scenario {scenario.id!r}: {message}")
        lowered_text = scenario_text.casefold()
        for focus_file in scenario.focus_files:
            if focus_file.casefold() not in lowered_text:
                errors.append(
                    f"scenario {scenario.id!r}: focus_files entry must be referenced in "
                    f"scenario text or finish condition: {focus_file}"
                )
        for inspection_path in scenario.inspection_paths:
            if inspection_path.casefold() not in lowered_text:
                errors.append(
                    f"scenario {scenario.id!r}: inspection_paths entry must be referenced "
                    f"in scenario text or operator hints: {inspection_path}"
                )
        if (
            scenario.workflow_family in SAVE_EXPLICIT_WORKFLOWS
            and "save" not in lowered_text
        ):
            errors.append(
                f"scenario {scenario.id!r}: save-dependent workflow must mention save "
                "explicitly in steps or finish condition"
            )
        if scenario.fixture_root == MANUAL_WORKFLOW_FIXTURE_ROOT:
            if any(locale == "BE" for locale in scenario.selected_locales):
                errors.append(
                    f"scenario {scenario.id!r}: manual_workflow fixture must not use BE as a "
                    "generic target locale"
                )
            if any(path.startswith("BE/") for path in scenario.focus_files):
                errors.append(
                    f"scenario {scenario.id!r}: manual_workflow focus_files must not point to "
                    "BE-only paths"
                )
        try:
            compute_tracked_file_hashes(
                repo_root=repo_root,
                tracked_repo_files=scenario.tracked_repo_files,
            )
        except ManualScenarioError as exc:
            errors.append(f"scenario {scenario.id!r}: {exc}")
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
        if scenario.id == "conflict-resolution-flow":
            for relpath in CONFLICT_NEUTRAL_SWITCH_CACHE_PATHS:
                if (repo_root / relpath).exists():
                    errors.append(
                        f"scenario {scenario.id!r}: neutral switch file must not keep "
                        f"conflict cache artifact: {relpath}"
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
        if family_counts.get(required_key, 0) <= 0:
            errors.append(
                f"scenario registry missing scenario for workflow_family: {required_key}"
            )

    for key, row in workflows.items():
        if not isinstance(row, dict):
            errors.append(f"workflow {key!r} contract row must be an object")
            continue
        raw_required_scenarios = row.get("required_scenario_ids")
        parsed_required_scenarios: tuple[str, ...] = ()
        if raw_required_scenarios is not None:
            if (
                not isinstance(raw_required_scenarios, list)
                or not raw_required_scenarios
                or any(
                    not isinstance(item, str) or not item.strip()
                    for item in raw_required_scenarios
                )
            ):
                errors.append(
                    f"workflow {key!r} required_scenario_ids must be non-empty string list"
                )
            else:
                normalized = tuple(item.strip() for item in raw_required_scenarios)
                if len(set(normalized)) != len(normalized):
                    errors.append(
                        f"workflow {key!r} required_scenario_ids must not contain duplicates"
                    )
                parsed_required_scenarios = normalized
        expected_required = REQUIRED_WORKFLOW_SCENARIO_IDS.get(key)
        if (
            expected_required is not None
            and parsed_required_scenarios != expected_required
        ):
            errors.append(
                f"workflow {key!r} required_scenario_ids must equal {list(expected_required)!r}"
            )
        for scenario_id in parsed_required_scenarios:
            if scenario_id not in scenario_ids:
                errors.append(
                    "workflow "
                    f"{key!r}: required_scenario_id not found in scenario registry: "
                    f"{scenario_id!r}"
                )
                continue
            referenced = next(
                scenario for scenario in scenarios if scenario.id == scenario_id
            )
            if referenced.workflow_family != key:
                errors.append(
                    f"workflow {key!r}: required_scenario_id must use matching "
                    f"workflow_family: {scenario_id!r}"
                )
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


def build_manual_contract_summary(
    *,
    repo_root: Path,
    registry_path: Path,
    workflow_contract_path: Path,
    collect_selectors: bool,
) -> dict[str, Any]:
    """Return structured manual-contract summary for CLI/report consumers."""
    scenario_ids: list[str] = []
    workflow_keys: list[str] = []
    with suppress(ManualScenarioError):
        scenario_ids = [
            scenario.id for scenario in load_scenario_registry(registry_path)
        ]
    try:
        payload = _load_json(workflow_contract_path)
    except ManualScenarioError:
        payload = {}
    if isinstance(payload, dict):
        raw_workflows = payload.get("required_workflows")
        if isinstance(raw_workflows, dict):
            workflow_keys = sorted(str(key) for key in raw_workflows)
    errors = validate_manual_scenario_contracts(
        repo_root=repo_root,
        registry_path=registry_path,
        workflow_contract_path=workflow_contract_path,
        collect_selectors=collect_selectors,
    )
    return {
        "version": 1,
        "registry": str(registry_path),
        "workflow_contract": str(workflow_contract_path),
        "scenario_count": len(scenario_ids),
        "scenario_ids": scenario_ids,
        "workflow_keys": workflow_keys,
        "collect_selectors": collect_selectors,
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
    summary = build_manual_contract_summary(
        repo_root=repo_root,
        registry_path=(repo_root / args.registry).resolve(),
        workflow_contract_path=(repo_root / args.workflow_contract).resolve(),
        collect_selectors=not bool(args.no_collect),
    )
    if args.json_out:
        _write_json(Path(args.json_out).resolve(), summary)
    if summary["errors"]:
        print("ui-manual-contract-check: FAIL")
        for err in summary["errors"]:
            print(f" - {err}")
        if args.verbose:
            print(json.dumps(summary, indent=2, sort_keys=True))
        return 1
    print("ui-manual-contract-check: PASS")
    print(f"validated registry: {args.registry}")
    print(f"validated workflow contract: {args.workflow_contract}")
    if args.verbose:
        print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
