"""Test module for preferences."""

from pathlib import Path

from translationzed_py.core import preferences


def test_load_is_pure_read_for_missing_settings_env(
    tmp_path: Path, monkeypatch
) -> None:
    """Verify load is pure read for missing settings env."""
    monkeypatch.chdir(tmp_path)
    prefs = preferences.load(tmp_path)

    assert prefs["prompt_write_on_exit"] is True
    assert prefs["wrap_text"] is False
    assert prefs["large_text_optimizations"] is True
    assert prefs["qa_check_trailing"] is True
    assert prefs["qa_check_newlines"] is True
    assert prefs["qa_check_escapes"] is False
    assert prefs["qa_check_same_as_source"] is False
    assert prefs["qa_auto_refresh"] is False
    assert prefs["qa_auto_mark_for_review"] is False
    assert prefs["qa_auto_mark_touched_for_review"] is False
    assert prefs["search_scope"] == "FILE"
    assert prefs["replace_scope"] == "FILE"
    assert prefs["tm_import_dir"] == str((tmp_path / ".tzp" / "tms").resolve())
    assert prefs["lt_editor_mode"] == "auto"
    assert prefs["lt_server_url"] == "http://127.0.0.1:8081"
    assert prefs["lt_timeout_ms"] == 1200
    assert prefs["lt_picky_mode"] is False
    assert prefs["lt_locale_map"] == "{}"
    assert prefs["qa_check_languagetool"] is False
    assert prefs["qa_languagetool_max_rows"] == 500
    assert prefs["qa_languagetool_automark"] is False

    path = tmp_path / ".tzp" / "config" / "settings.env"
    assert not path.exists()


def test_ensure_defaults_bootstraps_missing_settings_env(
    tmp_path: Path, monkeypatch
) -> None:
    """Verify ensure defaults bootstraps missing settings env."""
    monkeypatch.chdir(tmp_path)
    prefs = preferences.ensure_defaults(tmp_path)
    assert prefs["prompt_write_on_exit"] is True
    assert prefs["wrap_text"] is False
    assert prefs["large_text_optimizations"] is True
    assert prefs["qa_check_trailing"] is True
    assert prefs["qa_check_newlines"] is True
    assert prefs["qa_check_escapes"] is False
    assert prefs["qa_check_same_as_source"] is False
    assert prefs["qa_auto_refresh"] is False
    assert prefs["qa_auto_mark_for_review"] is False
    assert prefs["qa_auto_mark_touched_for_review"] is False
    assert prefs["search_scope"] == "FILE"
    assert prefs["replace_scope"] == "FILE"
    assert prefs["tm_import_dir"] == str((tmp_path / ".tzp" / "tms").resolve())
    assert prefs["lt_editor_mode"] == "auto"
    assert prefs["lt_server_url"] == "http://127.0.0.1:8081"
    assert prefs["lt_timeout_ms"] == 1200
    assert prefs["lt_picky_mode"] is False
    assert prefs["lt_locale_map"] == "{}"
    assert prefs["qa_check_languagetool"] is False
    assert prefs["qa_languagetool_max_rows"] == 500
    assert prefs["qa_languagetool_automark"] is False

    path = tmp_path / ".tzp" / "config" / "settings.env"
    assert path.exists()
    raw = path.read_text(encoding="utf-8")
    assert "PROMPT_WRITE_ON_EXIT=true" in raw
    assert "WRAP_TEXT=false" in raw
    assert "LARGE_TEXT_OPTIMIZATIONS=true" in raw
    assert "QA_CHECK_TRAILING=true" in raw
    assert "QA_CHECK_NEWLINES=true" in raw
    assert "QA_CHECK_ESCAPES=false" in raw
    assert "QA_CHECK_SAME_AS_SOURCE=false" in raw
    assert "QA_AUTO_REFRESH=false" in raw
    assert "QA_AUTO_MARK_FOR_REVIEW=false" in raw
    assert "QA_AUTO_MARK_TOUCHED_FOR_REVIEW=false" in raw
    assert "SEARCH_SCOPE=FILE" in raw
    assert "REPLACE_SCOPE=FILE" in raw
    assert f"TM_IMPORT_DIR={(tmp_path / '.tzp' / 'tms').resolve()}" in raw
    assert "LT_EDITOR_MODE=auto" in raw
    assert "LT_SERVER_URL=http://127.0.0.1:8081" in raw
    assert "LT_TIMEOUT_MS=1200" in raw
    assert "LT_PICKY_MODE=false" in raw
    assert "LT_LOCALE_MAP={}" in raw
    assert "QA_CHECK_LANGUAGETOOL=false" in raw
    assert "QA_LANGUAGETOOL_MAX_ROWS=500" in raw
    assert "QA_LANGUAGETOOL_AUTOMARK=false" in raw


def test_ensure_defaults_backfills_missing_keys_and_preserves_extras(
    tmp_path: Path, monkeypatch
) -> None:
    """Verify ensure defaults backfills missing keys and preserves extras."""
    monkeypatch.chdir(tmp_path)
    legacy_path = tmp_path / ".tzp-config" / "settings.env"
    legacy_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_path.write_text(
        "WRAP_TEXT=true\n"
        "QA_CHECK_ESCAPES=true\n"
        "TM_IMPORT_DIR=/tmp/custom_tm_import\n"
        "CUSTOM_FLAG=1\n",
        encoding="utf-8",
    )

    prefs = preferences.ensure_defaults(tmp_path)

    assert prefs["wrap_text"] is True
    assert prefs["qa_check_escapes"] is True
    assert prefs["prompt_write_on_exit"] is True
    assert prefs["search_scope"] == "FILE"
    assert prefs["replace_scope"] == "FILE"
    assert prefs["tm_import_dir"] == str(Path("/tmp/custom_tm_import").resolve())
    assert prefs["__extras__"]["CUSTOM_FLAG"] == "1"

    path = tmp_path / ".tzp" / "config" / "settings.env"
    raw = path.read_text(encoding="utf-8")
    assert "PROMPT_WRITE_ON_EXIT=true" in raw
    assert "WRAP_TEXT=true" in raw
    assert "QA_CHECK_TRAILING=true" in raw
    assert "QA_CHECK_NEWLINES=true" in raw
    assert "QA_CHECK_ESCAPES=true" in raw
    assert "QA_CHECK_SAME_AS_SOURCE=false" in raw
    assert "QA_AUTO_REFRESH=false" in raw
    assert "QA_AUTO_MARK_FOR_REVIEW=false" in raw
    assert "QA_AUTO_MARK_TOUCHED_FOR_REVIEW=false" in raw
    assert "SEARCH_SCOPE=FILE" in raw
    assert "REPLACE_SCOPE=FILE" in raw
    assert f"TM_IMPORT_DIR={Path('/tmp/custom_tm_import').resolve()}" in raw
    assert "CUSTOM_FLAG=1" in raw


def test_load_reads_legacy_settings_without_writing(
    tmp_path: Path, monkeypatch
) -> None:
    """Verify load reads legacy settings without writing."""
    monkeypatch.chdir(tmp_path)
    legacy_path = tmp_path / ".tzp-config" / "settings.env"
    legacy_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_path.write_text(
        "WRAP_TEXT=true\nSEARCH_SCOPE=POOL\nCUSTOM_FLAG=1\n",
        encoding="utf-8",
    )

    prefs = preferences.load(tmp_path)

    assert prefs["wrap_text"] is True
    assert prefs["search_scope"] == "POOL"
    assert prefs["__extras__"]["CUSTOM_FLAG"] == "1"
    assert not (tmp_path / ".tzp" / "config" / "settings.env").exists()


def test_ensure_defaults_reroutes_legacy_tm_import_dir_value(
    tmp_path: Path, monkeypatch
) -> None:
    """Verify ensure defaults reroutes legacy tm import dir value."""
    monkeypatch.chdir(tmp_path)
    legacy_path = tmp_path / ".tzp-config" / "settings.env"
    legacy_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_path.write_text(
        f"TM_IMPORT_DIR={(tmp_path / '.tzp' / 'imported_tms').resolve()}\n",
        encoding="utf-8",
    )

    prefs = preferences.ensure_defaults(tmp_path)

    expected = str((tmp_path / ".tzp" / "tms").resolve())
    assert prefs["tm_import_dir"] == expected
    raw = (tmp_path / ".tzp" / "config" / "settings.env").read_text(encoding="utf-8")
    assert f"TM_IMPORT_DIR={expected}" in raw


def test_ensure_defaults_migrates_root_imported_tms_into_tms(
    tmp_path: Path, monkeypatch
) -> None:
    """Verify ensure defaults migrates root imported tms into tms."""
    monkeypatch.chdir(tmp_path)
    old_dir = tmp_path / "imported_tms"
    old_dir.mkdir(parents=True, exist_ok=True)
    old_file = old_dir / "a.tmx"
    old_file.write_text("tmx", encoding="utf-8")

    preferences.ensure_defaults(tmp_path)

    new_file = tmp_path / ".tzp" / "tms" / "a.tmx"
    assert new_file.exists()
    assert new_file.read_text(encoding="utf-8") == "tmx"
    assert not old_file.exists()


def test_ensure_defaults_canonicalizes_relative_tm_import_dir(
    tmp_path: Path, monkeypatch
) -> None:
    """Verify ensure defaults canonicalizes relative tm import dir."""
    monkeypatch.chdir(tmp_path)
    cfg_path = tmp_path / ".tzp" / "config" / "settings.env"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(
        "TM_IMPORT_DIR=./relative/../tm_import\n",
        encoding="utf-8",
    )

    prefs = preferences.ensure_defaults(tmp_path)

    expected = str((tmp_path / "tm_import").resolve())
    assert prefs["tm_import_dir"] == expected
    raw = cfg_path.read_text(encoding="utf-8")
    assert f"TM_IMPORT_DIR={expected}" in raw


def test_ensure_defaults_normalizes_languagetool_settings(
    tmp_path: Path, monkeypatch
) -> None:
    """Verify LT-related preferences normalize invalid values safely."""
    monkeypatch.chdir(tmp_path)
    cfg_path = tmp_path / ".tzp" / "config" / "settings.env"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(
        "LT_EDITOR_MODE=invalid\n"
        "LT_SERVER_URL=https://lt.example.org\n"
        "LT_TIMEOUT_MS=999999\n"
        "LT_PICKY_MODE=true\n"
        "LT_LOCALE_MAP={bad json}\n"
        "QA_CHECK_LANGUAGETOOL=true\n"
        "QA_LANGUAGETOOL_MAX_ROWS=0\n"
        "QA_LANGUAGETOOL_AUTOMARK=true\n",
        encoding="utf-8",
    )

    prefs = preferences.ensure_defaults(tmp_path)

    assert prefs["lt_editor_mode"] == "auto"
    assert prefs["lt_server_url"] == "https://lt.example.org"
    assert prefs["lt_timeout_ms"] == 30000
    assert prefs["lt_picky_mode"] is True
    assert prefs["lt_locale_map"] == "{}"
    assert prefs["qa_check_languagetool"] is True
    assert prefs["qa_languagetool_max_rows"] == 1
    assert prefs["qa_languagetool_automark"] is True
