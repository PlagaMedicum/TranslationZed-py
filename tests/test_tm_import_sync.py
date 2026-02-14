from __future__ import annotations

from pathlib import Path

from translationzed_py.core.tm_import_sync import sync_import_folder
from translationzed_py.core.tm_store import TMStore


def _write_tmx(path: Path, source_lang: str = "EN", target_lang: str = "RU") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<tmx version="1.4">
  <header
    creationtool="test"
    creationtoolversion="1"
    datatype="PlainText"
    segtype="sentence"
    srclang="{source_lang}"
  />
  <body>
    <tu>
      <tuv xml:lang="{source_lang}"><seg>Hello world</seg></tuv>
      <tuv xml:lang="{target_lang}"><seg>Privet mir</seg></tuv>
    </tu>
  </body>
</tmx>
""",
        encoding="utf-8",
    )


def _write_xliff(
    path: Path,
    source_lang: str = "en-US",
    target_lang: str = "ru-RU",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2">
  <file source-language="{source_lang}" target-language="{target_lang}" datatype="plaintext">
    <body>
      <trans-unit id="1">
        <source>Hello world</source>
        <target>Privet mir</target>
      </trans-unit>
    </body>
  </file>
</xliff>
""",
        encoding="utf-8",
    )


def _write_po(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """
msgid ""
msgstr ""
"Language: ru\\n"
"X-Source-Language: en\\n"

msgid "Hello world"
msgstr "Privet mir"
""".strip()
        + "\n",
        encoding="utf-8",
    )


def test_sync_import_folder_imports_and_reports_changed(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    tm_dir = root / ".tzp" / "tms"
    tmx_path = tm_dir / "pack_ru.tmx"
    _write_tmx(tmx_path)
    store = TMStore(root)

    report = sync_import_folder(
        store,
        tm_dir,
        resolve_locales=lambda _path, _langs: (("EN", "RU"), False),
    )

    assert report.imported_segments == 1
    assert report.imported_files == ("pack_ru.tmx (1 segment(s))",)
    assert report.changed is True
    assert report.unresolved_files == ()
    assert report.zero_segment_files == ()
    assert report.failures == ()
    assert report.checked_files == ("pack_ru.tmx",)
    assert store.query(
        "Hello world",
        source_locale="EN",
        target_locale="RU",
        origins=["import"],
    )
    store.close()


def test_sync_import_folder_imports_xliff_file(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    tm_dir = root / ".tzp" / "tms"
    xliff_path = tm_dir / "pack_ru.xliff"
    _write_xliff(xliff_path)
    store = TMStore(root)

    report = sync_import_folder(
        store,
        tm_dir,
        resolve_locales=lambda _path, _langs: (("EN", "RU"), False),
    )

    assert report.imported_segments == 1
    assert report.imported_files == ("pack_ru.xliff (1 segment(s))",)
    assert report.failures == ()
    assert store.query(
        "Hello world",
        source_locale="EN",
        target_locale="RU",
        origins=["import"],
    )
    records = store.list_import_files()
    assert len(records) == 1
    assert records[0].source_locale_raw == "en-US"
    assert records[0].target_locale_raw == "ru-RU"
    store.close()


def test_sync_import_folder_imports_po_file(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    tm_dir = root / ".tzp" / "tms"
    po_path = tm_dir / "pack_ru.po"
    _write_po(po_path)
    store = TMStore(root)

    report = sync_import_folder(
        store,
        tm_dir,
        resolve_locales=lambda _path, _langs: (("EN", "RU"), False),
    )

    assert report.imported_segments == 1
    assert report.imported_files == ("pack_ru.po (1 segment(s))",)
    assert report.failures == ()
    assert store.query(
        "Hello world",
        source_locale="EN",
        target_locale="RU",
        origins=["import"],
    )
    records = store.list_import_files()
    assert len(records) == 1
    assert records[0].source_locale_raw == "en"
    assert records[0].target_locale_raw == "ru"
    store.close()


def test_sync_import_folder_skip_all_marks_remaining_unresolved(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    tm_dir = root / ".tzp" / "tms"
    _write_tmx(tm_dir / "one.tmx")
    _write_tmx(tm_dir / "two.tmx")
    store = TMStore(root)
    calls = {"count": 0}

    def _resolve(_path: Path, _langs: set[str]) -> tuple[tuple[str, str] | None, bool]:
        calls["count"] += 1
        return None, True

    report = sync_import_folder(store, tm_dir, resolve_locales=_resolve)

    assert calls["count"] == 1
    assert sorted(report.unresolved_files) == ["one.tmx", "two.tmx"]
    assert report.imported_segments == 0
    assert report.imported_files == ()
    assert report.zero_segment_files == ()
    records = store.list_import_files()
    assert len(records) == 2
    assert all(rec.status == "needs_mapping" for rec in records)
    store.close()


def test_sync_import_folder_deletes_missing_import_files(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    tm_dir = root / ".tzp" / "tms"
    tmx_path = tm_dir / "pack_ru.tmx"
    _write_tmx(tmx_path)
    store = TMStore(root)

    first = sync_import_folder(
        store,
        tm_dir,
        resolve_locales=lambda _path, _langs: (("EN", "RU"), False),
    )
    assert first.changed is True
    assert store.list_import_files()
    tmx_path.unlink()

    second = sync_import_folder(
        store,
        tm_dir,
        resolve_locales=lambda _path, _langs: (("EN", "RU"), False),
    )
    assert second.changed is True
    assert store.list_import_files() == []
    assert (
        store.query(
            "Hello world",
            source_locale="EN",
            target_locale="RU",
            origins=["import"],
        )
        == []
    )
    store.close()


def test_sync_import_folder_reimports_ready_file_when_entries_missing(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    tm_dir = root / ".tzp" / "tms"
    tmx_path = tm_dir / "pack_ru.tmx"
    _write_tmx(tmx_path)
    store = TMStore(root)
    stat = tmx_path.stat()
    store.upsert_import_file(
        tm_path=str(tmx_path),
        tm_name="pack_ru",
        source_locale="EN",
        target_locale="RU",
        mtime_ns=stat.st_mtime_ns,
        file_size=stat.st_size,
        enabled=True,
        status="ready",
    )

    report = sync_import_folder(
        store,
        tm_dir,
        resolve_locales=lambda _path, _langs: (("EN", "RU"), False),
    )

    assert report.imported_segments == 1
    assert report.zero_segment_files == ()
    assert store.query(
        "Hello world",
        source_locale="EN",
        target_locale="RU",
        origins=["import"],
    )
    store.close()


def test_sync_import_folder_reports_zero_segment_imports_and_raw_locales(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    tm_dir = root / ".tzp" / "tms"
    tmx_path = tm_dir / "pack_region.tmx"
    _write_tmx(tmx_path, source_lang="en-US", target_lang="be-BY")
    store = TMStore(root)

    report = sync_import_folder(
        store,
        tm_dir,
        resolve_locales=lambda _path, _langs: (("EN", "RU"), False),
    )

    assert report.imported_segments == 0
    assert report.imported_files == ("pack_region.tmx (0 segment(s))",)
    assert report.zero_segment_files == ("pack_region.tmx",)
    records = store.list_import_files()
    assert len(records) == 1
    assert records[0].source_locale == "EN"
    assert records[0].target_locale == "RU"
    assert records[0].source_locale_raw == "en-US"
    assert records[0].target_locale_raw == "be-BY"
    assert records[0].segment_count == 0
    store.close()


def test_sync_import_folder_processes_supported_aliases_and_ignores_unsupported(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    tm_dir = root / ".tzp" / "tms"
    tm_dir.mkdir(parents=True, exist_ok=True)
    (tm_dir / "ignored.json").write_text('{"a": 1}\n', encoding="utf-8")
    (tm_dir / "ignored.xlf").write_text("<xliff/>", encoding="utf-8")
    store = TMStore(root)

    report = sync_import_folder(
        store,
        tm_dir,
        resolve_locales=lambda _path, _langs: (("EN", "RU"), False),
    )

    assert report.imported_segments == 0
    assert report.checked_files == ("ignored.xlf",)
    assert report.imported_files == ("ignored.xlf (0 segment(s))",)
    assert report.changed is True
    records = store.list_import_files()
    assert len(records) == 1
    assert records[0].tm_path.endswith("ignored.xlf")
    assert records[0].segment_count == 0
    store.close()
