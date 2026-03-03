"""Regression tests for repository mutmut configuration."""

from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
    import tomli as tomllib


def test_mutmut_paths_to_mutate_target_critical_core_modules() -> None:
    """Ensure mutation scope remains pinned to the critical-core module set."""
    repo_root = Path(__file__).resolve().parent.parent
    pyproject = repo_root / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    config = data.get("tool", {}).get("mutmut", {})
    actual = sorted(str(path) for path in config.get("paths_to_mutate", []))
    expected = sorted(
        [
            "translationzed_py/core/parser.py",
            "translationzed_py/core/saver.py",
            "translationzed_py/core/status_cache.py",
            "translationzed_py/core/project_session.py",
            "translationzed_py/core/save_exit_flow.py",
            "translationzed_py/core/conflict_service.py",
            "translationzed_py/core/search_replace_service.py",
        ]
    )
    assert actual == expected
    assert config.get("tests_dir") == ["tests"]
