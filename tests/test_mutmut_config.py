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
    also_copy = sorted(str(path) for path in config.get("also_copy", []))
    expected_also_copy = sorted(
        str(path.relative_to(repo_root).as_posix())
        for path in (repo_root / "translationzed_py" / "core").glob("*.py")
        if str(path.relative_to(repo_root).as_posix()) not in expected
    )
    assert actual == expected
    assert also_copy == expected_also_copy
    assert config.get("tests_dir") == [
        "tests/test_parser_features.py",
        "tests/test_parser_offset_map_invariants.py",
        "tests/test_parser_branch_coverage.py",
        "tests/test_parser_perf_contract.py",
        "tests/test_saver.py",
        "tests/test_roundtrip.py",
        "tests/test_regression_roundtrip.py",
        "tests/test_status_cache.py",
        "tests/test_status_cache_helpers.py",
        "tests/test_status_cache_edge_branches.py",
        "tests/test_project_session.py",
        "tests/test_save_exit_flow.py",
        "tests/test_conflict_service.py",
        "tests/test_search_replace_service.py",
        "tests/test_search_wave2_equivalence.py",
        "tests/test_search_perf_contract.py",
    ]
    assert config.get("pytest_add_cli_args_test_selection") == [
        "--ignore=tests/benchmarks"
    ]
