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

    path = tmp_path / ".tzp" / "config" / "settings.env"
    assert not path.exists()


def test_ensure_defaults_bootstraps_missing_settings_env(
    tmp_path: Path, monkeypatch
) -> None:
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


def test_ensure_defaults_backfills_missing_keys_and_preserves_extras(
    tmp_path: Path, monkeypatch
) -> None:
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
