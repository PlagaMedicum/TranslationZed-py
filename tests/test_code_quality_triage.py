"""Regression tests for active-risk triage."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


def _load_module() -> ModuleType:
    script = Path(__file__).resolve().parents[1] / "scripts/code_quality_triage.py"
    spec = importlib.util.spec_from_file_location("code_quality_triage", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[misc]
    return module


def test_triage_marks_long_function_as_high_risk(tmp_path: Path) -> None:
    """Long functions should cross the risk-discovery threshold."""
    module = _load_module()
    path = tmp_path / "large.py"
    path.write_text(
        "def run(value):\n" + "".join("    value += 1\n" for _ in range(181)),
        encoding="utf-8",
    )
    high_risk, reasons, stats = module._triage_module(path)
    assert high_risk
    assert stats.max_function_lines >= 180
    assert reasons


def test_run_triage_requires_register_entry_for_changed_high_risk_module(
    tmp_path: Path,
) -> None:
    """Changed high-risk modules must have an active register entry."""
    module = _load_module()
    repo = tmp_path / "repo"
    source = repo / "translationzed_py/core/large.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "def run(value):\n" + "".join("    value += 1\n" for _ in range(181)),
        encoding="utf-8",
    )
    register = repo / "docs/reference/risk_register.json"
    register.parent.mkdir(parents=True)
    register.write_text('{"version": 2, "risks": []}', encoding="utf-8")
    _, errors = module.run_triage(
        repo_root=repo,
        risk_register=register,
        changed_files=["translationzed_py/core/large.py"],
    )
    assert errors == [
        "high-risk changed module missing risk entry: translationzed_py/core/large.py"
    ]

    register.write_text(
        json.dumps(
            {
                "version": 2,
                "risks": [
                    {
                        "module_path": "translationzed_py/core/large.py",
                        "relevant_tests": ["tests/test_large.py"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    _, errors = module.run_triage(
        repo_root=repo,
        risk_register=register,
        changed_files=["translationzed_py/core/large.py"],
    )
    assert errors == []


def test_run_triage_ignores_small_changed_module_without_register(
    tmp_path: Path,
) -> None:
    """Small changed modules should not require speculative risk entries."""
    module = _load_module()
    repo = tmp_path / "repo"
    source = repo / "translationzed_py/core/small.py"
    source.parent.mkdir(parents=True)
    source.write_text("def run(value):\n    return value\n", encoding="utf-8")
    register = repo / "docs/reference/risk_register.json"
    register.parent.mkdir(parents=True)
    register.write_text('{"version": 2, "risks": []}', encoding="utf-8")
    _, errors = module.run_triage(
        repo_root=repo,
        risk_register=register,
        changed_files=["translationzed_py/core/small.py"],
    )
    assert errors == []
