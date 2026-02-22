"""Tests for mutation stage profile resolver script."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


def _load_mutation_stage_module():
    path = Path("scripts/mutation_stage.py").resolve()
    spec = importlib.util.spec_from_file_location("mutation_stage_module", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_resolve_mutation_stage_profiles() -> None:
    """Verify stage profiles resolve to expected gate mode and threshold."""
    module = _load_mutation_stage_module()

    report = module.resolve_mutation_stage(stage="report", min_killed_percent=25.0)
    assert report.mode == "warn"
    assert report.min_killed_percent == 0.0

    soft = module.resolve_mutation_stage(stage="soft", min_killed_percent=25.0)
    assert soft.mode == "warn"
    assert soft.min_killed_percent == 25.0

    strict = module.resolve_mutation_stage(stage="strict", min_killed_percent=30.0)
    assert strict.mode == "fail"
    assert strict.min_killed_percent == 30.0


def test_resolve_mutation_stage_rejects_invalid_profile() -> None:
    """Verify invalid profile names raise ValueError."""
    module = _load_mutation_stage_module()
    with pytest.raises(ValueError, match="stage must be one of"):
        module.resolve_mutation_stage(stage="invalid", min_killed_percent=25.0)


def test_main_writes_env_lines_for_github_env(tmp_path: Path) -> None:
    """Verify CLI appends effective mutation gate values to env output file."""
    module = _load_mutation_stage_module()
    out_env = tmp_path / "github-env.txt"
    sys_argv = [
        "mutation_stage.py",
        "--stage",
        "strict",
        "--min-killed-percent",
        "27.5",
        "--out-env",
        str(out_env),
    ]

    old_argv = sys.argv
    try:
        sys.argv = sys_argv
        result = module.main()
    finally:
        sys.argv = old_argv

    assert result == 0
    content = out_env.read_text(encoding="utf-8")
    assert "MUTATION_EFFECTIVE_MODE=fail\n" in content
    assert "MUTATION_EFFECTIVE_MIN_KILLED_PERCENT=27.5\n" in content
