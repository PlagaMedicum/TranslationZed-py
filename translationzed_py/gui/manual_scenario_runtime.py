"""Manual UI scenario contract models and JSON parsing helpers."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCENARIO_ENV_FILE = "TZP_MANUAL_SCENARIO_FILE"
SCENARIO_ENV_RESULTS_DIR = "TZP_MANUAL_RESULTS_DIR"
SCENARIO_ENV_RUN_TOKEN = "TZP_MANUAL_RUN_TOKEN"
SCENARIO_REGISTRY_DEFAULT = "tests/manual_scenarios/scenarios.json"
SCENARIO_REGISTRY_VERSION = 1
VALID_WORKFLOW_FAMILIES = (
    "open_save",
    "conflict_resolution",
    "qa_checklist",
    "encoding_charsets",
    "tm_apply",
    "source_reference",
    "tzp_writeback",
    "status_triage",
    "search_replace",
    "git_sync",
)
VALID_MANUAL_DEPTHS = (
    "full_workflow",
    "branch_check",
    "same_file_diagnostic",
    "multi_file_roundtrip",
)


class ManualScenarioError(ValueError):
    """Raised when manual scenario payloads fail contract validation."""


@dataclass(frozen=True)
class ManualScenario:
    """One declarative manual UI scenario descriptor."""

    id: str
    title: str
    workflow_family: str
    manual_depth: str
    goal: str
    start_context: str
    fixture_root: str
    focus_files: tuple[str, ...]
    finish_condition: str
    selected_locales: tuple[str, ...]
    steps: tuple[str, ...]
    expected_checks: tuple[str, ...]
    tracked_repo_files: tuple[str, ...]
    env_overrides: dict[str, str]
    prefs_extras: dict[str, str]
    automation_pytest_selectors: tuple[str, ...]
    operator_hints: tuple[str, ...] = ()
    inspection_paths: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-serializable scenario payload."""
        return {
            "id": self.id,
            "title": self.title,
            "workflow_family": self.workflow_family,
            "manual_depth": self.manual_depth,
            "goal": self.goal,
            "start_context": self.start_context,
            "fixture_root": self.fixture_root,
            "focus_files": list(self.focus_files),
            "finish_condition": self.finish_condition,
            "selected_locales": list(self.selected_locales),
            "steps": list(self.steps),
            "expected_checks": list(self.expected_checks),
            "tracked_repo_files": list(self.tracked_repo_files),
            "env_overrides": dict(self.env_overrides),
            "prefs_extras": dict(self.prefs_extras),
            "automation_pytest_selectors": list(self.automation_pytest_selectors),
            "operator_hints": list(self.operator_hints),
            "inspection_paths": list(self.inspection_paths),
        }


@dataclass(frozen=True)
class ManualScenarioRuntime:
    """Runtime payload used by scenario-mode GUI startup."""

    version: int
    scenario: ManualScenario
    project_root: str

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-serializable runtime payload."""
        return {
            "version": self.version,
            "scenario": self.scenario.to_payload(),
            "project_root": self.project_root,
        }


def _require_non_empty_string(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ManualScenarioError(f"{name} must be a non-empty string")
    return value.strip()


def _string_list(value: Any, *, name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ManualScenarioError(f"{name} must be a non-empty list of strings")
    items: list[str] = []
    for idx, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise ManualScenarioError(f"{name}[{idx}] must be a non-empty string")
        items.append(item.strip())
    return tuple(items)


def _optional_string_list(value: Any, *, name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ManualScenarioError(f"{name} must be a list of strings when provided")
    items: list[str] = []
    for idx, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise ManualScenarioError(f"{name}[{idx}] must be a non-empty string")
        items.append(item.strip())
    return tuple(items)


def _optional_string_map(value: Any, *, name: str) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ManualScenarioError(f"{name} must be an object of string values")
    parsed: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key.strip():
            raise ManualScenarioError(f"{name} keys must be non-empty strings")
        if not isinstance(item, str):
            raise ManualScenarioError(f"{name}.{key!r} must be a string")
        parsed[key.strip()] = item
    return parsed


def _enum_string(value: Any, *, name: str, allowed: tuple[str, ...]) -> str:
    text = _require_non_empty_string(value, name=name)
    if text not in allowed:
        allowed_text = ", ".join(allowed)
        raise ManualScenarioError(f"{name} must be one of: {allowed_text}")
    return text


def _fixture_relative_paths(value: Any, *, name: str) -> tuple[str, ...]:
    items = _string_list(value, name=name)
    normalized: list[str] = []
    seen: set[str] = set()
    for idx, item in enumerate(items):
        if "\\" in item:
            raise ManualScenarioError(
                f"{name}[{idx}] must use POSIX-style fixture-relative paths"
            )
        path = Path(item)
        if path.is_absolute():
            raise ManualScenarioError(f"{name}[{idx}] must be fixture-relative")
        if any(part in {"", ".", ".."} for part in path.parts):
            raise ManualScenarioError(
                f"{name}[{idx}] must not contain empty, '.' or '..' segments"
            )
        normalized_item = path.as_posix()
        if normalized_item in seen:
            raise ManualScenarioError(f"{name} has duplicate path: {normalized_item}")
        seen.add(normalized_item)
        normalized.append(normalized_item)
    return tuple(normalized)


def _optional_fixture_relative_paths(value: Any, *, name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ManualScenarioError(f"{name} must be a list of fixture-relative paths")
    if not value:
        return ()
    return _fixture_relative_paths(value, name=name)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(8192)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def compute_tracked_file_hashes(
    *, repo_root: Path, tracked_repo_files: tuple[str, ...]
) -> list[dict[str, str]]:
    """Return deterministic repo-relative tracked file hash rows."""
    root = repo_root.resolve()
    rows: list[dict[str, str]] = []
    seen_paths: set[str] = set()
    for idx, raw in enumerate(tracked_repo_files):
        rel_path = str(raw).strip()
        if not rel_path:
            raise ManualScenarioError(
                f"tracked_repo_files[{idx}] must be a non-empty string"
            )
        if Path(rel_path).is_absolute():
            raise ManualScenarioError(
                f"tracked_repo_files[{idx}] must be repo-relative: {rel_path!r}"
            )
        candidate = (root / rel_path).resolve()
        try:
            normalized = candidate.relative_to(root).as_posix()
        except ValueError as exc:
            raise ManualScenarioError(
                f"tracked_repo_files[{idx}] escapes repo root: {rel_path!r}"
            ) from exc
        if normalized in seen_paths:
            raise ManualScenarioError(
                f"tracked_repo_files has duplicate path: {normalized}"
            )
        if not candidate.is_file():
            raise ManualScenarioError(
                f"tracked_repo_files[{idx}] must reference an existing file: {normalized}"
            )
        seen_paths.add(normalized)
        rows.append({"path": normalized, "sha256": _sha256_file(candidate)})
    rows.sort(key=lambda item: item["path"])
    return rows


def parse_manual_scenario(payload: Any) -> ManualScenario:
    """Parse and validate a single scenario payload object."""
    if not isinstance(payload, dict):
        raise ManualScenarioError("scenario payload must be an object")
    return ManualScenario(
        id=_require_non_empty_string(payload.get("id"), name="id"),
        title=_require_non_empty_string(payload.get("title"), name="title"),
        workflow_family=_enum_string(
            payload.get("workflow_family"),
            name="workflow_family",
            allowed=VALID_WORKFLOW_FAMILIES,
        ),
        manual_depth=_enum_string(
            payload.get("manual_depth"),
            name="manual_depth",
            allowed=VALID_MANUAL_DEPTHS,
        ),
        goal=_require_non_empty_string(payload.get("goal"), name="goal"),
        start_context=_require_non_empty_string(
            payload.get("start_context"), name="start_context"
        ),
        fixture_root=_require_non_empty_string(
            payload.get("fixture_root"), name="fixture_root"
        ),
        focus_files=_fixture_relative_paths(
            payload.get("focus_files"), name="focus_files"
        ),
        finish_condition=_require_non_empty_string(
            payload.get("finish_condition"), name="finish_condition"
        ),
        selected_locales=_string_list(
            payload.get("selected_locales"), name="selected_locales"
        ),
        steps=_string_list(payload.get("steps"), name="steps"),
        expected_checks=_string_list(
            payload.get("expected_checks"), name="expected_checks"
        ),
        tracked_repo_files=_string_list(
            payload.get("tracked_repo_files"), name="tracked_repo_files"
        ),
        env_overrides=_optional_string_map(
            payload.get("env_overrides"), name="env_overrides"
        ),
        prefs_extras=_optional_string_map(
            payload.get("prefs_extras"), name="prefs_extras"
        ),
        automation_pytest_selectors=_optional_string_list(
            payload.get("automation_pytest_selectors"),
            name="automation_pytest_selectors",
        ),
        operator_hints=_optional_string_list(
            payload.get("operator_hints"),
            name="operator_hints",
        ),
        inspection_paths=_optional_fixture_relative_paths(
            payload.get("inspection_paths"),
            name="inspection_paths",
        ),
    )


def parse_scenario_registry(payload: Any) -> tuple[ManualScenario, ...]:
    """Parse and validate a scenario registry payload."""
    if not isinstance(payload, dict):
        raise ManualScenarioError("scenario registry root must be an object")
    version = payload.get("version")
    if version != SCENARIO_REGISTRY_VERSION:
        raise ManualScenarioError(
            "scenario registry version must equal "
            f"{SCENARIO_REGISTRY_VERSION}, got {version!r}"
        )
    rows = payload.get("scenarios")
    if not isinstance(rows, list) or not rows:
        raise ManualScenarioError(
            "scenario registry requires non-empty list `scenarios`"
        )
    scenarios = tuple(parse_manual_scenario(item) for item in rows)
    seen: set[str] = set()
    duplicates: list[str] = []
    for item in scenarios:
        if item.id in seen:
            duplicates.append(item.id)
            continue
        seen.add(item.id)
    if duplicates:
        dup = ", ".join(sorted(set(duplicates)))
        raise ManualScenarioError(f"duplicate scenario ids: {dup}")
    return scenarios


def load_scenario_registry(path: Path) -> tuple[ManualScenario, ...]:
    """Load and validate scenario registry JSON from disk."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ManualScenarioError(f"missing scenario registry: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ManualScenarioError(
            f"invalid JSON in scenario registry {path}: {exc}"
        ) from exc
    return parse_scenario_registry(payload)


def scenario_by_id(
    scenarios: tuple[ManualScenario, ...], scenario_id: str
) -> ManualScenario:
    """Return one scenario by id or raise a contract error."""
    requested = scenario_id.strip()
    for scenario in scenarios:
        if scenario.id == requested:
            return scenario
    raise ManualScenarioError(f"unknown scenario id: {scenario_id!r}")


def parse_manual_runtime(payload: Any) -> ManualScenarioRuntime:
    """Parse runtime payload provided via `TZP_MANUAL_SCENARIO_FILE`."""
    if not isinstance(payload, dict):
        raise ManualScenarioError("manual scenario runtime payload must be an object")
    version = payload.get("version")
    if version != SCENARIO_REGISTRY_VERSION:
        raise ManualScenarioError(
            "manual scenario runtime version must equal "
            f"{SCENARIO_REGISTRY_VERSION}, got {version!r}"
        )
    scenario = parse_manual_scenario(payload.get("scenario"))
    project_root = _require_non_empty_string(
        payload.get("project_root"), name="project_root"
    )
    return ManualScenarioRuntime(
        version=version,
        scenario=scenario,
        project_root=project_root,
    )


def load_manual_runtime(path: Path) -> ManualScenarioRuntime:
    """Load and validate scenario runtime payload from disk."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ManualScenarioError(f"missing manual runtime payload: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ManualScenarioError(f"invalid manual runtime JSON {path}: {exc}") from exc
    return parse_manual_runtime(payload)
