#!/usr/bin/env python3
"""Validate documentation structure, semantics, and automation coherence."""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import unquote

REQUIRED_ENTRYPOINTS = (
    "index.md",
    "meta/docs_structure.md",
    "reference/quick_context.md",
    "reference/automation_surface.md",
    "reference/test_surface.md",
    "reference/module_map.md",
    "reference/risk_register.md",
    "reference/risk_register.json",
    "spec/technical.md",
    "ux/use_cases.md",
    "architecture/overview.md",
    "quality/testing_strategy.md",
    "operations/checklists.md",
    "plan/implementation_active.md",
    "plan/implementation_history.md",
)

REQUIRED_ACTIVE_PLAN_SECTIONS = (
    "current-objective",
    "constraints",
    "verified-state",
    "acceptance-criteria",
    "open-follow-ups",
)

RETIRED_REFERENCES = (
    "docs/reference/contract_index.json",
    "docs/reference/review_queue.json",
    "docs/reference/review_queue.md",
    "docs/spec/v0_9/implementation_subtasks.md",
    "reference/review_queue.json",
    "reference/review_queue.md",
    "spec/v0_9/implementation_subtasks.md",
)

STALE_PATTERNS = (
    (re.compile(r"\bv0\.9(?:\.0)?\s+target\b", re.IGNORECASE), "v0.9 is current"),
    (
        re.compile(r"\b(?:planned|upcoming)\s+(?:for|in)?\s*`?v0\.9", re.IGNORECASE),
        "implemented v0.9 behavior must not be described as future work",
    ),
    (
        re.compile(r"LanguageTool integration \(explicitly deferred\)", re.IGNORECASE),
        "LanguageTool is implemented",
    ),
    (
        re.compile(r"Project\s*▸\s*(?:Open|Switch\s*Locale)", re.IGNORECASE),
        "menu labels use General, not Project",
    ),
)

SEMANTIC_CONTRACTS: dict[str, tuple[str, ...]] = {
    "spec/technical.md": (
        "byte-preserving",
        "no-write-on-open",
        "locale-specific encoding fidelity",
        "Atomic multi-file save",
        "Security Considerations",
    ),
    "spec/v0_9/qa_live_checklist.md": (
        "Rule State Machine",
        "Formal Progress Model",
        "C(t) =",
        "LanguageTool Failure Semantics",
    ),
    "spec/v0_9/tm_quality_explainability.md": (
        "Preserved Scoring Core (Normative)",
        "Explainability Payload Schema",
        r"raw = \operatorname{round}(100 \cdot ratio)",
        r"L_{\min\_base} = \max(1, \lfloor 0.6 L_q \rfloor)",
        r"\lfloor 1.85 L_q \rfloor",
        r"overlap \ge 0.55",
        r"ratio \ge 0.70",
        "Determinism Guarantees",
    ),
    "spec/v0_9/crash_recovery_uc12.md": (
        "Dialog Contract (Required Actions)",
        "`Restore`",
        "`Discard`",
        "`Cancel`",
        "No-write-on-open",
    ),
    "domain/tm_ranking.md": (
        "TM Long-Variant Detection Contract",
        r"L_{\min b} = \max(1,\lfloor 0.6 \cdot L_q \rfloor)",
        r"I_{\mathrm{long}} := (k \ge 8) \land (L_q \ge 80)",
        r"\lfloor 1.85 \cdot L_q \rfloor",
        r"\text{overlap} \ge 0.55",
        r"\text{ratio} \ge 0.70",
        "Ordering (Tie-Break)",
    ),
    "performance/math_appendix.md": (
        "Parser Model",
        "TM Query Cost Model",
        "Cache-Cap Invariants",
        "Statistical Measurement Contract",
        "Equivalence Proof Obligations",
        r"T_{\text{tm}} =",
        r"\operatorname{MAD}",
    ),
}

API_STRUCTURE_PAGES = (
    "reference/api/core_workflows.md",
    "reference/api/core_data_io.md",
    "reference/api/core_preferences.md",
)

API_REQUIRED_SECTIONS = (
    "Why This Layer Exists",
    "When Not To Use",
    "Call-Chain Examples",
    "DTO Boundaries",
    "Failure Modes",
)

WORKFLOW_CRITICAL_MODULES = (
    "project_session",
    "file_workflow",
    "search_replace_service",
    "qa_service",
    "tm_workflow_service",
    "save_exit_flow",
    "conflict_service",
    "source_reference_service",
)

GATE_POLICY_DOCS = (
    "quality/testing_strategy.md",
    "operations/checklists.md",
    "reference/automation_surface.md",
)

RENDERED_HTML_SCAN_SCOPE = (
    "reference/quick_context.md",
    "reference/automation_surface.md",
    "reference/test_surface.md",
    "quality/testing_strategy.md",
    "quality/assurance_standard.md",
    "operations/checklists.md",
    "plan/implementation_active.md",
    "ux/use_cases.md",
    "ux/use_cases_project_lifecycle.md",
    "ux/use_cases_editing_status.md",
    "ux/use_cases_search_qa.md",
    "ux/use_cases_tm.md",
)

LINK_RE = re.compile(r"!?\[[^\]]*]\(([^)]+)\)")
NAV_PATH_RE = re.compile(r":\s+([A-Za-z0-9_./-]+\.md)\s*$")
HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$")
MAKE_TARGET_RE = re.compile(r"^([A-Za-z0-9_.-]+):", re.MULTILINE)
INLINE_MAKE_RE = re.compile(r"`make\s+([A-Za-z0-9_.-]+)")
LINE_MAKE_RE = re.compile(r"^\s*(?:run:\s*)?make\s+([A-Za-z0-9_.-]+)", re.MULTILINE)
MKDOCSTRINGS_RE = re.compile(
    r"^:::\s+(translationzed_py(?:\.[A-Za-z0-9_]+)+)", re.MULTILINE
)
WORKFLOW_SCRIPT_RE = re.compile(r"\b(?:bash|sh)\s+(scripts/[A-Za-z0-9_./-]+)")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _slugify(value: str) -> str:
    text = re.sub(r"<[^>]+>", "", value)
    text = re.sub(r"[`*_~]", "", text).strip().lower()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    return re.sub(r"[-\s]+", "-", text).strip("-")


def _headings(path: Path) -> set[str]:
    anchors: set[str] = set()
    counts: dict[str, int] = {}
    for line in _read(path).splitlines():
        match = HEADING_RE.match(line)
        if not match:
            continue
        base = _slugify(match.group(1))
        if not base:
            continue
        count = counts.get(base, 0)
        counts[base] = count + 1
        anchors.add(base if count == 0 else f"{base}_{count}")
    return anchors


def _make_targets(path: Path) -> set[str]:
    return set(MAKE_TARGET_RE.findall(_read(path))) if path.is_file() else set()


def validate_entrypoints(docs_root: Path) -> list[str]:
    """Return missing canonical documentation entrypoints."""
    return [
        f"missing documentation entrypoint: {relative}"
        for relative in REQUIRED_ENTRYPOINTS
        if not (docs_root / relative).is_file()
    ]


def validate_navigation(docs_root: Path, config_paths: list[Path]) -> list[str]:
    """Return missing Markdown paths referenced by portal navigation."""
    errors: list[str] = []
    for config in config_paths:
        if not config.is_file():
            errors.append(f"missing documentation config: {config}")
            continue
        for line_number, line in enumerate(_read(config).splitlines(), start=1):
            match = NAV_PATH_RE.search(line)
            if match and not (docs_root / match.group(1)).is_file():
                errors.append(
                    f"{config}:{line_number}: missing nav path {match.group(1)}"
                )
    return errors


def _split_link(raw: str) -> tuple[str, str]:
    target = raw.strip().split(maxsplit=1)[0].strip("<>")
    path, separator, fragment = target.partition("#")
    return unquote(path), unquote(fragment) if separator else ""


def validate_local_links(docs_root: Path) -> list[str]:
    """Return broken local Markdown file and anchor links."""
    errors: list[str] = []
    anchors: dict[Path, set[str]] = {}
    root = docs_root.resolve()
    for source in sorted(docs_root.rglob("*.md")):
        for line_number, line in enumerate(_read(source).splitlines(), start=1):
            for raw in LINK_RE.findall(line):
                path_text, fragment = _split_link(raw)
                if path_text.startswith(("http://", "https://", "mailto:")):
                    continue
                target = (
                    source if not path_text else (source.parent / path_text).resolve()
                )
                try:
                    target.relative_to(root)
                except ValueError:
                    errors.append(
                        f"{source}:{line_number}: local link escapes docs root: {raw}"
                    )
                    continue
                if not target.is_file():
                    errors.append(
                        f"{source}:{line_number}: missing local link target: {raw}"
                    )
                    continue
                if (
                    fragment
                    and target.suffix.lower() == ".md"
                    and fragment not in anchors.setdefault(target, _headings(target))
                ):
                    errors.append(
                        f"{source}:{line_number}: missing anchor #{fragment} in "
                        f"{target.relative_to(docs_root)}"
                    )
    return errors


def validate_active_plan(docs_root: Path) -> list[str]:
    """Return missing structural sections in the active plan."""
    path = docs_root / "plan/implementation_active.md"
    if not path.is_file():
        return [f"missing active plan: {path}"]
    headings = _headings(path)
    return [
        f"{path}: missing required section #{section}"
        for section in REQUIRED_ACTIVE_PLAN_SECTIONS
        if section not in headings
    ]


def _nonempty_strings(value: Any) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(item, str) and item.strip() for item in value)
    )


def validate_risk_register(docs_root: Path, repo_root: Path) -> list[str]:
    """Return active-risk schema and referenced-path errors."""
    path = docs_root / "reference/risk_register.json"
    if not path.is_file():
        return [f"missing active-risk register: {path}"]
    try:
        payload = json.loads(_read(path))
    except json.JSONDecodeError as exc:
        return [f"{path}: invalid JSON: {exc}"]
    errors: list[str] = []
    if payload.get("version") != 2:
        errors.append(f"{path}: version must be 2")
    risks = payload.get("risks")
    if not isinstance(risks, list):
        return errors + [f"{path}: risks must be a list"]
    required = {
        "module_path",
        "status",
        "severity",
        "concern",
        "evidence",
        "constraints",
        "closure_criteria",
        "relevant_tests",
    }
    seen: set[str] = set()
    for index, risk in enumerate(risks):
        prefix = f"{path}: risks[{index}]"
        if not isinstance(risk, dict):
            errors.append(f"{prefix} must be an object")
            continue
        missing = sorted(required - set(risk))
        if missing:
            errors.append(f"{prefix} missing fields: {', '.join(missing)}")
            continue
        module_path = risk["module_path"]
        if not isinstance(module_path, str) or not module_path.endswith(".py"):
            errors.append(f"{prefix}.module_path must be a Python path")
        elif module_path in seen:
            errors.append(f"{prefix}.module_path duplicates {module_path}")
        else:
            seen.add(module_path)
            if not (repo_root / module_path).is_file():
                errors.append(f"{prefix}.module_path does not exist: {module_path}")
        if risk["status"] not in {"monitoring", "refactor_candidate"}:
            errors.append(f"{prefix}.status is invalid")
        if risk["severity"] not in {"medium", "high"}:
            errors.append(f"{prefix}.severity is invalid")
        if not isinstance(risk["concern"], str) or not risk["concern"].strip():
            errors.append(f"{prefix}.concern must be non-empty")
        for field in ("evidence", "constraints", "closure_criteria", "relevant_tests"):
            if not _nonempty_strings(risk[field]):
                errors.append(f"{prefix}.{field} must be non-empty strings")
        if _nonempty_strings(risk["relevant_tests"]):
            for test_path in risk["relevant_tests"]:
                if not (repo_root / test_path).is_file():
                    errors.append(f"{prefix}.relevant_tests missing: {test_path}")
    return errors


def validate_retired_references(docs_root: Path, extra_paths: list[Path]) -> list[str]:
    """Return references to retired documentation artifacts."""
    errors: list[str] = []
    for path in [*sorted(docs_root.rglob("*.md")), *extra_paths]:
        if not path.is_file():
            continue
        text = _read(path)
        for reference in RETIRED_REFERENCES:
            if reference in text:
                errors.append(f"{path}: references retired path {reference}")
    return errors


def validate_stale_language(docs_root: Path) -> list[str]:
    """Return stale lifecycle or implemented-as-future wording."""
    errors: list[str] = []
    excluded = {docs_root / "plan/implementation_history.md"}
    for path in sorted(docs_root.rglob("*.md")):
        if path in excluded:
            continue
        text = _read(path)
        for pattern, reason in STALE_PATTERNS:
            if pattern.search(text):
                errors.append(f"{path}: stale language ({reason})")
    return errors


def validate_semantic_contracts(docs_root: Path) -> list[str]:
    """Return missing safety, formula, state-machine, and API contracts."""
    errors: list[str] = []
    for relative, snippets in SEMANTIC_CONTRACTS.items():
        path = docs_root / relative
        if not path.is_file():
            errors.append(f"missing semantic contract page: {path}")
            continue
        text = _read(path)
        for snippet in snippets:
            if snippet not in text:
                errors.append(f"{path}: missing semantic contract: {snippet!r}")
    for relative in API_STRUCTURE_PAGES:
        path = docs_root / relative
        if not path.is_file():
            errors.append(f"missing API contract page: {path}")
            continue
        text = _read(path)
        for section in API_REQUIRED_SECTIONS:
            if section not in text:
                errors.append(f"{path}: missing API section: {section!r}")
    return errors


def validate_math_source(docs_root: Path) -> list[str]:
    """Return malformed source-level TeX errors."""
    path = docs_root / "performance/math_appendix.md"
    if not path.is_file():
        return [f"missing performance math contract: {path}"]
    text = _read(path)
    errors: list[str] = []
    if text.count("$$") % 2:
        errors.append(f"{path}: unmatched display-math delimiters")
    broken = (
        re.compile(r"\$\$[^$\n]*\$\$[}\]]"),
        re.compile(r"\\frac\{[^}\n]*\$\$"),
    )
    for pattern in broken:
        if pattern.search(text):
            errors.append(f"{path}: malformed TeX block ({pattern.pattern})")
    return errors


def validate_diagram_assets(docs_root: Path) -> list[str]:
    """Return missing maintained diagram sources and static assets."""
    required = (
        "diagrams/static/system-context.svg",
        "diagrams/static/layered-architecture.svg",
        "diagrams/static/save-flow.svg",
        "diagrams/static/module-dependency-map.svg",
        "diagrams/src/layered_architecture.puml",
        "diagrams/src/gui_controller_domain_map.puml",
        "diagrams/src/module_dependency_dense.puml",
        "diagrams/src/core_service_contracts_dense.puml",
        "diagrams/src/gui_controller_adapters_dense.puml",
    )
    return [
        f"missing diagram artifact/source: {docs_root / relative}"
        for relative in required
        if not (docs_root / relative).is_file()
    ]


def validate_module_map(docs_root: Path, repo_root: Path) -> list[str]:
    """Return application modules missing from the ownership map."""
    path = docs_root / "reference/module_map.md"
    if not path.is_file():
        return [f"missing module map: {path}"]
    text = _read(path)
    errors: list[str] = []
    for layer in ("core", "gui"):
        for module in sorted((repo_root / "translationzed_py" / layer).glob("*.py")):
            if module.name == "__init__.py":
                continue
            token = f"{layer}.{module.stem}"
            if token not in text:
                errors.append(f"{path}: missing module ownership for {token}")
    return errors


def validate_source_api_refs(docs_root: Path, repo_root: Path) -> list[str]:
    """Return rendered API references that do not resolve to source modules."""
    errors: list[str] = []
    for path in sorted((docs_root / "reference/api").glob("*.md")):
        for dotted in MKDOCSTRINGS_RE.findall(_read(path)):
            module_path = repo_root / (dotted.replace(".", "/") + ".py")
            if not module_path.is_file():
                errors.append(f"{path}: mkdocstrings module does not exist: {dotted}")
    workflow = docs_root / "reference/api/core_workflows.md"
    text = _read(workflow) if workflow.is_file() else ""
    for module in WORKFLOW_CRITICAL_MODULES:
        if f"::: translationzed_py.core.{module}" not in text:
            errors.append(f"{workflow}: missing workflow API block for {module}")
    return errors


def _documented_make_targets(paths: list[Path]) -> dict[str, set[Path]]:
    references: dict[str, set[Path]] = {}
    for path in paths:
        if not path.is_file():
            continue
        text = _read(path)
        for target in {*INLINE_MAKE_RE.findall(text), *LINE_MAKE_RE.findall(text)}:
            references.setdefault(target, set()).add(path)
    return references


def validate_command_parity(repo_root: Path, docs_root: Path) -> list[str]:
    """Return documented or workflow commands that are not executable."""
    makefile = repo_root / "Makefile"
    targets = _make_targets(makefile)
    paths = [
        repo_root / "README.md",
        *sorted(docs_root.rglob("*.md")),
        *sorted((repo_root / ".github/workflows").glob("*.yml")),
    ]
    errors: list[str] = []
    for target, sources in sorted(_documented_make_targets(paths).items()):
        if target not in targets:
            source_list = ", ".join(
                str(path.relative_to(repo_root)) for path in sorted(sources)
            )
            errors.append(f"documented Make target missing: {target} ({source_list})")
    for workflow in sorted((repo_root / ".github/workflows").glob("*.yml")):
        for script in WORKFLOW_SCRIPT_RE.findall(_read(workflow)):
            if not (repo_root / script).is_file():
                errors.append(f"{workflow}: referenced script does not exist: {script}")
    return errors


def validate_gate_policy(repo_root: Path, docs_root: Path) -> list[str]:
    """Return gate registry, documentation, and script-component drift."""
    path = docs_root / "reference/gate_policy_registry.json"
    if not path.is_file():
        return [f"missing gate policy registry: {path}"]
    try:
        payload = json.loads(_read(path))
    except json.JSONDecodeError as exc:
        return [f"{path}: invalid JSON: {exc}"]
    errors: list[str] = []
    layers = payload.get("layers")
    if payload.get("version") != 1 or not isinstance(layers, list):
        return [f"{path}: expected version 1 with layer list"]
    expected_ids = ("L0", "L1", "L2", "L3", "L4", "L5", "L6")
    ids = tuple(row.get("id") for row in layers if isinstance(row, dict))
    if ids != expected_ids:
        errors.append(f"{path}: layer IDs must be {expected_ids!r}")
    make_targets = _make_targets(repo_root / "Makefile")
    policy_texts = [_read(docs_root / relative) for relative in GATE_POLICY_DOCS]
    for index, row in enumerate(layers):
        if not isinstance(row, dict):
            errors.append(f"{path}: layers[{index}] must be an object")
            continue
        command = row.get("command")
        if not isinstance(command, str) or not command.startswith("make "):
            errors.append(f"{path}: layers[{index}].command must start with make")
            continue
        target = command.split()[1]
        if target not in make_targets:
            errors.append(f"{path}: command target missing from Makefile: {target}")
        for relative, text in zip(GATE_POLICY_DOCS, policy_texts, strict=True):
            if command not in text:
                errors.append(f"{docs_root / relative}: missing gate command {command}")
    required_gate_tokens = {
        "scripts/gates/gate_ci_pr.sh": (
            "test_cov.sh",
            "security.sh",
            "docs_check.sh",
            "test_perf_scale.sh",
        ),
        "scripts/gates/gate_release.sh": (
            "bench_check.sh",
            "test_perf_heavy.sh",
            "test_mutation_stage_internal.sh",
            "release_evidence_check.py",
        ),
    }
    for relative, tokens in required_gate_tokens.items():
        gate = repo_root / relative
        if not gate.is_file():
            errors.append(f"missing gate script: {gate}")
            continue
        text = _read(gate)
        for token in tokens:
            if token not in text:
                errors.append(f"{gate}: missing required gate component {token}")
    return errors


def validate_mkdocs(repo_root: Path, docs_root: Path, configs: list[Path]) -> list[str]:
    """Return missing portal navigation and renderer contracts."""
    errors = validate_navigation(docs_root, configs)
    required = (
        "use_directory_urls: false",
        "reference/automation_surface.md",
        "reference/test_surface.md",
        "reference/risk_register.md",
        "architecture/code_architecture.md",
        "quality/assurance_standard.md",
        "reference/api/index.md",
        "mermaid.min.js",
        "tex-mml-chtml.js",
    )
    for config in configs:
        if not config.is_file():
            continue
        text = _read(config)
        for snippet in required:
            if snippet not in text:
                errors.append(f"{config}: missing docs portal contract {snippet!r}")
    main = repo_root / "mkdocs.yml"
    if main.is_file():
        for snippet in (
            "name: material",
            "pymdownx.superfences",
            "pymdownx.arithmatex",
            "mkdocstrings",
        ):
            if snippet not in _read(main):
                errors.append(f"{main}: missing renderer configuration {snippet!r}")
    return errors


def _canonical_html_rel(markdown_rel: str) -> str:
    return (
        "index.html"
        if markdown_rel == "index.md"
        else markdown_rel.removesuffix(".md") + ".html"
    )


def _looks_like_pseudo_list(text: str) -> bool:
    return bool(
        text.startswith(("- ", "* ", "- [", "* ["))
        or re.search(r"(?:^|\s)-\s\[[^\]]+]", text)
        or (": - " in text and text.count(" - ") >= 2)
        or (
            text.count("|") >= 3
            and re.search(
                r"\|\s*(Field|Value|Trigger|Flow|Goal|Post-condition)\s*\|", text, re.I
            )
        )
    )


def validate_rendered_html(site_root: Path) -> list[str]:
    """Return missing rendered pages and malformed pseudo-list paragraphs."""
    if not site_root.is_dir():
        return [f"rendered site root not found: {site_root}"]
    errors: list[str] = []
    for relative in RENDERED_HTML_SCAN_SCOPE:
        path = site_root / _canonical_html_rel(relative)
        if not path.is_file():
            errors.append(f"missing rendered canonical page: {path}")
            continue
        for block in re.findall(r"<p\b[^>]*>(.*?)</p>", _read(path), re.S | re.I):
            text = " ".join(html.unescape(re.sub(r"<[^>]+>", "", block)).split())
            if text and _looks_like_pseudo_list(text):
                errors.append(f"{path}: pseudo-list paragraph detected: {text[:120]}")
                break
    return errors


def validate_docs(
    *,
    repo_root: Path,
    docs_root: Path,
    config_paths: list[Path],
    site_root: Path | None = None,
) -> list[str]:
    """Run the complete focused documentation assurance suite."""
    errors = [
        *validate_entrypoints(docs_root),
        *validate_local_links(docs_root),
        *validate_active_plan(docs_root),
        *validate_risk_register(docs_root, repo_root),
        *validate_retired_references(docs_root, config_paths),
        *validate_stale_language(docs_root),
        *validate_semantic_contracts(docs_root),
        *validate_math_source(docs_root),
        *validate_diagram_assets(docs_root),
        *validate_module_map(docs_root, repo_root),
        *validate_source_api_refs(docs_root, repo_root),
        *validate_command_parity(repo_root, docs_root),
        *validate_gate_policy(repo_root, docs_root),
        *validate_mkdocs(repo_root, docs_root, config_paths),
    ]
    if site_root is not None:
        errors.extend(validate_rendered_html(site_root))
    return errors


def main() -> int:
    """Run documentation assurance and return a process exit status."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--docs-root", default="docs")
    parser.add_argument("--site-root", default="artifacts/docs/site")
    parser.add_argument("--config", action="append", default=[])
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    docs_root = (repo_root / args.docs_root).resolve()
    site_root = (repo_root / args.site_root).resolve()
    configs = args.config or ["mkdocs.yml", "mkdocs.fallback.yml"]
    config_paths = [(repo_root / value).resolve() for value in configs]
    errors = validate_docs(
        repo_root=repo_root,
        docs_root=docs_root,
        config_paths=config_paths,
        site_root=site_root,
    )
    if errors:
        print("docs-contract-check: FAIL")
        for error in errors:
            print(f" - {error}")
        return 1
    print("docs-contract-check: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
