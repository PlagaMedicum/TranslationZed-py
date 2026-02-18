"""Architecture guard checks for GUI/core boundary and file-size policies."""

from __future__ import annotations

import ast
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BoundaryRule:
    """Define allowed imports and a maximum line budget for one file."""

    allowed_core_modules: frozenset[str]
    max_lines: int


DEFAULT_RULES: dict[str, BoundaryRule] = {
    "translationzed_py/gui/main_window.py": BoundaryRule(
        allowed_core_modules=frozenset(
            {
                "translationzed_py.core",
                "translationzed_py.core.app_config",
                "translationzed_py.core.conflict_service",
                "translationzed_py.core.en_hash_cache",
                "translationzed_py.core.file_workflow",
                "translationzed_py.core.model",
                "translationzed_py.core.preferences_service",
                "translationzed_py.core.project_session",
                "translationzed_py.core.qa_service",
                "translationzed_py.core.render_workflow_service",
                "translationzed_py.core.save_exit_flow",
                "translationzed_py.core.saver",
                "translationzed_py.core.search",
                "translationzed_py.core.search_replace_service",
                "translationzed_py.core.source_reference_service",
                "translationzed_py.core.status_cache",
                "translationzed_py.core.tm_import_sync",
                "translationzed_py.core.tm_query",
                "translationzed_py.core.tm_rebuild",
                "translationzed_py.core.tm_store",
                "translationzed_py.core.tm_workflow_service",
            }
        ),
        # Growth watchdog until the remaining extraction slices land.
        max_lines=5600,
    )
}


def collect_core_modules(source: str) -> set[str]:
    """Collect imported `translationzed_py.core*` module names from source."""
    tree = ast.parse(source)
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("translationzed_py.core"):
                    modules.add(alias.name)
            continue
        if isinstance(node, ast.ImportFrom):
            module = node.module
            if module and module.startswith("translationzed_py.core"):
                modules.add(module)
    return modules


def check_file(path: Path, rule: BoundaryRule) -> list[str]:
    """Validate one file against its boundary rule and line-budget limits."""
    if not path.exists():
        return [f"{path}: missing file for architecture guard check."]
    source = path.read_text(encoding="utf-8")
    violations: list[str] = []
    try:
        modules = collect_core_modules(source)
    except SyntaxError as exc:
        return [f"{path}: cannot parse imports ({exc.msg})."]
    disallowed = sorted(
        module for module in modules if module not in rule.allowed_core_modules
    )
    if disallowed:
        violations.append(f"{path}: disallowed core imports: {', '.join(disallowed)}")
    line_count = len(source.splitlines())
    if line_count > rule.max_lines:
        violations.append(
            f"{path}: line budget exceeded ({line_count} > {rule.max_lines})"
        )
    return violations


def check_rules(
    root: Path, rules: Mapping[str, BoundaryRule] | None = None
) -> list[str]:
    """Run architecture rules for all guarded files under the given root."""
    active_rules = rules or DEFAULT_RULES
    violations: list[str] = []
    for rel_path, rule in active_rules.items():
        violations.extend(check_file(root / rel_path, rule))
    return violations
