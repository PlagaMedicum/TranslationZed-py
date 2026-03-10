"""Contracts for changed-file packet-test routing selector."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


def _load_module() -> ModuleType:
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "select_test_targets.py"
    spec = importlib.util.spec_from_file_location("select_test_targets", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[misc]
    return module


def test_load_routing_map_accepts_project_contract() -> None:
    """Repository routing map should satisfy schema/version contracts."""
    module = _load_module()
    repo_root = Path(__file__).resolve().parents[1]
    routing = module.load_routing_map(repo_root / "scripts" / "test_routing_map.json")
    assert routing.version == 1
    assert routing.rules
    assert routing.full_targets


def test_select_targets_fast_matches_rules_with_dedupe() -> None:
    """Fast mode should route by changed paths and deduplicate target list."""
    module = _load_module()
    routing = module.RoutingMap(
        version=1,
        default_fast_targets=(),
        full_targets=("test-all",),
        rules=(
            module.RoutingRule(
                id="a",
                description="a",
                match_globs=("translationzed_py/core/a*.py",),
                targets_fast=("test-a", "test-shared"),
                targets_full=("test-a",),
            ),
            module.RoutingRule(
                id="b",
                description="b",
                match_globs=("translationzed_py/core/b*.py",),
                targets_fast=("test-b", "test-shared"),
                targets_full=("test-b",),
            ),
        ),
    )
    selected = module.select_targets(
        routing_map=routing,
        changed_paths=[
            "translationzed_py/core/alpha.py",
            "translationzed_py/core/beta.py",
        ],
        mode="fast",
    )
    assert selected == ["test-a", "test-shared", "test-b"]


def test_select_targets_full_returns_full_targets_only() -> None:
    """Full mode should return the map full-target set in order."""
    module = _load_module()
    routing = module.RoutingMap(
        version=1,
        default_fast_targets=("test-default",),
        full_targets=("test-one", "test-two", "test-one"),
        rules=(),
    )
    selected = module.select_targets(
        routing_map=routing,
        changed_paths=[],
        mode="full",
    )
    assert selected == ["test-one", "test-two"]


def test_load_routing_map_rejects_duplicate_rule_ids(tmp_path: Path) -> None:
    """Duplicate rule IDs should fail routing map validation."""
    module = _load_module()
    payload = {
        "version": 1,
        "default_fast_targets": [],
        "full_targets": ["test-full"],
        "rules": [
            {
                "id": "dup",
                "description": "x",
                "match_globs": ["tests/test_a.py"],
                "targets_fast": ["test-a"],
                "targets_full": ["test-a"],
            },
            {
                "id": "dup",
                "description": "y",
                "match_globs": ["tests/test_b.py"],
                "targets_fast": ["test-b"],
                "targets_full": ["test-b"],
            },
        ],
    }
    path = tmp_path / "map.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    try:
        module.load_routing_map(path)
    except module.RoutingMapError as exc:
        assert "duplicate rule id" in str(exc)
    else:
        raise AssertionError("expected duplicate-rule validation failure")
