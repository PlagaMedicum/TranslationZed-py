"""Tests for mechanical documentation validation."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


def _load_module() -> ModuleType:
    script_path = Path(__file__).resolve().parents[1] / "scripts/docs_contract_check.py"
    spec = importlib.util.spec_from_file_location("docs_contract_check", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[misc]
    return module


def test_local_links_validate_files_and_anchors(tmp_path: Path) -> None:
    """Local Markdown links should resolve to an existing file and heading."""
    module = _load_module()
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "target.md").write_text("# Target Heading\n", encoding="utf-8")
    source = docs / "source.md"
    source.write_text("[ok](target.md#target-heading)\n", encoding="utf-8")
    assert module.validate_local_links(docs) == []

    source.write_text("[bad](target.md#missing)\n", encoding="utf-8")
    errors = module.validate_local_links(docs)
    assert any("missing anchor #missing" in error for error in errors)


def test_navigation_rejects_missing_paths(tmp_path: Path) -> None:
    """Every Markdown page in navigation must exist."""
    module = _load_module()
    docs = tmp_path / "docs"
    docs.mkdir()
    config = tmp_path / "mkdocs.yml"
    config.write_text("nav:\n  - Missing: missing.md\n", encoding="utf-8")
    errors = module.validate_navigation(docs, [config])
    assert any("missing nav path missing.md" in error for error in errors)


def test_risk_register_validates_schema_and_repo_paths(tmp_path: Path) -> None:
    """Active risks should reference existing modules and focused tests."""
    module = _load_module()
    repo = tmp_path / "repo"
    docs = repo / "docs"
    reference = docs / "reference"
    reference.mkdir(parents=True)
    source = repo / "translationzed_py/core/parser.py"
    test = repo / "tests/test_parser.py"
    source.parent.mkdir(parents=True)
    test.parent.mkdir(parents=True)
    source.write_text("", encoding="utf-8")
    test.write_text("", encoding="utf-8")
    payload = {
        "version": 2,
        "risks": [
            {
                "module_path": "translationzed_py/core/parser.py",
                "status": "monitoring",
                "severity": "high",
                "concern": "Span-sensitive parser.",
                "evidence": ["Parser controls byte spans."],
                "constraints": ["Preserve byte offsets."],
                "closure_criteria": ["Keep roundtrip tests green."],
                "relevant_tests": ["tests/test_parser.py"],
            }
        ],
    }
    (reference / "risk_register.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )
    assert module.validate_risk_register(docs, repo) == []

    payload["risks"][0]["relevant_tests"] = ["tests/missing.py"]
    (reference / "risk_register.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )
    errors = module.validate_risk_register(docs, repo)
    assert any("relevant_tests missing" in error for error in errors)


def test_active_plan_requires_only_structural_sections(tmp_path: Path) -> None:
    """The active plan contract should require structure without exact prose."""
    module = _load_module()
    docs = tmp_path / "docs"
    plan = docs / "plan/implementation_active.md"
    plan.parent.mkdir(parents=True)
    plan.write_text(
        "\n".join(
            [
                "# Plan",
                "## Current Objective",
                "## Constraints",
                "## Verified State",
                "## Acceptance Criteria",
                "## Open Follow-ups",
            ]
        ),
        encoding="utf-8",
    )
    assert module.validate_active_plan(docs) == []


def test_retired_references_are_rejected(tmp_path: Path) -> None:
    """Removed generated/history surfaces must not remain linked."""
    module = _load_module()
    docs = tmp_path / "docs"
    docs.mkdir()
    page = docs / "page.md"
    page.write_text("See docs/reference/review_queue.json\n", encoding="utf-8")
    errors = module.validate_retired_references(docs, [])
    assert any("references retired path" in error for error in errors)


def test_command_parity_rejects_missing_documented_make_target(
    tmp_path: Path,
) -> None:
    """Documented and workflow Make commands must exist."""
    module = _load_module()
    repo = tmp_path / "repo"
    docs = repo / "docs"
    docs.mkdir(parents=True)
    (repo / "Makefile").write_text("check:\n\ttrue\n", encoding="utf-8")
    (docs / "commands.md").write_text("Run `make missing`.\n", encoding="utf-8")
    errors = module.validate_command_parity(repo, docs)
    assert any("documented Make target missing: missing" in error for error in errors)


def test_semantic_contracts_reject_missing_formula(tmp_path: Path) -> None:
    """Focused semantic contracts should fail when a protected formula disappears."""
    module = _load_module()
    docs = tmp_path / "docs"
    for relative, snippets in module.SEMANTIC_CONTRACTS.items():
        path = docs / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(snippets), encoding="utf-8")
    tm_path = docs / "domain/tm_ranking.md"
    tm_path.write_text("TM Long-Variant Detection Contract\n", encoding="utf-8")
    errors = module.validate_semantic_contracts(docs)
    assert any("missing semantic contract" in error for error in errors)


def test_stale_language_rejects_implemented_feature_as_future(
    tmp_path: Path,
) -> None:
    """Current contract docs must not regress to future v0.9 wording."""
    module = _load_module()
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "page.md").write_text("This is the v0.9 target.\n", encoding="utf-8")
    errors = module.validate_stale_language(docs)
    assert any("v0.9 is current" in error for error in errors)
