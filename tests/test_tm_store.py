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
    exact = store.query(
        "Hello world", source_locale="EN", target_locale="BE", limit=5
    )
    assert exact
    assert exact[0].score == 100
    assert exact[0].target_text == "Privet mir"

    store.insert_import_pairs(
        [("Hello world!", "Privet mir!")],
        source_locale="EN",
        target_locale="BE",
    )
    fuzzy = store.query("Hello world!!", source_locale="EN", target_locale="BE", limit=5)
    assert any(match.score < 100 for match in fuzzy)
    store.close()
