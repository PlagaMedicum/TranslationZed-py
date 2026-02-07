from pathlib import Path

from translationzed_py.core import preferences


def test_load_is_pure_read_for_missing_settings_env(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    prefs = preferences.load(tmp_path)

    assert prefs["prompt_write_on_exit"] is True
    assert prefs["wrap_text"] is False
    assert prefs["large_text_optimizations"] is True
    assert prefs["search_scope"] == "FILE"
    assert prefs["replace_scope"] == "FILE"
    assert prefs["tm_import_dir"] == str((tmp_path / "imported_tms").resolve())

    path = tmp_path / ".tzp-config" / "settings.env"
    assert not path.exists()


def test_ensure_defaults_bootstraps_missing_settings_env(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    prefs = preferences.ensure_defaults(tmp_path)
    assert prefs["prompt_write_on_exit"] is True
    assert prefs["wrap_text"] is False
    assert prefs["large_text_optimizations"] is True
    assert prefs["search_scope"] == "FILE"
    assert prefs["replace_scope"] == "FILE"
    assert prefs["tm_import_dir"] == str((tmp_path / "imported_tms").resolve())

    path = tmp_path / ".tzp-config" / "settings.env"
    assert path.exists()
    raw = path.read_text(encoding="utf-8")
    assert "PROMPT_WRITE_ON_EXIT=true" in raw
    assert "WRAP_TEXT=false" in raw
    assert "LARGE_TEXT_OPTIMIZATIONS=true" in raw
    assert "SEARCH_SCOPE=FILE" in raw
    assert "REPLACE_SCOPE=FILE" in raw
    assert f"TM_IMPORT_DIR={(tmp_path / 'imported_tms').resolve()}" in raw


def test_ensure_defaults_backfills_missing_keys_and_preserves_extras(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / ".tzp-config" / "settings.env"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "WRAP_TEXT=true\nTM_IMPORT_DIR=/tmp/custom_tm_import\nCUSTOM_FLAG=1\n",
        encoding="utf-8",
    )

    prefs = preferences.ensure_defaults(tmp_path)

    assert prefs["wrap_text"] is True
    assert prefs["prompt_write_on_exit"] is True
    assert prefs["search_scope"] == "FILE"
    assert prefs["replace_scope"] == "FILE"
    assert prefs["tm_import_dir"] == "/tmp/custom_tm_import"
    assert prefs["__extras__"]["CUSTOM_FLAG"] == "1"

    raw = path.read_text(encoding="utf-8")
    assert "PROMPT_WRITE_ON_EXIT=true" in raw
    assert "WRAP_TEXT=true" in raw
    assert "SEARCH_SCOPE=FILE" in raw
    assert "REPLACE_SCOPE=FILE" in raw
    assert "TM_IMPORT_DIR=/tmp/custom_tm_import" in raw
    assert "CUSTOM_FLAG=1" in raw
