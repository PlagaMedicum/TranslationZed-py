from pathlib import Path

from translationzed_py.core.tm_store import TMStore


def test_tm_store_exact_and_fuzzy(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    store = TMStore(root)
    file_path = root / "BE" / "ui.txt"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    store.upsert_project_entries(
        [("key1", "Hello world", "Privet mir")],
        source_locale="EN",
        target_locale="BE",
        file_path=str(file_path),
    )
    store.insert_import_pairs(
        [("Hello world", "Import mir")],
        source_locale="EN",
        target_locale="BE",
        tm_name="external_memories",
        tm_path=str(root / "imports" / "external_memories.tmx"),
    )
    assert store.has_entries(source_locale="EN", target_locale="BE") is True
    exact = store.query("Hello world", source_locale="EN", target_locale="BE", limit=5)
    assert exact
    assert exact[0].score == 100
    assert exact[0].target_text == "Privet mir"
    project_only = store.query(
        "Hello world",
        source_locale="EN",
        target_locale="BE",
        limit=5,
        origins=["project"],
    )
    assert all(match.origin == "project" for match in project_only)
    import_only = store.query(
        "Hello world",
        source_locale="EN",
        target_locale="BE",
        limit=5,
        origins=["import"],
    )
    assert import_only
    assert all(match.origin == "import" for match in import_only)
    assert any(match.tm_name == "external_memories" for match in import_only)

    store.insert_import_pairs(
        [("Hello world!", "Privet mir!")],
        source_locale="EN",
        target_locale="BE",
    )
    fuzzy = store.query(
        "Hello world!!", source_locale="EN", target_locale="BE", limit=5
    )
    assert any(match.score < 100 for match in fuzzy)
    offthread = TMStore.query_path(
        store.db_path,
        "Hello world",
        source_locale="EN",
        target_locale="BE",
        limit=5,
    )
    assert offthread
    assert offthread[0].score == 100
    store.close()


def test_tm_import_file_registry_and_replace(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    store = TMStore(root)
    tmx_path = root / ".tzp" / "imported_tms" / "pack_ru.tmx"
    tmx_path.parent.mkdir(parents=True, exist_ok=True)
    tmx_path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<tmx version="1.4">
  <header
    creationtool="test"
    creationtoolversion="1"
    datatype="PlainText"
    segtype="sentence"
    srclang="EN"
  />
  <body>
    <tu>
      <tuv xml:lang="EN"><seg>Hello world</seg></tuv>
      <tuv xml:lang="RU"><seg>Privet mir</seg></tuv>
    </tu>
  </body>
</tmx>
""",
        encoding="utf-8",
    )
    count = store.replace_import_tmx(
        tmx_path,
        source_locale="EN",
        target_locale="RU",
        tm_name="pack_ru",
    )
    assert count == 1
    records = store.list_import_files()
    assert records
    assert records[0].tm_name == "pack_ru"
    assert records[0].target_locale == "RU"
    matches = store.query(
        "Hello world",
        source_locale="EN",
        target_locale="RU",
        origins=["import"],
    )
    assert matches
    assert matches[0].tm_name == "pack_ru"
    store.set_import_enabled(str(tmx_path), False)
    assert (
        store.query(
            "Hello world",
            source_locale="EN",
            target_locale="RU",
            origins=["import"],
        )
        == []
    )
    count = store.replace_import_tmx(
        tmx_path,
        source_locale="EN",
        target_locale="RU",
        tm_name="pack_ru",
    )
    assert count == 1
    assert (
        store.query(
            "Hello world",
            source_locale="EN",
            target_locale="RU",
            origins=["import"],
        )
        == []
    )
    stat = tmx_path.stat()
    store.upsert_import_file(
        tm_path=str(tmx_path),
        tm_name="pack_ru",
        source_locale="EN",
        target_locale="RU",
        mtime_ns=stat.st_mtime_ns,
        file_size=stat.st_size,
        enabled=True,
        status="error",
        note="parse failed",
    )
    assert (
        store.query(
            "Hello world",
            source_locale="EN",
            target_locale="RU",
            origins=["import"],
        )
        == []
    )
    store.upsert_import_file(
        tm_path=str(tmx_path),
        tm_name="pack_ru",
        source_locale="EN",
        target_locale="RU",
        mtime_ns=stat.st_mtime_ns,
        file_size=stat.st_size,
        enabled=True,
        status="ready",
        note="",
    )
    assert store.query(
        "Hello world",
        source_locale="EN",
        target_locale="RU",
        origins=["import"],
    )
    store.delete_import_file(str(tmx_path))
    assert not store.list_import_files()
    store.close()
