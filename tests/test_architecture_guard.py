"""Test module for architecture guard."""

from __future__ import annotations

from pathlib import Path

from translationzed_py.core.architecture_guard import (
    BoundaryRule,
    check_rules,
    collect_core_modules,
)


def test_collect_core_modules_handles_import_and_import_from() -> None:
    """Verify collect core modules handles import and import from."""
    source = """
import os
import translationzed_py.core.search as search_mod
from translationzed_py.core.status_cache import read
from translationzed_py.gui.entry_model import EntryTableModel
"""
    modules = collect_core_modules(source)
    assert modules == {
        "translationzed_py.core.search",
        "translationzed_py.core.status_cache",
    }


def test_check_rules_reports_disallowed_import_and_line_budget(
    tmp_path: Path,
) -> None:
    """Verify check rules reports disallowed import and line budget."""
    target = tmp_path / "translationzed_py" / "gui" / "main_window.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "\n".join(
            [
                "from translationzed_py.core.search import SearchRow",
                "from translationzed_py.core.tmx_io import import_units",
                "x = 1",
                "y = 2",
                "z = 3",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    rules = {
        "translationzed_py/gui/main_window.py": BoundaryRule(
            allowed_core_modules=frozenset({"translationzed_py.core.search"}),
            max_lines=3,
        )
    }
    violations = check_rules(tmp_path, rules)
    assert any("disallowed core imports" in item for item in violations)
    assert any("translationzed_py.core.tmx_io" in item for item in violations)
    assert any("line budget exceeded" in item for item in violations)


def test_check_rules_passes_within_allowlist_and_budget(tmp_path: Path) -> None:
    """Verify check rules passes within allowlist and budget."""
    target = tmp_path / "translationzed_py" / "gui" / "main_window.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "from translationzed_py.core.search import SearchRow\nx = SearchRow\n",
        encoding="utf-8",
    )
    rules = {
        "translationzed_py/gui/main_window.py": BoundaryRule(
            allowed_core_modules=frozenset({"translationzed_py.core.search"}),
            max_lines=20,
        )
    }
    assert check_rules(tmp_path, rules) == []
