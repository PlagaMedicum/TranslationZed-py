from __future__ import annotations

from pathlib import Path

from translationzed_py.core import preferences
from translationzed_py.core.preferences_service import (
    PreferencesService,
    build_persist_payload,
    normalize_loaded_preferences,
    normalize_scope,
    resolve_startup_root,
)


def test_resolve_startup_root_prefers_cli_project(tmp_path: Path) -> None:
    cli_project = tmp_path / "cli_root"
    cli_project.mkdir(parents=True)
    saved_default = tmp_path / "saved_default"
    saved_default.mkdir(parents=True)
    resolved = resolve_startup_root(
        project_root=str(cli_project),
        saved_default_root=str(saved_default),
    )
    assert resolved.root == cli_project.resolve()
    assert resolved.default_root == ""
    assert resolved.requires_picker is False


def test_resolve_startup_root_uses_saved_default_when_existing(tmp_path: Path) -> None:
    saved_default = tmp_path / "saved_default"
    saved_default.mkdir(parents=True)
    resolved = resolve_startup_root(
        project_root=None,
        saved_default_root=str(saved_default),
    )
    assert resolved.root == saved_default.resolve()
    assert resolved.default_root == str(saved_default)
    assert resolved.requires_picker is False


def test_resolve_startup_root_requires_picker_when_default_missing(
    tmp_path: Path,
) -> None:
    resolved = resolve_startup_root(
        project_root=None,
        saved_default_root=str(tmp_path / "missing"),
    )
    assert resolved.root is None
    assert resolved.default_root == ""
    assert resolved.requires_picker is True


def test_normalize_scope_falls_back_to_file() -> None:
    assert normalize_scope("LOCALE") == "LOCALE"
    assert normalize_scope("pool") == "POOL"
    assert normalize_scope("invalid") == "FILE"


def test_preferences_service_normalize_scope_delegates_helper() -> None:
    service = PreferencesService()
    assert service.normalize_scope("locale") == "LOCALE"
    assert service.normalize_scope("bad") == "FILE"


def test_normalize_loaded_preferences_applies_layout_reset_policy() -> None:
    raw = {
        "prompt_write_on_exit": True,
        "wrap_text": True,
        "large_text_optimizations": False,
        "default_root": "/tmp/default",
        "search_scope": "bad-scope",
        "replace_scope": "POOL",
        "last_locales": ["BE"],
        "last_root": "/tmp/last",
        "tm_import_dir": "",
        "window_geometry": "abc",
        "__extras__": {
            "LAYOUT_RESET_REV": "1",
            "TABLE_KEY_WIDTH": "123",
            "KEEP_ME": "x",
        },
    }
    result = normalize_loaded_preferences(
        raw,
        fallback_default_root="/fallback/default",
        fallback_last_root="/fallback/last",
        default_tm_import_dir="/fallback/tm",
        test_mode=True,
    )
    assert result.prompt_write_on_exit is False
    assert result.wrap_text is True
    assert result.large_text_optimizations is False
    assert result.default_root == "/tmp/default"
    assert result.search_scope == "FILE"
    assert result.replace_scope == "POOL"
    assert result.last_locales == ["BE"]
    assert result.last_root == "/tmp/last"
    assert result.tm_import_dir == "/fallback/tm"
    assert result.window_geometry == ""
    assert result.extras["LAYOUT_RESET_REV"] == "3"
    assert "TABLE_KEY_WIDTH" not in result.extras
    assert result.extras["KEEP_ME"] == "x"
    assert result.patched_raw is not None


def test_build_persist_payload_normalizes_scope_and_copies_mutables() -> None:
    locales = ["BE", "RU"]
    extras = {"A": "1"}
    payload = build_persist_payload(
        prompt_write_on_exit=True,
        wrap_text=False,
        large_text_optimizations=True,
        last_root="/root",
        last_locales=locales,
        window_geometry="geom",
        default_root=" /default ",
        tm_import_dir=" /tm ",
        search_scope="invalid",
        replace_scope="locale",
        extras=extras,
    )
    locales.append("TH")
    extras["B"] = "2"
    assert payload["search_scope"] == "FILE"
    assert payload["replace_scope"] == "LOCALE"
    assert payload["last_locales"] == ["BE", "RU"]
    assert payload["__extras__"] == {"A": "1"}
    assert payload["default_root"] == "/default"
    assert payload["tm_import_dir"] == "/tm"


def test_preferences_service_load_normalized_bootstraps_settings(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    service = PreferencesService()

    loaded = service.load_normalized_preferences(
        fallback_default_root="",
        fallback_last_root=str(tmp_path),
        default_tm_import_dir="/fallback/tm",
        test_mode=False,
    )

    assert loaded.wrap_text is False
    assert loaded.search_scope == "FILE"
    assert (tmp_path / ".tzp" / "config" / "settings.env").exists()


def test_preferences_service_persist_main_window_preferences(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    default_root = tmp_path / "project"
    default_root.mkdir(parents=True)
    service = PreferencesService()

    service.persist_main_window_preferences(
        prompt_write_on_exit=False,
        wrap_text=True,
        large_text_optimizations=True,
        last_root=str(default_root),
        last_locales=["BE", "RU"],
        window_geometry="abc",
        default_root=str(default_root),
        tm_import_dir=str(tmp_path / ".tzp" / "tms"),
        search_scope="locale",
        replace_scope="pool",
        extras={"X": "1"},
    )

    saved = preferences.load(None)
    assert saved["prompt_write_on_exit"] is False
    assert saved["wrap_text"] is True
    assert saved["default_root"] == str(default_root)
    assert saved["search_scope"] == "LOCALE"
    assert saved["replace_scope"] == "POOL"
    assert saved["__extras__"]["X"] == "1"


def test_preferences_service_resolve_startup_uses_saved_default(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    default_root = tmp_path / "workspace"
    default_root.mkdir(parents=True)
    service = PreferencesService()
    service.persist_default_root(str(default_root))

    startup = service.resolve_startup_root(project_root=None)

    assert startup.root == default_root.resolve()
    assert startup.default_root == str(default_root)
    assert startup.requires_picker is False
