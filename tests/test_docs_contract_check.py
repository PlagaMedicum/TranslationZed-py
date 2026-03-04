"""Unit coverage for docs contract checker regression guards."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def _load_docs_contract_module() -> ModuleType:
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "docs_contract_check.py"
    spec = importlib.util.spec_from_file_location("docs_contract_check", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[misc]
    return module


def test_pseudo_list_paragraph_detection() -> None:
    """Pseudo-bullet paragraphs should be flagged as docs-shape violations."""
    module = _load_docs_contract_module()
    assert module._looks_like_pseudo_list_paragraph("- [✓] done item")
    assert module._looks_like_pseudo_list_paragraph("Covered: - parser - tm - qa")
    assert module._looks_like_pseudo_list_paragraph(
        "| Trigger | General ▸ Save | | Flow | 1. write |"
    )
    assert not module._looks_like_pseudo_list_paragraph(
        "Covered checks are listed in proper bullet items."
    )


def test_math_source_sanity_detects_broken_tex(tmp_path: Path) -> None:
    """Malformed TeX blocks should fail math source sanity validation."""
    module = _load_docs_contract_module()
    docs_root = tmp_path / "docs"
    math_path = docs_root / "performance" / "math_appendix.md"
    math_path.parent.mkdir(parents=True, exist_ok=True)
    math_path.write_text(
        "$$ G = 100\\cdot\\frac{a-b $$}}{a}\n",
        encoding="utf-8",
    )
    errors = module._validate_math_source_sanity(docs_root)
    assert errors
    assert any("malformed TeX block" in err for err in errors)


def test_rendered_html_shape_detects_pseudo_list_paragraphs(tmp_path: Path) -> None:
    """Rendered canonical pages should reject pseudo-list paragraph content."""
    module = _load_docs_contract_module()
    site_root = tmp_path / "site"
    for rel in module.RENDERED_HTML_SCAN_SCOPE:
        html_rel = module._canonical_html_rel(rel)
        html_path = site_root / html_rel
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(
            "<html><body><p>All good.</p></body></html>", encoding="utf-8"
        )
    target = site_root / module._canonical_html_rel("plan/implementation_history.md")
    target.write_text(
        "<html><body><p>A10: - [✓] step one - [ ] step two</p></body></html>",
        encoding="utf-8",
    )
    errors = module._validate_rendered_html_shape(site_root)
    assert errors
    assert any("pseudo-list paragraph detected" in err for err in errors)


def test_review_queue_refs_require_flagged_marker(tmp_path: Path) -> None:
    """Active queue entries should require FLAGGED_MODULE markers in code architecture."""
    module = _load_docs_contract_module()
    docs_root = tmp_path / "docs"
    (docs_root / "reference").mkdir(parents=True, exist_ok=True)
    (docs_root / "architecture").mkdir(parents=True, exist_ok=True)
    (docs_root / "reference" / "review_queue.json").write_text(
        """
{
  "version": 1,
  "entries": [
    {
      "module_path": "translationzed_py/core/preferences.py",
      "status": "REVIEW_REQUIRED",
      "risk_level": "P1",
      "reason_codes": ["COMPLEXITY"],
      "evidence": ["test"],
      "refactor_scope": "split parser",
      "required_tests": ["tests/test_preferences.py"],
      "owner": "docs",
      "opened_at": "2026-02-26",
      "closure_criteria": ["split into helpers"],
      "closed_at": null
    }
  ]
}
        """.strip(),
        encoding="utf-8",
    )
    (docs_root / "architecture" / "code_architecture.md").write_text(
        "# Code Architecture\n",
        encoding="utf-8",
    )
    errors = module._validate_review_queue_refs(docs_root)
    assert errors
    assert any("missing flagged-module marker" in err for err in errors)


def test_review_queue_refs_require_api_warning_for_flagged_modules(
    tmp_path: Path,
) -> None:
    """Active flagged modules should require API visibility + warning wording."""
    module = _load_docs_contract_module()
    docs_root = tmp_path / "docs"
    (docs_root / "reference" / "api").mkdir(parents=True, exist_ok=True)
    (docs_root / "architecture").mkdir(parents=True, exist_ok=True)
    (docs_root / "reference" / "review_queue.json").write_text(
        """
{
  "version": 1,
  "entries": [
    {
      "module_path": "translationzed_py/core/parser.py",
      "status": "REVIEW_REQUIRED",
      "risk_level": "P1",
      "reason_codes": ["COMPLEXITY"],
      "evidence": ["test"],
      "refactor_scope": "split parser",
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
    (docs_root / "architecture" / "code_architecture.md").write_text(
        "FLAGGED_MODULE: translationzed_py/core/parser.py\n",
        encoding="utf-8",
    )
    (docs_root / "reference" / "api" / "core.md").write_text(
        "::: translationzed_py.core.parser\n",
        encoding="utf-8",
    )
    errors = module._validate_review_queue_refs(docs_root)
    assert errors
    assert any("must include warning text" in err for err in errors)


def test_tm_long_variant_contract_requires_formula_snippets(tmp_path: Path) -> None:
    """TM ranking doc should require long-variant formula snippets."""
    module = _load_docs_contract_module()
    docs_root = tmp_path / "docs"
    (docs_root / "domain").mkdir(parents=True, exist_ok=True)
    (docs_root / "architecture").mkdir(parents=True, exist_ok=True)
    (docs_root / "domain" / "tm_ranking.md").write_text(
        "# TM Ranking\n\n### TM Long-Variant Detection Contract\n",
        encoding="utf-8",
    )
    (docs_root / "architecture" / "code_architecture.md").write_text(
        "TM Long-Variant Detection Pipeline\n",
        encoding="utf-8",
    )
    (docs_root / "architecture" / "diagrams.md").write_text(
        "TM Long-Variant Detection Activity\n",
        encoding="utf-8",
    )
    errors = module._validate_tm_long_variant_contract(docs_root)
    assert errors
    assert any("missing TM long-variant contract snippet" in err for err in errors)


def test_tm_long_variant_contract_requires_diagram_anchors(tmp_path: Path) -> None:
    """TM long-variant contract should require architecture diagram anchors."""
    module = _load_docs_contract_module()
    docs_root = tmp_path / "docs"
    (docs_root / "domain").mkdir(parents=True, exist_ok=True)
    (docs_root / "architecture").mkdir(parents=True, exist_ok=True)
    (docs_root / "domain" / "tm_ranking.md").write_text(
        """
### 4.3 TM Long-Variant Detection Contract
L_{\\text{min\\_base}} = \\max(1,\\lfloor 0.6 \\cdot L_q \\rfloor)
is\\_long\\_multi := (k \\ge 8) \\land (L_q \\ge 80)
\\lfloor 1.85 \\cdot L_q \\rfloor
\\text{overlap} \\ge 0.55
\\text{ratio} \\ge 0.70
        """.strip(),
        encoding="utf-8",
    )
    (docs_root / "architecture" / "code_architecture.md").write_text(
        "Other heading\n",
        encoding="utf-8",
    )
    (docs_root / "architecture" / "diagrams.md").write_text(
        "Different heading\n",
        encoding="utf-8",
    )
    errors = module._validate_tm_long_variant_contract(docs_root)
    assert errors
    assert any("missing TM long-variant diagram anchor" in err for err in errors)


def test_v09_spec_contract_requires_required_snippets(tmp_path: Path) -> None:
    """v0.9 spec pages must include required headings/snippets."""
    module = _load_docs_contract_module()
    docs_root = tmp_path / "docs"
    (docs_root / "spec" / "v0_9").mkdir(parents=True, exist_ok=True)
    (docs_root / "spec" / "v0_9" / "qa_live_checklist.md").write_text(
        "# QA\n", encoding="utf-8"
    )
    (docs_root / "spec" / "v0_9" / "tm_quality_explainability.md").write_text(
        "# TM\n", encoding="utf-8"
    )
    (docs_root / "spec" / "v0_9" / "crash_recovery_uc12.md").write_text(
        "# CR\n", encoding="utf-8"
    )
    (docs_root / "spec" / "v0_9" / "implementation_subtasks.md").write_text(
        "# Subtasks\n", encoding="utf-8"
    )
    errors = module._validate_v09_spec_contract(docs_root)
    assert errors
    assert any("missing required v0.9 spec contract snippet" in err for err in errors)


def test_api_structure_contract_requires_standard_sections(tmp_path: Path) -> None:
    """API pages must provide why/when-not/call-chain/dto/failure sections."""
    module = _load_docs_contract_module()
    docs_root = tmp_path / "docs"
    (docs_root / "reference" / "api").mkdir(parents=True, exist_ok=True)
    for rel in module.API_STRUCTURE_PAGES:
        path = docs_root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# API\n", encoding="utf-8")
    errors = module._validate_api_structure_contract(docs_root)
    assert errors
    assert any("missing required API structure section" in err for err in errors)


def test_active_plan_drift_detects_stale_v08_pending_language(tmp_path: Path) -> None:
    """Active docs must not present v0.8 as pending/in-progress release state."""
    module = _load_docs_contract_module()
    docs_root = tmp_path / "docs"
    (docs_root / "plan").mkdir(parents=True, exist_ok=True)
    (docs_root / "operations").mkdir(parents=True, exist_ok=True)
    (docs_root / "plan" / "implementation_active.md").write_text(
        "v0.8.0 in progress\n",
        encoding="utf-8",
    )
    (docs_root / "operations" / "checklists.md").write_text(
        "v0.8.0 release gate (next target)\n",
        encoding="utf-8",
    )
    (docs_root / "plan" / "implementation_history.md").write_text(
        "Pending before final tag\n",
        encoding="utf-8",
    )
    errors = module._validate_active_plan_drift(docs_root)
    assert errors
    assert any("stale release-state wording" in err for err in errors)


def test_module_map_coverage_detects_missing_entries(tmp_path: Path) -> None:
    """Module map coverage should fail when repo modules are not listed."""
    module = _load_docs_contract_module()
    repo_root = tmp_path / "repo"
    docs_root = repo_root / "docs"
    (docs_root / "reference").mkdir(parents=True, exist_ok=True)
    (repo_root / "translationzed_py" / "core").mkdir(parents=True, exist_ok=True)
    (repo_root / "translationzed_py" / "gui").mkdir(parents=True, exist_ok=True)
    (repo_root / "translationzed_py" / "core" / "__init__.py").write_text(
        "", encoding="utf-8"
    )
    (repo_root / "translationzed_py" / "gui" / "__init__.py").write_text(
        "", encoding="utf-8"
    )
    (repo_root / "translationzed_py" / "core" / "alpha.py").write_text(
        "x = 1\n", encoding="utf-8"
    )
    (repo_root / "translationzed_py" / "gui" / "beta.py").write_text(
        "x = 1\n", encoding="utf-8"
    )
    (docs_root / "reference" / "module_map.md").write_text(
        "| Module | Responsibility |\n|---|---|\n| `core.model` | sample |\n",
        encoding="utf-8",
    )
    errors = module._validate_module_map_coverage(docs_root, repo_root)
    assert errors
    assert any("core.alpha" in err for err in errors)
    assert any("gui.beta" in err for err in errors)


def test_module_map_coverage_passes_when_entries_exist(tmp_path: Path) -> None:
    """Module map coverage should pass when all modules are represented."""
    module = _load_docs_contract_module()
    repo_root = tmp_path / "repo"
    docs_root = repo_root / "docs"
    (docs_root / "reference").mkdir(parents=True, exist_ok=True)
    (repo_root / "translationzed_py" / "core").mkdir(parents=True, exist_ok=True)
    (repo_root / "translationzed_py" / "gui").mkdir(parents=True, exist_ok=True)
    (repo_root / "translationzed_py" / "core" / "__init__.py").write_text(
        "", encoding="utf-8"
    )
    (repo_root / "translationzed_py" / "gui" / "__init__.py").write_text(
        "", encoding="utf-8"
    )
    (repo_root / "translationzed_py" / "core" / "alpha.py").write_text(
        "x = 1\n", encoding="utf-8"
    )
    (repo_root / "translationzed_py" / "gui" / "beta.py").write_text(
        "x = 1\n", encoding="utf-8"
    )
    (docs_root / "reference" / "module_map.md").write_text(
        "| Module | Responsibility |\n"
        "|---|---|\n"
        "| `core.alpha` | sample |\n"
        "| `gui.beta` | sample |\n",
        encoding="utf-8",
    )
    errors = module._validate_module_map_coverage(docs_root, repo_root)
    assert errors == []


def test_workflow_api_surface_detects_missing_coverage(tmp_path: Path) -> None:
    """Workflow API surface should fail when critical modules are missing."""
    module = _load_docs_contract_module()
    docs_root = tmp_path / "docs"
    (docs_root / "reference" / "api").mkdir(parents=True, exist_ok=True)
    (docs_root / "reference" / "api" / "core_workflows.md").write_text(
        "# Core Workflows API\n::: translationzed_py.core.project_session\n",
        encoding="utf-8",
    )
    errors = module._validate_workflow_api_surface(docs_root)
    assert errors
    assert any("missing workflow module coverage" in err for err in errors)
    assert any("missing mkdocstrings API block" in err for err in errors)


def test_workflow_api_surface_passes_for_required_modules(tmp_path: Path) -> None:
    """Workflow API surface should pass when all critical modules are present."""
    module = _load_docs_contract_module()
    docs_root = tmp_path / "docs"
    (docs_root / "reference" / "api").mkdir(parents=True, exist_ok=True)
    lines = ["# Core Workflows API"]
    for name in module.WORKFLOW_CRITICAL_MODULES:
        lines.append(f"`{name}`")
        lines.append(f"::: translationzed_py.core.{name}")
    (docs_root / "reference" / "api" / "core_workflows.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )
    errors = module._validate_workflow_api_surface(docs_root)
    assert errors == []


def test_quick_context_orientation_links_detect_missing_paths(tmp_path: Path) -> None:
    """Quick context should include orientation surface links."""
    module = _load_docs_contract_module()
    docs_root = tmp_path / "docs"
    (docs_root / "reference").mkdir(parents=True, exist_ok=True)
    (docs_root / "reference" / "quick_context.md").write_text(
        "# Quick Context\n",
        encoding="utf-8",
    )
    errors = module._validate_quick_context_orientation_links(docs_root)
    assert errors
    assert any("missing orientation surface link" in err for err in errors)


def test_quick_context_orientation_links_pass_with_paths(tmp_path: Path) -> None:
    """Quick context should pass when orientation links are present."""
    module = _load_docs_contract_module()
    docs_root = tmp_path / "docs"
    (docs_root / "reference").mkdir(parents=True, exist_ok=True)
    content = (
        "# Quick Context\n"
        "docs/reference/automation_surface.md\n"
        "docs/reference/test_surface.md\n"
    )
    (docs_root / "reference" / "quick_context.md").write_text(
        content,
        encoding="utf-8",
    )
    errors = module._validate_quick_context_orientation_links(docs_root)
    assert errors == []
