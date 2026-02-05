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
