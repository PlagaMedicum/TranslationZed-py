"""Test module for app config loading and diff settings."""

from __future__ import annotations

from pathlib import Path

import translationzed_py.core.app_config as app_config


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
""".strip() + "\n",
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
""".strip() + "\n",
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
""".strip() + "\n",
    )
    cfg = app_config.load(tmp_path)
    assert cfg.insertion_enabled_globs == ("*.txt",)
    assert cfg.preview_context_lines == 3


def test_candidate_roots_none_and_dedup(tmp_path: Path, monkeypatch) -> None:
    """Candidate roots should include cwd and deduplicate duplicates."""
    monkeypatch.chdir(tmp_path)
    roots_none = app_config._candidate_roots(None)
    assert roots_none == [tmp_path.resolve()]

    roots_dup = app_config._candidate_roots(tmp_path)
    assert roots_dup == [tmp_path.resolve()]


def test_load_toml_handles_oserror(tmp_path: Path, monkeypatch) -> None:
    """TOML loader should safely return empty payload when read fails."""
    cfg_file = tmp_path / "config" / "app.toml"
    cfg_file.parent.mkdir(parents=True, exist_ok=True)
    cfg_file.write_text("[diff]\npreview_context_lines = 3\n", encoding="utf-8")

    def _raise_oserror(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise OSError("blocked")

    monkeypatch.setattr(Path, "read_text", _raise_oserror)
    assert app_config._load_toml(cfg_file) == {}


def test_normalize_globs_string_input() -> None:
    """String glob payload should normalize to one-item tuple."""
    assert app_config._normalize_globs(" *.cfg ", default=("*.txt",)) == ("*.cfg",)


def test_load_ignores_non_dict_sections(tmp_path: Path) -> None:
    """Non-dict top-level config sections should be ignored safely."""
    app_config.load.cache_clear()
    _write_config(
        tmp_path,
        """
paths = "bad"
cache = "bad"
adapters = "bad"
formats = "bad"
diff = "bad"
""".strip() + "\n",
    )
    cfg = app_config.load(tmp_path)
    assert cfg.cache_dir == ".tzp/cache"
    assert cfg.config_dir == ".tzp/config"
    assert cfg.cache_ext == ".bin"
    assert cfg.translation_ext == ".txt"
