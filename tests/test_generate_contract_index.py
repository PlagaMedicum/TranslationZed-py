"""Regression tests for targeted contract-context generation."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest


def _load_module() -> ModuleType:
    script_path = (
        Path(__file__).resolve().parents[1] / "scripts/generate_contract_index.py"
    )
    spec = importlib.util.spec_from_file_location(
        "generate_contract_index", script_path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[misc]
    return module


def _sample_repo(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    module_path = repo / "translationzed_py/core/sample.py"
    module_path.parent.mkdir(parents=True)
    module_path.write_text(
        '''"""Sample module."""

def run(value: int) -> int:
    """Return a value.

    Preconditions:
    value is non-negative.
    """
    return value

def _private() -> None:
    """Internal helper."""

class Worker:
    """Public worker."""

    def execute(self) -> None:
        """Execute work."""

    def _reset(self) -> None:
        """Reset work."""
''',
        encoding="utf-8",
    )
    return repo, module_path


def test_build_contract_index_is_targeted_and_deterministic(tmp_path: Path) -> None:
    """Only selected modules should appear in stable source order."""
    module = _load_module()
    repo, module_path = _sample_repo(tmp_path)
    payload = module.build_contract_index(
        repo_root=repo,
        module_paths=[module_path, module_path],
    )
    assert payload["schema_version"] == 2
    assert [row["module"] for row in payload["modules"]] == [
        "translationzed_py.core.sample"
    ]
    names = [row["name"] for row in payload["modules"][0]["symbols"]]
    assert names == ["run", "_private", "Worker", "Worker.execute", "Worker._reset"]
    assert payload["modules"][0]["symbols"][0]["contracts"] == {
        "Preconditions": "value is non-negative."
    }


def test_public_only_excludes_private_symbols(tmp_path: Path) -> None:
    """Public-only mode should omit private functions and members."""
    module = _load_module()
    repo, module_path = _sample_repo(tmp_path)
    payload = module.build_contract_index(
        repo_root=repo,
        module_paths=[module_path],
        public_only=True,
    )
    names = [row["name"] for row in payload["modules"][0]["symbols"]]
    assert names == ["run", "Worker", "Worker.execute"]


def test_resolve_module_path_accepts_dotted_name_and_rejects_escape(
    tmp_path: Path,
) -> None:
    """Module selection must remain explicit and inside the repository."""
    module = _load_module()
    repo, module_path = _sample_repo(tmp_path)
    assert (
        module.resolve_module_path(repo, "translationzed_py.core.sample") == module_path
    )
    with pytest.raises(ValueError, match="escapes repository root"):
        module.resolve_module_path(repo, "../outside.py")
