"""Test module for tm store."""

import gc
import warnings
from pathlib import Path

from translationzed_py.core.tm_store import TMStore


def test_tm_store_exact_and_fuzzy(tmp_path: Path) -> None:
    """Verify tm store exact and fuzzy."""
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


def test_tm_store_project_match_exposes_row_status(tmp_path: Path) -> None:
    """Verify tm store project match exposes row status."""
    root = tmp_path / "root"
    root.mkdir()
    store = TMStore(root)
    file_path = root / "BE" / "ui.txt"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    store.upsert_project_entries(
        [("key1", "Drop all", "Пакінуць усё", 1)],
        source_locale="EN",
        target_locale="BE",
        file_path=str(file_path),
    )
    store.insert_import_pairs(
        [("Drop all", "Import drop all")],
        source_locale="EN",
        target_locale="BE",
        tm_name="ext",
        tm_path=str(root / ".tzp" / "tms" / "ext.tmx"),
    )

    matches = store.query(
        "Drop all",
        source_locale="EN",
        target_locale="BE",
        limit=10,
    )
    project = next(match for match in matches if match.origin == "project")
    imported = next(match for match in matches if match.origin == "import")
    assert project.row_status == 1
    assert imported.row_status is None
    store.close()


def test_tm_store_query_path_closes_temporary_connections(tmp_path: Path) -> None:
    """Verify tm store query path closes temporary connections."""
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
    db_path = store.db_path
    store.close()

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ResourceWarning)
        for _ in range(8):
            matches = TMStore.query_path(
                db_path,
                "Hello world",
                source_locale="EN",
                target_locale="BE",
                limit=3,
            )
            assert matches
        gc.collect()

    resource_warnings = [
        row for row in caught if issubclass(row.category, ResourceWarning)
    ]
    assert not resource_warnings


def test_tm_store_filters_low_token_overlap_candidates(tmp_path: Path) -> None:
    """Verify tm store filters low token overlap candidates."""
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
    """Verify tm store plural neighbor is returned for single token query."""
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
    """Verify tm store tagged query matches phrase candidate."""
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
    """Verify tm store fuzzy prefix lookup finds neighboring strings."""
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
    """Verify tm store keeps fuzzy neighbors when exact pool is large."""
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


def test_tm_store_short_query_includes_phrase_neighbors(tmp_path: Path) -> None:
    """Verify tm store short query includes phrase neighbors."""
    root = tmp_path / "root"
    root.mkdir()
    store = TMStore(root)
    file_path = root / "BE" / "ui.txt"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        ("k_all", "All", "Усе"),
        ("k_apply_all", "Apply all", "Прымяніць усё"),
    ]
    rows.extend(
        (
            f"noise_{i}",
            f"All token {i:04d}",
            f"Шум {i:04d}",
        )
        for i in range(2200)
    )
    store.upsert_project_entries(
        rows,
        source_locale="EN",
        target_locale="BE",
        file_path=str(file_path),
        updated_at=1,
    )

    fuzzy = store.query(
        "All",
        source_locale="EN",
        target_locale="BE",
        limit=12,
        min_score=5,
    )

    match = next((item for item in fuzzy if item.source_text == "Apply all"), None)
    assert match is not None
    assert match.score >= 40
    store.close()


def test_tm_store_multi_token_query_includes_non_prefix_neighbors(
    tmp_path: Path,
) -> None:
    """Verify tm store multi token query includes non prefix neighbors."""
    root = tmp_path / "root"
    root.mkdir()
    store = TMStore(root)
    file_path = root / "BE" / "ui.txt"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    store.upsert_project_entries(
        [
            ("k1", "Drop one", "Скінуць шт."),
            ("k2", "Drop-all", "Пакід. усё"),
            ("k3", "Drop all", "Пакінуць усё"),
            ("k4", "Drink one", "Выпіць шт."),
        ],
        source_locale="EN",
        target_locale="BE",
        file_path=str(file_path),
    )

    fuzzy = store.query(
        "Drop one",
        source_locale="EN",
        target_locale="BE",
        limit=12,
        min_score=25,
    )

    sources = {match.source_text for match in fuzzy}
    assert "Drop one" in sources
    assert {"Drop-all", "Drop all"} & sources
    store.close()


def test_tm_store_project_origin_keeps_fuzzy_neighbors(tmp_path: Path) -> None:
    """Verify tm store project origin keeps fuzzy neighbors."""
    root = tmp_path / "root"
    root.mkdir()
    store = TMStore(root)
    file_path = root / "BE" / "ui.txt"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    store.upsert_project_entries(
        [
            ("k1", "Drop all", "Пакінуць усё"),
            ("k2", "Drop one", "Скінуць шт."),
            ("k3", "Drop-all", "Пакід. усё"),
            ("k4", "Drop", "Скінуць"),
        ],
        source_locale="EN",
        target_locale="BE",
        file_path=str(file_path),
    )

    fuzzy = store.query(
        "Drop all",
        source_locale="EN",
        target_locale="BE",
        limit=12,
        min_score=5,
        origins=["project"],
    )

    sources = {match.source_text for match in fuzzy}
    assert "Drop one" in sources
    assert "Drop-all" in sources
    store.close()


def test_tm_store_import_origin_keeps_fuzzy_neighbors(tmp_path: Path) -> None:
    """Verify tm store import origin keeps fuzzy neighbors."""
    root = tmp_path / "root"
    root.mkdir()
    store = TMStore(root)
    store.insert_import_pairs(
        [
            ("Drop all", "Пакінуць усё"),
            ("Drop one", "Скінуць шт."),
            ("Drop-all", "Пакід. усё"),
            ("Drop", "Скінуць"),
        ],
        source_locale="EN",
        target_locale="BE",
        tm_name="import_pack",
        tm_path=str(root / ".tzp" / "tms" / "import_pack.tmx"),
    )

    fuzzy = store.query(
        "Drop all",
        source_locale="EN",
        target_locale="BE",
        limit=12,
        min_score=5,
        origins=["import"],
    )

    sources = {match.source_text for match in fuzzy}
    assert "Drop one" in sources
    assert "Drop-all" in sources
    store.close()


def test_tm_store_multi_token_query_handles_single_char_token_typos(
    tmp_path: Path,
) -> None:
    """Verify tm store multi token query handles single char token typos."""
    root = tmp_path / "root"
    root.mkdir()
    store = TMStore(root)
    file_path = root / "BE" / "ui.txt"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    store.upsert_project_entries(
        [
            ("k1", "Drop one", "Скінуць шт."),
            ("k2", "Drap all", "Пакінуць усё"),
            ("k3", "Drop", "Скінуць"),
        ],
        source_locale="EN",
        target_locale="BE",
        file_path=str(file_path),
    )

    fuzzy = store.query(
        "Drop one",
        source_locale="EN",
        target_locale="BE",
        limit=12,
        min_score=5,
    )

    sources = {match.source_text for match in fuzzy}
    assert "Drap all" in sources
    store.close()


def test_tm_store_single_token_query_filters_substring_noise(tmp_path: Path) -> None:
    """Verify tm store single token query filters substring noise."""
    root = tmp_path / "root"
    root.mkdir()
    store = TMStore(root)
    file_path = root / "BE" / "ui.txt"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    store.upsert_project_entries(
        [
            ("k1", "All", "Усе"),
            ("k2", "Apply all", "Прымяніць усё"),
            ("k3", "Small crate", "Малы скрыня"),
        ],
        source_locale="EN",
        target_locale="BE",
        file_path=str(file_path),
    )

    fuzzy = store.query(
        "All",
        source_locale="EN",
        target_locale="BE",
        limit=12,
        min_score=5,
    )

    sources = {match.source_text for match in fuzzy}
    assert "Apply all" in sources
    assert "Small crate" not in sources
    store.close()


def test_tm_store_token_matching_supports_common_affixes(tmp_path: Path) -> None:
    """Verify tm store token matching supports common affixes."""
    root = tmp_path / "root"
    root.mkdir()
    store = TMStore(root)
    file_path = root / "BE" / "ui.txt"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    store.upsert_project_entries(
        [
            ("k1", "Run", "Бег"),
            ("k2", "Running", "Бегчы"),
            ("k3", "Runner", "Бягун"),
        ],
        source_locale="EN",
        target_locale="BE",
        file_path=str(file_path),
    )

    fuzzy = store.query(
        "Run",
        source_locale="EN",
        target_locale="BE",
        limit=12,
        min_score=20,
    )

    sources = {match.source_text for match in fuzzy}
    assert "Running" in sources
    assert "Runner" in sources
    store.close()


def test_tm_store_affix_stemming_is_scoped_to_en_source_locale(tmp_path: Path) -> None:
    """Verify tm store affix stemming is scoped to en source locale."""
    root = tmp_path / "root"
    root.mkdir()
    store = TMStore(root)
    file_path = root / "BE" / "ui.txt"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    store.upsert_project_entries(
        [
            ("k1", "Run", "Бег"),
            ("k2", "Running", "Бегчы"),
        ],
        source_locale="FR",
        target_locale="BE",
        file_path=str(file_path),
    )

    fuzzy = store.query(
        "Run",
        source_locale="FR",
        target_locale="BE",
        limit=12,
        min_score=5,
    )

    sources = {match.source_text for match in fuzzy}
    assert "Run" in sources
    assert "Running" not in sources
    store.close()


def test_tm_store_exposes_ranked_and_raw_scores_for_diagnostics(tmp_path: Path) -> None:
    """Verify tm store exposes ranked and raw scores for diagnostics."""
    root = tmp_path / "root"
    root.mkdir()
    store = TMStore(root)
    file_path = root / "BE" / "ui.txt"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    store.upsert_project_entries(
        [
            ("k1", "Drop one", "Скінуць шт."),
            ("k2", "Drop all", "Пакінуць усё"),
        ],
        source_locale="EN",
        target_locale="BE",
        file_path=str(file_path),
    )

    fuzzy = store.query(
        "Drop one",
        source_locale="EN",
        target_locale="BE",
        limit=12,
        min_score=5,
    )

    exact = next(match for match in fuzzy if match.source_text == "Drop one")
    neighbor = next(match for match in fuzzy if match.source_text == "Drop all")
    assert exact.raw_score == 100
    assert neighbor.raw_score is not None
    assert neighbor.raw_score <= neighbor.score
    store.close()


def test_tm_store_fuzzy_prefix_lookup_handles_dense_prefix_sets(tmp_path: Path) -> None:
    """Verify tm store fuzzy prefix lookup handles dense prefix sets."""
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
    """Verify tm import file registry and replace."""
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


def test_tm_store_replace_import_tm_with_xliff(tmp_path: Path) -> None:
    """Verify tm store replace import tm with xliff."""
    root = tmp_path / "root"
    root.mkdir()
    store = TMStore(root)
    xliff_path = root / ".tzp" / "tms" / "pack_ru.xliff"
    xliff_path.parent.mkdir(parents=True, exist_ok=True)
    xliff_path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2">
  <file source-language="en-US" target-language="ru-RU" datatype="plaintext">
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

    count = store.replace_import_tm(
        xliff_path,
        source_locale="EN",
        target_locale="RU",
        source_locale_raw="en-US",
        target_locale_raw="ru-RU",
        tm_name="pack_ru",
    )
    assert count == 1
    matches = store.query(
        "Hello world",
        source_locale="EN",
        target_locale="RU",
        origins=["import"],
    )
    assert matches
    assert matches[0].tm_name == "pack_ru"
    records = store.list_import_files()
    assert len(records) == 1
    assert records[0].source_locale_raw == "en-US"
    assert records[0].target_locale_raw == "ru-RU"
    store.close()


def test_tm_store_replace_import_tm_with_po(tmp_path: Path) -> None:
    """Verify tm store replace import tm with po."""
    root = tmp_path / "root"
    root.mkdir()
    store = TMStore(root)
    po_path = root / ".tzp" / "tms" / "pack_ru.po"
    po_path.parent.mkdir(parents=True, exist_ok=True)
    po_path.write_text(
        """
msgid ""
msgstr ""
"Language: ru\\n"
"X-Source-Language: en\\n"

msgid "Hello world"
msgstr "Privet mir"
""".strip() + "\n",
        encoding="utf-8",
    )

    count = store.replace_import_tm(
        po_path,
        source_locale="EN",
        target_locale="RU",
        source_locale_raw="en",
        target_locale_raw="ru",
        tm_name="pack_ru",
    )
    assert count == 1
    matches = store.query(
        "Hello world",
        source_locale="EN",
        target_locale="RU",
        origins=["import"],
    )
    assert matches
    assert matches[0].tm_name == "pack_ru"
    records = store.list_import_files()
    assert len(records) == 1
    assert records[0].source_locale_raw == "en"
    assert records[0].target_locale_raw == "ru"
    store.close()
