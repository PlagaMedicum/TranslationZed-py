"""Regression tests for review queue schema validation."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def _load_module() -> ModuleType:
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "review_queue_check.py"
    spec = importlib.util.spec_from_file_location("review_queue_check", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[misc]
    return module


def test_validate_queue_accepts_empty_schema(tmp_path: Path) -> None:
    """Empty queue with version should pass."""
    module = _load_module()
    queue = tmp_path / "review_queue.json"
    queue.write_text('{"version": 1, "entries": []}', encoding="utf-8")
    assert module.validate_queue(queue) == []


def test_validate_queue_rejects_invalid_entry(tmp_path: Path) -> None:
    """Invalid status and missing dates should fail validation."""
    module = _load_module()
    queue = tmp_path / "review_queue.json"
    queue.write_text(
        """
{
  "version": 1,
  "entries": [
    {
      "module_path": "translationzed_py/core/parser.py",
      "status": "BROKEN",
      "risk_level": "P1",
      "reason_codes": ["COMPLEXITY"],
      "evidence": ["example"],
      "refactor_scope": "split parser helpers",
      "required_tests": ["tests/test_parser_offset_map_invariants.py"],
      "owner": "docs",
      "opened_at": "2026-02-26",
      "closure_criteria": ["reduce complexity"],
      "closed_at": null
    }
  ]
}
        """.strip(),
        encoding="utf-8",
    )
    errors = module.validate_queue(queue)
    assert errors
    assert any(".status must be one of" in err for err in errors)


def test_validate_queue_rejects_duplicate_active_entries(tmp_path: Path) -> None:
    """Duplicate active module entries should fail queue integrity checks."""
    module = _load_module()
    queue = tmp_path / "review_queue.json"
    payload = """
{
  "version": 1,
  "entries": [
    {
      "module_path": "translationzed_py/core/parser.py",
      "status": "REVIEW_REQUIRED",
      "risk_level": "P1",
      "reason_codes": ["COMPLEXITY"],
      "evidence": ["one"],
      "refactor_scope": "scope",
      "required_tests": ["tests/test_parser_offset_map_invariants.py"],
      "owner": "docs",
      "opened_at": "2026-02-26",
      "closure_criteria": ["criteria"],
      "closed_at": null
    },
    {
      "module_path": "translationzed_py/core/parser.py",
      "status": "IN_REFACTOR",
      "risk_level": "P1",
      "reason_codes": ["COMPLEXITY"],
      "evidence": ["two"],
      "refactor_scope": "scope",
      "required_tests": ["tests/test_parser_offset_map_invariants.py"],
      "owner": "docs",
      "opened_at": "2026-02-27",
      "closure_criteria": ["criteria"],
      "closed_at": null
    }
  ]
}
    """.strip()
    queue.write_text(payload, encoding="utf-8")
    errors = module.validate_queue(queue, repo_root=Path(".").resolve())
    assert any("duplicate active queue entry" in err for err in errors)


def test_validate_queue_rejects_missing_repo_paths(tmp_path: Path) -> None:
    """Missing module/test paths should fail when repo_root checks are enabled."""
    module = _load_module()
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    queue = tmp_path / "review_queue.json"
    queue.write_text(
        """
{
  "version": 1,
  "entries": [
    {
      "module_path": "translationzed_py/core/not_real.py",
      "status": "REVIEW_REQUIRED",
      "risk_level": "P1",
      "reason_codes": ["TEST_GAP"],
      "evidence": ["missing paths"],
      "refactor_scope": "scope",
      "required_tests": ["tests/test_not_real.py"],
      "owner": "docs",
      "opened_at": "2026-02-26",
      "closure_criteria": ["criteria"],
      "closed_at": null
    }
  ]
}
        """.strip(),
        encoding="utf-8",
    )
    errors = module.validate_queue(queue, repo_root=repo)
    assert any("module_path does not exist" in err for err in errors)
    assert any("required_tests path missing" in err for err in errors)
