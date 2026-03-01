"""Regression tests for code quality triage helpers."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def _load_module() -> ModuleType:
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "code_quality_triage.py"
    spec = importlib.util.spec_from_file_location("code_quality_triage", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[misc]
    return module


def test_extract_modules_from_doc_finds_explicit_markers(tmp_path: Path) -> None:
    """Only explicit module markers should resolve to dotted modules."""
    module = _load_module()
    doc = tmp_path / "api.md"
    doc.write_text(
        """
::: translationzed_py.core.parser

FLAGGED_MODULE: translationzed_py/core/saver.py
TRIAGE_MODULE: translationzed_py.core.file_workflow
        """.strip(),
        encoding="utf-8",
    )
    resolved = module._extract_modules_from_doc(doc)
    assert "translationzed_py.core.parser" in resolved
    assert "translationzed_py.core.saver" in resolved
    assert "translationzed_py.core.file_workflow" in resolved


def test_triage_module_marks_large_complexity(tmp_path: Path) -> None:
    """Large/branchy module should be marked REVIEW_REQUIRED."""
    module = _load_module()
    py_file = tmp_path / "huge.py"
    body = ["def heavy(x):"]
    body.extend(["    if x > 0:\n        x -= 1"] * 60)
    body.append("    return x")
    py_file.write_text("\n".join(body), encoding="utf-8")
    outcome, risk, reasons, evidence = module._triage_module(py_file)
    assert outcome == "REVIEW_REQUIRED"
    assert risk in {"P1", "P0"}
    assert reasons
    assert evidence


def test_triage_module_passes_small_module(tmp_path: Path) -> None:
    """Small module should pass triage."""
    module = _load_module()
    py_file = tmp_path / "small.py"
    py_file.write_text(
        "def ok(x):\n    return x + 1\n",
        encoding="utf-8",
    )
    outcome, risk, reasons, evidence = module._triage_module(py_file)
    assert outcome == "PASS"
    assert risk == "P2"
    assert reasons == []
    assert evidence


def test_collect_target_modules_includes_changed_core_files(tmp_path: Path) -> None:
    """Changed core python modules should be triaged by default."""
    module = _load_module()
    changed = [
        "translationzed_py/core/parser.py",
        "docs/architecture/flows.md",
    ]
    modules, deep_docs = module._collect_target_modules(tmp_path, changed, [])
    assert "translationzed_py.core.parser" in modules
    assert "docs/architecture/flows.md" in deep_docs
