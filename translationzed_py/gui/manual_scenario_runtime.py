"""Manual UI scenario contract models and JSON parsing helpers."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

SCENARIO_ENV_FILE = "TZP_MANUAL_SCENARIO_FILE"
SCENARIO_ENV_RESULTS_DIR = "TZP_MANUAL_RESULTS_DIR"
SCENARIO_REGISTRY_DEFAULT = "tests/manual_scenarios/scenarios.json"
SCENARIO_REGISTRY_VERSION = 1


class ManualScenarioError(ValueError):
    """Raised when manual scenario payloads fail contract validation."""


@dataclass(frozen=True)
class ManualScenario:
    """One declarative manual UI scenario descriptor."""

    id: str
    title: str
    fixture_root: str
    selected_locales: tuple[str, ...]
    steps: tuple[str, ...]
    expected_checks: tuple[str, ...]
    env_overrides: dict[str, str]
    prefs_extras: dict[str, str]
    automation_pytest_selectors: tuple[str, ...]

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-serializable scenario payload."""
        return asdict(self)


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


def parse_manual_scenario(payload: Any) -> ManualScenario:
    """Parse and validate a single scenario payload object."""
    if not isinstance(payload, dict):
        raise ManualScenarioError("scenario payload must be an object")
    return ManualScenario(
        id=_require_non_empty_string(payload.get("id"), name="id"),
        title=_require_non_empty_string(payload.get("title"), name="title"),
        fixture_root=_require_non_empty_string(
            payload.get("fixture_root"), name="fixture_root"
        ),
        selected_locales=_string_list(
            payload.get("selected_locales"), name="selected_locales"
        ),
        steps=_string_list(payload.get("steps"), name="steps"),
        expected_checks=_string_list(
            payload.get("expected_checks"), name="expected_checks"
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
