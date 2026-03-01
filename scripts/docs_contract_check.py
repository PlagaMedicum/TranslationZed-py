#!/usr/bin/env python3
"""Validate documentation coherency and stale-terminology contracts."""

from __future__ import annotations

import argparse
import html
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PatternRule:
    """One banned-pattern rule scoped to canonical docs."""

    pattern: re.Pattern[str]
    reason: str


CANONICAL_DOCS = [
    "index.md",
    "meta/docs_structure.md",
    "reference/quick_context.md",
    "reference/module_map.md",
    "reference/contract_index.md",
    "reference/review_queue.md",
    "spec/technical.md",
    "ux/use_cases.md",
    "architecture/overview.md",
    "architecture/code_architecture.md",
    "architecture/flows.md",
    "architecture/diagrams.md",
    "domain/tm_ranking.md",
    "quality/assurance_standard.md",
    "quality/testing_strategy.md",
    "operations/checklists.md",
    "performance/math_appendix.md",
    "plan/implementation_active.md",
    "plan/implementation_history.md",
    "reference/api/index.md",
    "reference/api/core_workflows.md",
    "reference/api/core_data_io.md",
    "reference/api/core_preferences.md",
]

CANONICAL_SCAN_SCOPE = [
    "index.md",
    "meta/docs_structure.md",
    "reference/quick_context.md",
    "reference/module_map.md",
    "reference/contract_index.md",
    "reference/review_queue.md",
    "spec/technical.md",
    "ux/use_cases.md",
    "architecture/overview.md",
    "architecture/code_architecture.md",
    "architecture/flows.md",
    "architecture/diagrams.md",
    "domain/tm_ranking.md",
    "quality/assurance_standard.md",
    "quality/testing_strategy.md",
    "operations/checklists.md",
    "performance/math_appendix.md",
    "plan/implementation_active.md",
    "reference/api/index.md",
    "reference/api/core_workflows.md",
    "reference/api/core_data_io.md",
    "reference/api/core_preferences.md",
]

RENDERED_HTML_SCAN_SCOPE = [
    "quality/testing_strategy.md",
    "quality/assurance_standard.md",
    "operations/checklists.md",
    "plan/implementation_active.md",
    "plan/implementation_history.md",
]

BANNED_RULES = [
    PatternRule(
        pattern=re.compile(
            r"LanguageTool integration \(explicitly deferred\)", re.IGNORECASE
        ),
        reason="LanguageTool is implemented; deferred wording is stale.",
    ),
    PatternRule(
        pattern=re.compile(r"Project\s*▸\s*Open", re.IGNORECASE),
        reason="Menu wording must match current UI label: General -> Open.",
    ),
    PatternRule(
        pattern=re.compile(r"Project\s*▸\s*Switch\s*Locale", re.IGNORECASE),
        reason="Menu wording must match current UI label: General -> Switch Locale(s).",
    ),
    PatternRule(
        pattern=re.compile(r"Click\s*\*\*Files\*\*", re.IGNORECASE),
        reason="Left tab is Project, not Files.",
    ),
    PatternRule(
        pattern=re.compile(r"technical_notes_current_state", re.IGNORECASE),
        reason="Retired notes doc must not be referenced from canonical docs.",
    ),
    PatternRule(
        pattern=re.compile(
            r"translation_zed_py_technical_specification\.md", re.IGNORECASE
        ),
        reason="Legacy technical spec path detected.",
    ),
    PatternRule(
        pattern=re.compile(
            r"translation_zed_py_use_case_ux_specification\.md", re.IGNORECASE
        ),
        reason="Legacy UX spec path detected.",
    ),
    PatternRule(
        pattern=re.compile(r"docs/implementation_plan\.md", re.IGNORECASE),
        reason="Legacy implementation plan path detected.",
    ),
    PatternRule(
        pattern=re.compile(r"docs/testing_strategy\.md", re.IGNORECASE),
        reason="Legacy testing strategy path detected.",
    ),
    PatternRule(
        pattern=re.compile(r"docs/checklists\.md", re.IGNORECASE),
        reason="Legacy checklists path detected.",
    ),
    PatternRule(
        pattern=re.compile(r"docs/tm_ranking_algorithm\.md", re.IGNORECASE),
        reason="Legacy TM ranking path detected.",
    ),
    PatternRule(
        pattern=re.compile(r"docs/performance_math_appendix\.md", re.IGNORECASE),
        reason="Legacy performance appendix path detected.",
    ),
    PatternRule(
        pattern=re.compile(r"Static fallback", re.IGNORECASE),
        reason="Fallback diagram sections are disallowed in canonical docs.",
    ),
    PatternRule(
        pattern=re.compile(r"!\[[^\]]*\]\(\.\./diagrams/static/[^)]+\)"),
        reason="Inline fallback image embeds are disallowed in canonical docs.",
    ),
]

PROHIBITED_NORMALIZATION_PATTERNS = [
    re.compile(r"\bno issues found\b", re.IGNORECASE),
    re.compile(r"\bnothing to refactor\b", re.IGNORECASE),
    re.compile(r"\bfully robust\b", re.IGNORECASE),
    re.compile(r"\bacceptable as[- ]is\b", re.IGNORECASE),
    re.compile(r"\bproduction-perfect\b", re.IGNORECASE),
]

TM_LONG_VARIANT_FORMULA_SNIPPETS = (
    "TM Long-Variant Detection Contract",
    r"L_{\text{min\_base}} = \max(1,\lfloor 0.6 \cdot L_q \rfloor)",
    r"is\_long\_multi := (k \ge 8) \land (L_q \ge 80)",
    r"\lfloor 1.85 \cdot L_q \rfloor",
    r"\text{overlap} \ge 0.55",
    r"\text{ratio} \ge 0.70",
)

TM_LONG_VARIANT_DIAGRAM_ANCHORS = (
    ("architecture/code_architecture.md", "TM Long-Variant Detection Pipeline"),
    ("architecture/diagrams.md", "TM Long-Variant Detection Activity"),
)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _validate_file_presence(docs_root: Path) -> list[str]:
    errors: list[str] = []
    for rel in CANONICAL_DOCS:
        path = docs_root / rel
        if not path.is_file():
            errors.append(f"missing canonical doc: {path}")
    return errors


def _validate_patterns(docs_root: Path) -> list[str]:
    errors: list[str] = []
    for rel in CANONICAL_SCAN_SCOPE:
        path = docs_root / rel
        if not path.is_file():
            continue
        text = _read_text(path)
        for rule in BANNED_RULES:
            if rule.pattern.search(text):
                errors.append(f"{path}: {rule.reason}")
    return errors


def _validate_normalization_phrasing(docs_root: Path) -> list[str]:
    errors: list[str] = []
    exempt = {"quality/assurance_standard.md"}
    for rel in CANONICAL_SCAN_SCOPE:
        if rel in exempt:
            continue
        path = docs_root / rel
        if not path.is_file():
            continue
        text = _read_text(path)
        for pattern in PROHIBITED_NORMALIZATION_PATTERNS:
            if pattern.search(text):
                errors.append(
                    f"{path}: normalization language is disallowed ({pattern.pattern})"
                )
    return errors


def _validate_mathjax_markers(docs_root: Path) -> list[str]:
    errors: list[str] = []
    math_doc = docs_root / "performance/math_appendix.md"
    if not math_doc.is_file():
        return errors
    text = _read_text(math_doc)
    if "$$" not in text and "$" not in text:
        errors.append(
            f"{math_doc}: expected TeX markers ($...$ or $$...$$) for MathJax rendering"
        )
    return errors


def _validate_math_source_sanity(docs_root: Path) -> list[str]:
    errors: list[str] = []
    math_doc = docs_root / "performance/math_appendix.md"
    if not math_doc.is_file():
        return errors
    text = _read_text(math_doc)
    if text.count("$$") % 2 != 0:
        errors.append(
            f"{math_doc}: unmatched display-math delimiters ('$$' count must be even)"
        )
    broken_patterns = [
        re.compile(r"\$\$[^$\n]*\$\$[}\]]"),
        re.compile(r"\\frac\{[^}\n]*\$\$"),
        re.compile(r"\$\$[^$\n]*\{\\text\{legacy\}\}[^$\n]*\$\$\}"),
    ]
    for pattern in broken_patterns:
        if pattern.search(text):
            errors.append(
                f"{math_doc}: malformed TeX block detected ({pattern.pattern})"
            )
    return errors


def _validate_diagram_assets(docs_root: Path) -> list[str]:
    errors: list[str] = []
    required = [
        "diagrams/static/system-context.svg",
        "diagrams/static/layered-architecture.svg",
        "diagrams/static/save-flow.svg",
        "diagrams/static/module-dependency-map.svg",
        "diagrams/src/layered_architecture.puml",
        "diagrams/src/gui_controller_domain_map.puml",
        "diagrams/src/module_dependency_dense.puml",
        "diagrams/src/core_service_contracts_dense.puml",
        "diagrams/src/gui_controller_adapters_dense.puml",
    ]
    for rel in required:
        path = docs_root / rel
        if not path.is_file():
            errors.append(f"missing diagram artifact/source: {path}")
    return errors


def _load_review_queue(docs_root: Path) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    queue_path = docs_root / "reference/review_queue.json"
    if not queue_path.is_file():
        return None, [f"missing review queue artifact: {queue_path}"]
    try:
        payload = json.loads(_read_text(queue_path))
    except json.JSONDecodeError as exc:
        return None, [f"invalid review queue JSON: {queue_path}: {exc}"]
    if not isinstance(payload, dict):
        return None, [f"review queue root must be object: {queue_path}"]
    if not isinstance(payload.get("version"), int):
        errors.append(f"{queue_path}: `version` must be integer")
    entries = payload.get("entries")
    if not isinstance(entries, list):
        errors.append(f"{queue_path}: `entries` must be a list")
    return payload, errors


def _validate_review_queue_refs(docs_root: Path) -> list[str]:
    errors: list[str] = []
    payload, queue_errors = _load_review_queue(docs_root)
    errors.extend(queue_errors)
    if payload is None or not isinstance(payload.get("entries"), list):
        return errors

    active_statuses = {"REVIEW_REQUIRED", "IN_REFACTOR"}
    active_paths: set[str] = set()
    for idx, entry in enumerate(payload["entries"]):
        if not isinstance(entry, dict):
            errors.append(f"review_queue entry[{idx}] must be object")
            continue
        module_path = entry.get("module_path")
        status = entry.get("status")
        if not isinstance(module_path, str):
            errors.append(f"review_queue entry[{idx}] missing string module_path")
            continue
        if status in active_statuses:
            active_paths.add(module_path)

    if not active_paths:
        return errors

    code_arch = docs_root / "architecture/code_architecture.md"
    if not code_arch.is_file():
        errors.append(f"missing code architecture doc: {code_arch}")
        return errors
    arch_text = _read_text(code_arch)
    for module_path in sorted(active_paths):
        marker = f"FLAGGED_MODULE: {module_path}"
        if marker not in arch_text:
            errors.append(
                f"{code_arch}: missing flagged-module marker for active queue entry: {marker}"
            )

    api_docs = sorted((docs_root / "reference" / "api").glob("*.md"))
    for module_path in sorted(active_paths):
        dotted = module_path.removesuffix(".py").replace("/", ".")
        matching = [path for path in api_docs if dotted in _read_text(path)]
        if not matching:
            errors.append(
                "flagged module must remain visible in API docs with warning: "
                f"{module_path}"
            )
            continue
        warning_found = any(
            re.search(r"flagged for deep review", _read_text(path), re.IGNORECASE)
            for path in matching
        )
        if not warning_found:
            errors.append(
                "flagged module API docs must include warning text "
                f"'flagged for deep review': {module_path}"
            )
    return errors


def _validate_contract_index_artifacts(docs_root: Path) -> list[str]:
    errors: list[str] = []
    index_json = docs_root / "reference/contract_index.json"
    index_md = docs_root / "reference/contract_index.md"
    if not index_json.is_file():
        errors.append(f"missing contract index artifact: {index_json}")
    if not index_md.is_file():
        errors.append(f"missing contract index wrapper doc: {index_md}")
    elif "contract_index.json" not in _read_text(index_md):
        errors.append(f"{index_md}: must reference contract_index.json")
    return errors


def _validate_required_headings(docs_root: Path) -> list[str]:
    errors: list[str] = []
    technical = docs_root / "spec/technical.md"
    if technical.is_file():
        text = _read_text(technical)
        if not re.search(
            r"^###?\s+(?:\d+(?:\.\d+)*\s+)?Programming Paradigm and Architectural Style\s*$",
            text,
            flags=re.MULTILINE,
        ):
            errors.append(
                f"{technical}: missing required heading "
                "'Programming Paradigm and Architectural Style'"
            )
    return errors


def _validate_tm_long_variant_contract(docs_root: Path) -> list[str]:
    errors: list[str] = []
    tm_doc = docs_root / "domain/tm_ranking.md"
    if not tm_doc.is_file():
        return errors
    tm_text = _read_text(tm_doc)
    for snippet in TM_LONG_VARIANT_FORMULA_SNIPPETS:
        if snippet not in tm_text:
            errors.append(
                f"{tm_doc}: missing TM long-variant contract snippet: {snippet!r}"
            )

    for rel, anchor in TM_LONG_VARIANT_DIAGRAM_ANCHORS:
        path = docs_root / rel
        if not path.is_file():
            errors.append(f"missing TM long-variant diagram doc: {path}")
            continue
        text = _read_text(path)
        if anchor not in text:
            errors.append(f"{path}: missing TM long-variant diagram anchor: {anchor!r}")
    return errors


def _validate_mkdocs_contract(repo_root: Path) -> list[str]:
    errors: list[str] = []
    configs = [repo_root / "mkdocs.yml", repo_root / "mkdocs.fallback.yml"]
    for mkdocs_path in configs:
        if not mkdocs_path.is_file():
            errors.append(f"missing mkdocs config: {mkdocs_path}")
            continue
        text = _read_text(mkdocs_path)
        required_snippets = [
            "use_directory_urls: false",
            "Code Architecture: architecture/code_architecture.md",
            "Assurance Standard: quality/assurance_standard.md",
            "API Overview: reference/api/index.md",
            "mermaid.min.js",
            "tex-mml-chtml.js",
        ]
        for snippet in required_snippets:
            if snippet not in text:
                errors.append(
                    f"{mkdocs_path}: missing required docs-rendering contract snippet: {snippet!r}"
                )
    main_mkdocs_path = repo_root / "mkdocs.yml"
    if main_mkdocs_path.is_file():
        main_text = _read_text(main_mkdocs_path)
        for snippet in (
            "name: material",
            "pymdownx.superfences",
            "name: mermaid",
            "pymdownx.arithmatex",
            "mkdocstrings",
        ):
            if snippet not in main_text:
                errors.append(
                    f"{main_mkdocs_path}: missing required docs-rendering "
                    f"contract snippet: {snippet!r}"
                )
    return errors


def _canonical_html_rel(markdown_rel: str) -> str:
    if markdown_rel == "index.md":
        return "index.html"
    return markdown_rel.removesuffix(".md") + ".html"


def _paragraph_texts_from_html(raw_html: str) -> list[str]:
    texts: list[str] = []
    for block in re.findall(
        r"<p\b[^>]*>(.*?)</p>", raw_html, flags=re.DOTALL | re.IGNORECASE
    ):
        without_tags = re.sub(r"<[^>]+>", "", block)
        normalized = " ".join(html.unescape(without_tags).split())
        if normalized:
            texts.append(normalized)
    return texts


def _looks_like_pseudo_list_paragraph(text: str) -> bool:
    if text.startswith(("- ", "* ", "- [", "* [")):
        return True
    if re.search(r"(?:^|\s)-\s\[[^\]]+\]", text):
        return True
    return bool(": - " in text and text.count(" - ") >= 2)


def _validate_rendered_html_shape(site_root: Path) -> list[str]:
    errors: list[str] = []
    if not site_root.is_dir():
        return [f"rendered site root not found: {site_root}"]
    for rel in RENDERED_HTML_SCAN_SCOPE:
        html_rel = _canonical_html_rel(rel)
        html_path = site_root / html_rel
        if not html_path.is_file():
            errors.append(f"missing rendered canonical page: {html_path}")
            continue
        page = _read_text(html_path)
        for paragraph in _paragraph_texts_from_html(page):
            if _looks_like_pseudo_list_paragraph(paragraph):
                preview = paragraph[:120]
                errors.append(
                    f"{html_path}: pseudo-list paragraph detected "
                    f"(expected <li>): {preview}"
                )
                break
    return errors


def main() -> int:
    """Run documentation contract checks and return process exit code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docs-root", default="docs", help="Documentation root path")
    parser.add_argument(
        "--site-root",
        default="artifacts/docs/site",
        help="Rendered docs site root for HTML structure checks",
    )
    args = parser.parse_args()

    docs_root = Path(args.docs_root)
    site_root = Path(args.site_root)
    if not docs_root.is_dir():
        print(f"error: docs root not found: {docs_root}")
        return 2

    errors: list[str] = []
    errors.extend(_validate_file_presence(docs_root))
    errors.extend(_validate_patterns(docs_root))
    errors.extend(_validate_normalization_phrasing(docs_root))
    errors.extend(_validate_mathjax_markers(docs_root))
    errors.extend(_validate_math_source_sanity(docs_root))
    errors.extend(_validate_diagram_assets(docs_root))
    errors.extend(_validate_review_queue_refs(docs_root))
    errors.extend(_validate_contract_index_artifacts(docs_root))
    errors.extend(_validate_required_headings(docs_root))
    errors.extend(_validate_tm_long_variant_contract(docs_root))
    errors.extend(_validate_mkdocs_contract(Path.cwd()))
    errors.extend(_validate_rendered_html_shape(site_root))

    if errors:
        print("docs-contract-check: FAIL")
        for err in errors:
            print(f" - {err}")
        return 1

    print("docs-contract-check: PASS")
    print(f"checked canonical docs under: {docs_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
