"""Regression tests for contract index generation."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def _load_module() -> ModuleType:
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "generate_contract_index.py"
    spec = importlib.util.spec_from_file_location(
        "generate_contract_index", script_path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[misc]
    return module


def test_build_contract_index_collects_module_and_symbol(tmp_path: Path) -> None:
    """Contract index builder should collect core module and symbol metadata."""
    module = _load_module()
    repo = tmp_path / "repo"
    scope = repo / "translationzed_py" / "core"
    scope.mkdir(parents=True, exist_ok=True)
    sample = scope / "sample.py"
    sample.write_text(
        '''
"""Sample module doc."""

def run(value: int) -> int:
    """Run sample function.

    Preconditions:
    value is non-negative.
    """
    return value + 1
'''.strip() + "\n",
        encoding="utf-8",
    )
    payload = module.build_contract_index(repo_root=repo, scope_dir=scope)
    assert payload["schema_version"] == 1
    assert payload["modules"]
    first = payload["modules"][0]
    assert first["module"] == "translationzed_py.core.sample"
    assert first["symbols"]
    assert first["symbols"][0]["name"] == "run"
