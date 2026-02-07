from pathlib import Path

from translationzed_py.core.tm_preferences import TMPreferencesActions, apply_actions
from translationzed_py.core.tm_store import TMStore


def test_tm_preferences_apply_handles_remove_toggle_and_import(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    store = TMStore(root)

    managed = root / "imported_tms"
    managed.mkdir(parents=True, exist_ok=True)
    existing = managed / "existing.tmx"
    existing.write_text("x", encoding="utf-8")
    stat = existing.stat()
    store.upsert_import_file(
        tm_path=str(existing),
        tm_name="existing",
        source_locale="EN",
        target_locale="BE",
        mtime_ns=stat.st_mtime_ns,
        file_size=stat.st_size,
        enabled=True,
        status="ready",
    )

    source = tmp_path / "source.tmx"
    source.write_text("tmx", encoding="utf-8")

    def _copy_to_managed(path: Path) -> Path:
        dest = managed / path.name
        dest.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        return dest

    actions = TMPreferencesActions(
        remove_paths={str(existing)},
        enabled_map={str(existing): False},
        import_paths=[str(source)],
    )
    report = apply_actions(store, actions, copy_to_import_dir=_copy_to_managed)

    assert report.failures == ()
    assert report.sync_paths == (managed / "source.tmx",)
    assert not existing.exists()
    assert store.list_import_files() == []
    store.close()


def test_tm_preferences_apply_collects_copy_failures(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    store = TMStore(root)
    source = tmp_path / "source.tmx"
    source.write_text("tmx", encoding="utf-8")

    actions = TMPreferencesActions(import_paths=[str(source)])
    report = apply_actions(
        store,
        actions,
        copy_to_import_dir=lambda _path: (_ for _ in ()).throw(OSError("copy failed")),
    )

    assert report.sync_paths == ()
    assert len(report.failures) == 1
    assert "copy failed" in report.failures[0]
    store.close()
