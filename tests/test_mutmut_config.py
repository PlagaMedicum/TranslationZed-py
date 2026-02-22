"""Regression tests for repository mutmut configuration."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest


def test_mutmut_paths_to_mutate_target_critical_core_modules(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensure mutation scope remains pinned to the critical-core module set."""
    try:
        mutmain = importlib.import_module("mutmut.__main__")
    except ModuleNotFoundError:
        pytest.skip("mutmut is unavailable in this environment.")
    except PermissionError as exc:
        pytest.skip(f"mutmut import is unavailable in this environment: {exc}")
    monkeypatch.chdir(Path(__file__).resolve().parent.parent)
    config = mutmain.load_config()
    actual = sorted(str(path.as_posix()) for path in config.paths_to_mutate)
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
    assert config.tests_dir == ["tests"]
