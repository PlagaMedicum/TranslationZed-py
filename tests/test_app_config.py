"""Test module for app config loading and diff settings."""

from __future__ import annotations

from pathlib import Path

from translationzed_py.core import app_config


def _write_config(tmp_path: Path, text: str) -> None:
    cfg = tmp_path / "config"
    cfg.mkdir(parents=True, exist_ok=True)
    (cfg / "app.toml").write_text(text, encoding="utf-8")


def test_load_defaults_include_diff_contract(tmp_path: Path) -> None:
    """Verify app config defaults include diff insertion settings."""
    app_config.load.cache_clear()
    cfg = app_config.load(tmp_path)
    assert cfg.insertion_enabled_globs == ("*.txt",)
    assert cfg.preview_context_lines == 3


def test_load_reads_diff_overrides_from_toml(tmp_path: Path) -> None:
    """Verify diff config values are loaded from app.toml."""
    app_config.load.cache_clear()
    _write_config(
        tmp_path,
        """
[diff]
insertion_enabled_globs = ["*.txt", "*.lua"]
preview_context_lines = 5
""".strip()
        + "\n",
    )
    cfg = app_config.load(tmp_path)
    assert cfg.insertion_enabled_globs == ("*.txt", "*.lua")
    assert cfg.preview_context_lines == 5


def test_load_normalizes_diff_values(tmp_path: Path) -> None:
    """Verify diff config normalization deduplicates globs and clamps context."""
    app_config.load.cache_clear()
    _write_config(
        tmp_path,
        """
[diff]
insertion_enabled_globs = ["*.txt", "", "*.txt", " *.cfg "]
preview_context_lines = 99
""".strip()
        + "\n",
    )
    cfg = app_config.load(tmp_path)
    assert cfg.insertion_enabled_globs == ("*.txt", "*.cfg")
    assert cfg.preview_context_lines == 20


def test_load_keeps_default_diff_values_for_invalid_payload(tmp_path: Path) -> None:
    """Verify invalid diff payload keeps safe defaults."""
    app_config.load.cache_clear()
    _write_config(
        tmp_path,
        """
[diff]
insertion_enabled_globs = 1
preview_context_lines = "bad"
""".strip()
        + "\n",
    )
    cfg = app_config.load(tmp_path)
    assert cfg.insertion_enabled_globs == ("*.txt",)
    assert cfg.preview_context_lines == 3
