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


def test_tm_store_filters_low_token_overlap_candidates(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    store = TMStore(root)
    file_path = root / "BE" / "ui.txt"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    store.upsert_project_entries(
        [
            ("k1", "water bottle", "water bottle tr"),
            ("k2", "better battle", "better battle tr"),
        ],
        source_locale="EN",
        target_locale="BE",
        file_path=str(file_path),
    )

    fuzzy = store.query(
        "water bottle!!",
        source_locale="EN",
        target_locale="BE",
        limit=10,
    )

    assert any(match.source_text == "water bottle" for match in fuzzy)
    assert all(match.source_text != "better battle" for match in fuzzy)
    store.close()


def test_tm_store_plural_neighbor_is_returned_for_single_token_query(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    store = TMStore(root)
    file_path = root / "BE" / "ui.txt"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    store.upsert_project_entries(
        [
            ("k_favorite", "Favorite", "Улюбёнае"),
            ("k_favorites", "Favorites", "Улюбёныя"),
            ("k_factory", "Factory", "Завод"),
        ],
        source_locale="EN",
        target_locale="BE",
        file_path=str(file_path),
    )

    matches = store.query(
        "Favorite",
        source_locale="EN",
        target_locale="BE",
        limit=10,
        min_score=20,
    )

    assert any(match.source_text == "Favorites" for match in matches)
    favorites = next(match for match in matches if match.source_text == "Favorites")
    assert favorites.score >= 90
    store.close()


def test_tm_store_tagged_query_matches_phrase_candidate(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    store = TMStore(root)
    file_path = root / "BE" / "ui.txt"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    store.upsert_project_entries(
        [("k1", "Make new item", "Зрабіць новы прадмет")],
        source_locale="EN",
        target_locale="BE",
        file_path=str(file_path),
    )

    fuzzy = store.query(
        "<LINE> Make item",
        source_locale="EN",
        target_locale="BE",
        limit=10,
    )

    assert any(match.source_text == "Make new item" for match in fuzzy)
    store.close()


def test_tm_store_fuzzy_prefix_lookup_finds_neighboring_strings(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    store = TMStore(root)
    file_path = root / "BE" / "ui.txt"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    store.upsert_project_entries(
        [
            ("k_run", "Official: Run", "Run tr"),
            ("k_rest", "Official: Rest", "Rest tr"),
        ],
        source_locale="EN",
        target_locale="BE",
        file_path=str(file_path),
        updated_at=1,
    )
    noisy = [
        (f"noise_{i}", f"Random token {i:03d}", f"noise tr {i:03d}") for i in range(350)
    ]
    store.upsert_project_entries(
        noisy,
        source_locale="EN",
        target_locale="BE",
        file_path=str(file_path),
        updated_at=2,
    )

    fuzzy = store.query(
        "Official: Rest",
        source_locale="EN",
        target_locale="BE",
        limit=10,
        min_score=30,
    )
    strict = store.query(
        "Official: Rest",
        source_locale="EN",
        target_locale="BE",
        limit=10,
        min_score=90,
    )

    run = next((m for m in fuzzy if m.source_text == "Official: Run"), None)
    assert run is not None
    assert run.score >= 80
    assert all(match.source_text != "Official: Run" for match in strict)
    store.close()


def test_tm_store_keeps_fuzzy_neighbors_when_exact_pool_is_large(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    store = TMStore(root)
    file_path = root / "BE" / "ui.txt"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    store.upsert_project_entries(
        [("k_run", "Official: Run", "Run tr"), ("k_rest", "Official: Rest", "Rest tr")],
        source_locale="EN",
        target_locale="BE",
        file_path=str(file_path),
        updated_at=1,
    )
    for i in range(20):
        store.insert_import_pairs(
            [("Official: Rest", f"Imported rest {i}")],
            source_locale="EN",
            target_locale="BE",
            tm_name=f"tm_{i}",
            tm_path=str(root / ".tzp" / "tms" / f"tm_{i}.tmx"),
            updated_at=2 + i,
        )

    fuzzy = store.query(
        "Official: Rest",
        source_locale="EN",
        target_locale="BE",
        limit=12,
        min_score=30,
    )

    assert any(match.source_text == "Official: Run" for match in fuzzy)
    store.close()


def test_tm_store_fuzzy_prefix_lookup_handles_dense_prefix_sets(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    store = TMStore(root)
    file_path = root / "BE" / "ui.txt"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    store.upsert_project_entries(
        [("k_run", "Official: Run", "Run tr"), ("k_rest", "Official: Rest", "Rest tr")],
        source_locale="EN",
        target_locale="BE",
        file_path=str(file_path),
        updated_at=1,
    )
    noisy = [
        (f"noise_{i}", f"Official: Token {i:04d}", f"Noise tr {i:04d}")
        for i in range(1500)
    ]
    store.upsert_project_entries(
        noisy,
        source_locale="EN",
        target_locale="BE",
        file_path=str(file_path),
        updated_at=3,
    )

    fuzzy = store.query(
        "Official: Rest",
        source_locale="EN",
        target_locale="BE",
        limit=12,
        min_score=30,
    )

    assert any(match.source_text == "Official: Run" for match in fuzzy)
    store.close()


def test_tm_import_file_registry_and_replace(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    store = TMStore(root)
    tmx_path = root / ".tzp" / "tms" / "pack_ru.tmx"
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
        source_locale_raw="en-US",
        target_locale_raw="ru-RU",
        tm_name="pack_ru",
    )
    assert count == 1
    records = store.list_import_files()
    assert records
    assert records[0].tm_name == "pack_ru"
    assert records[0].target_locale == "RU"
    assert records[0].source_locale_raw == "en-US"
    assert records[0].target_locale_raw == "ru-RU"
    assert records[0].segment_count == 1
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
