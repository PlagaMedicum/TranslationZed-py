"""Regression tests for repository pytest discovery configuration."""

from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
    import tomli as tomllib


def test_pytest_collection_is_pinned_to_tests_dir() -> None:
    """Ensure pytest collection stays within the committed tests root."""
    repo_root = Path(__file__).resolve().parent.parent
    pyproject = repo_root / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    config = data.get("tool", {}).get("pytest", {}).get("ini_options", {})

    assert config.get("testpaths") == ["tests"]
    assert config.get("addopts") == "-ra -q --benchmark-skip"

    ignored = set(config.get("norecursedirs", []))
    assert {
        "mutants",
        ".external",
        "artifacts",
        "build",
        "dist",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".venv",
    }.issubset(ignored)
