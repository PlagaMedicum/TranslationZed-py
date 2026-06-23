"""Contract tests for direct source-reference mode selection."""

from __future__ import annotations

from pathlib import Path

from translationzed_py.core.source_reference_service import (
    normalize_source_reference_mode,
    resolve_source_reference_mode_for_path,
    source_reference_path_key,
)


def test_source_reference_mode_normalization_contract() -> None:
    """Normalize source-reference modes as stable locale tokens."""
    assert normalize_source_reference_mode("target") == "TARGET"
    assert normalize_source_reference_mode(" ko ") == "KO"
    assert normalize_source_reference_mode("", default="EN") == "EN"


def test_source_reference_mode_for_path_prefers_file_override() -> None:
    """Per-file override should win over the default selector mode."""
    root = Path("/tmp/proj")
    path = root / "RU" / "ui.txt"
    key = source_reference_path_key(root, path)
    assert (
        resolve_source_reference_mode_for_path(
            root=root,
            path=path,
            default_mode="EN",
            overrides={key: "KO"},
        )
        == "KO"
    )


def test_source_reference_mode_for_path_uses_default_when_unoverridden() -> None:
    """Default source-reference mode should remain visible when no file override exists."""
    root = Path("/tmp/proj")
    path = root / "RU" / "menu.txt"
    assert (
        resolve_source_reference_mode_for_path(
            root=root,
            path=path,
            default_mode="KO",
            overrides={},
        )
        == "KO"
    )
