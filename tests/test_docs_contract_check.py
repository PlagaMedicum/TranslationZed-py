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
