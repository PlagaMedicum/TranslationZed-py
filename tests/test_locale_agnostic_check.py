"""Unit tests for locale-agnostic UI/docs guard script."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def _load_module() -> ModuleType:
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "locale_agnostic_check.py"
    spec = importlib.util.spec_from_file_location("locale_agnostic_check", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[misc]
    return module


def test_detects_locale_biased_ui_placeholder(tmp_path: Path) -> None:
    """Locale-coded placeholder examples in production GUI sinks should fail."""
    module = _load_module()
    repo = tmp_path / "repo"
    path = repo / "translationzed_py" / "gui" / "sample.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """
def build(widget):
    widget.setPlaceholderText("EN,RU")
        """.strip() + "\n",
        encoding="utf-8",
    )
    errors = module.validate_locale_agnostic_contract(repo)
    assert any("concrete locale-code chain example detected" in item for item in errors)


def test_allowlist_marker_skips_intentional_literal(tmp_path: Path) -> None:
    """Narrow allowlist marker should suppress one intentional literal check."""
    module = _load_module()
    repo = tmp_path / "repo"
    path = repo / "translationzed_py" / "gui" / "sample.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """
def build(widget):
    # locale-agnostic: allow
    widget.setPlaceholderText("EN,RU")
        """.strip() + "\n",
        encoding="utf-8",
    )
    errors = module.validate_locale_agnostic_contract(repo)
    assert errors == []


def test_detects_locale_json_example_in_docs(tmp_path: Path) -> None:
    """Canonical docs with concrete locale JSON examples should fail."""
    module = _load_module()
    repo = tmp_path / "repo"
    path = repo / "docs" / "spec" / "technical.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        'Fallback presets example: {"BE":["RU","EN"]}\n',
        encoding="utf-8",
    )
    errors = module.validate_locale_agnostic_contract(repo)
    assert any("concrete locale JSON example detected" in item for item in errors)


def test_tests_and_fixtures_are_exempt_from_guard(tmp_path: Path) -> None:
    """Locale examples in tests/fixtures are allowed and must not fail the guard."""
    module = _load_module()
    repo = tmp_path / "repo"
    test_path = repo / "tests" / "test_sample.py"
    fixture_path = repo / "tests" / "fixtures" / "sample.txt"
    test_path.parent.mkdir(parents=True, exist_ok=True)
    fixture_path.parent.mkdir(parents=True, exist_ok=True)
    test_path.write_text(
        'def test_stub() -> None:\n    assert "EN,RU" == "EN,RU"\n',
        encoding="utf-8",
    )
    fixture_path.write_text('{"BE":["RU","EN"]}\n', encoding="utf-8")
    errors = module.validate_locale_agnostic_contract(repo)
    assert errors == []


def test_passes_for_locale_agnostic_copy(tmp_path: Path) -> None:
    """Generic token placeholders should pass locale-agnostic checks."""
    module = _load_module()
    repo = tmp_path / "repo"
    gui_path = repo / "translationzed_py" / "gui" / "sample.py"
    doc_path = repo / "docs" / "spec" / "technical.md"
    gui_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    gui_path.write_text(
        """
def build(widget):
    widget.setPlaceholderText("<LOCALE_A>,<LOCALE_B>")
    widget.setToolTip(
        "Per-file source-reference override JSON map, for example "
        '{"<RELATIVE_PATH>":"<SOURCE_LOCALE>"}'
    )
        """.strip() + "\n",
        encoding="utf-8",
    )
    doc_path.write_text(
        'Source-reference override example: {"<RELATIVE_PATH>":"<SOURCE_LOCALE>"}\n',
        encoding="utf-8",
    )
    errors = module.validate_locale_agnostic_contract(repo)
    assert errors == []
