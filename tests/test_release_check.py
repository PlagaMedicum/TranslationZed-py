"""Test module for release check."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def _load_release_check_module():
    path = Path("scripts/release_check.py").resolve()
    spec = importlib.util.spec_from_file_location("release_check_module", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_normalize_tag_accepts_release_and_rc_forms() -> None:
    """Verify normalize tag accepts release and rc forms."""
    module = _load_release_check_module()
    assert module._normalize_tag("v0.6.0") == ("0.6.0", None)
    assert module._normalize_tag("0.6.0") == ("0.6.0", None)
    assert module._normalize_tag("refs/tags/v0.6.0-rc1") == ("0.6.0", "1")
    assert module._normalize_tag("v0.6.0-RC2") == ("0.6.0", "2")


def test_normalize_tag_rejects_non_release_tags() -> None:
    """Verify normalize tag rejects non release tags."""
    module = _load_release_check_module()
    with pytest.raises(RuntimeError):
        module._normalize_tag("v0.6")
    with pytest.raises(RuntimeError):
        module._normalize_tag("v0.6.0-beta1")
