"""Test module for preferences edge-path coverage."""

from __future__ import annotations

from pathlib import Path

from translationzed_py.core import preferences


def test_runtime_root_uses_executable_parent_when_frozen(
    monkeypatch, tmp_path: Path
) -> None:
    """Verify runtime root resolves from executable directory in frozen mode."""
    fake_executable = tmp_path / "bin" / "app"
    fake_executable.parent.mkdir(parents=True)
    fake_executable.write_text("", encoding="utf-8")

    monkeypatch.setattr(preferences.sys, "frozen", True, raising=False)
    monkeypatch.setattr(
        preferences.sys, "executable", str(fake_executable), raising=False
    )

    assert preferences._runtime_root() == fake_executable.resolve().parent


def test_default_tm_import_dir_matches_canonical_path(tmp_path: Path) -> None:
    """Verify tm import dir default helper returns canonical import directory."""
    assert preferences._default_tm_import_dir(tmp_path) == str(
        (tmp_path / ".tzp" / "tms").resolve()
    )


def test_migrate_legacy_tm_import_dirs_handles_collisions_and_replace_errors(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Verify legacy TM migration handles collisions, non-files, and replace failures."""
    canonical = (tmp_path / ".tzp" / "tms").resolve()
    canonical.mkdir(parents=True, exist_ok=True)
    (canonical / "dup.tmx").write_text("new", encoding="utf-8")

    legacy = (tmp_path / ".tzp" / "imported_tms").resolve()
    legacy.mkdir(parents=True, exist_ok=True)
    (legacy / "nested").mkdir(parents=True, exist_ok=True)
    (legacy / "dup.tmx").write_text("old-dup", encoding="utf-8")
    (legacy / "fail.tmx").write_text("old-fail", encoding="utf-8")

    original_replace = Path.replace

    def _patched_replace(path_obj: Path, dest: Path) -> Path:
        if path_obj.name == "fail.tmx":
            raise OSError("replace failed")
        return original_replace(path_obj, dest)

    monkeypatch.setattr(Path, "replace", _patched_replace)

    changed = preferences._migrate_legacy_tm_import_dirs(tmp_path)

    assert changed is True
    assert (canonical / "dup_1.tmx").exists()
    assert (legacy / "fail.tmx").exists()


def test_parse_env_handles_invalid_lines_false_flags_and_read_errors(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Verify env parser handles malformed lines, false booleans, and read errors."""
    path = tmp_path / "settings.env"
    path.write_text(
        "INVALID_LINE\n"
        "LARGE_TEXT_OPTIMIZATIONS=false\n"
        "PROMPT_WRITE_ON_EXIT=off\n",
        encoding="utf-8",
    )

    parsed = preferences._parse_env(path)
    assert parsed["large_text_optimizations"] is False
    assert parsed["prompt_write_on_exit"] is False

    def _raise_read_text(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise OSError("read failed")

    monkeypatch.setattr(Path, "read_text", _raise_read_text)
    assert preferences._parse_env(path) == {}


def test_save_skips_extras_that_shadow_known_keys(tmp_path: Path) -> None:
    """Verify save ignores extras that reuse known preference key names."""
    prefs = preferences.load(tmp_path)
    prefs["__extras__"] = {
        "WRAP_TEXT": "shadow",
        "CUSTOM_FLAG": "1",
    }

    preferences.save(prefs, tmp_path)

    raw = (tmp_path / ".tzp" / "config" / "settings.env").read_text(encoding="utf-8")
    assert "CUSTOM_FLAG=1" in raw
    assert "WRAP_TEXT=shadow" not in raw
