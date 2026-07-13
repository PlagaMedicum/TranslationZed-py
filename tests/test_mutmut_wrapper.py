"""Regression tests for the local mutmut wrapper."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


def _load_wrapper_module():
    path = Path("scripts/mutmut_wrapper.py").resolve()
    spec = importlib.util.spec_from_file_location("mutmut_wrapper_module", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_wrapper_treats_click_none_return_as_success(monkeypatch) -> None:
    """Verify wrapper preserves Click success when the command returns None."""
    module = _load_wrapper_module()

    def fake_main(**_: object) -> None:
        return None

    fake_module = types.SimpleNamespace(cli=types.SimpleNamespace(main=fake_main))
    monkeypatch.setattr(module.importlib, "import_module", lambda _: fake_module)
    assert module.main(["results"]) == 0


def test_wrapper_preserves_explicit_system_exit_code(monkeypatch) -> None:
    """Verify wrapper returns the original CLI exit code when Click exits."""
    module = _load_wrapper_module()

    def _raise_exit(**_: object) -> None:
        raise SystemExit(3)

    fake_module = types.SimpleNamespace(cli=types.SimpleNamespace(main=_raise_exit))
    monkeypatch.setattr(module.importlib, "import_module", lambda _: fake_module)
    assert module.main(["run"]) == 3
