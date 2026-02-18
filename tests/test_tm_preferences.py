"""Test module for tm preferences."""

from pathlib import Path

from translationzed_py.core.tm_preferences import (
    TMPreferencesActions,
    actions_from_values,
    apply_actions,
)
from translationzed_py.core.tm_store import TMStore


def test_tm_preferences_apply_handles_remove_toggle_and_import(tmp_path: Path) -> None:
    """Verify tm preferences apply handles remove toggle and import."""
    root = tmp_path / "root"
    root.mkdir()
    store = TMStore(root)

    managed = root / ".tzp" / "tms"
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
    """Verify tm preferences apply collects copy failures."""
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


def test_tm_preferences_actions_from_values_handles_invalid_and_blank_inputs() -> None:
    """Verify tm preferences action parser normalizes supported value types."""
    actions = actions_from_values(
        {
            "tm_remove_paths": ["  ", "/tmp/a.tmx"],
            "tm_enabled": ["not-a-dict"],
            "tm_import_paths": ["", "  /tmp/b.tmx  "],
        }
    )
    assert actions.remove_paths == {"/tmp/a.tmx"}
    assert actions.enabled_map == {}
    assert actions.import_paths == ["/tmp/b.tmx"]


def test_tm_preferences_apply_handles_unlink_failure_and_toggle_update(
    tmp_path: Path, monkeypatch
) -> None:
    """Verify apply actions records unlink errors and updates enabled states."""
    root = tmp_path / "root"
    root.mkdir()
    store = TMStore(root)
    managed = root / ".tzp" / "tms"
    managed.mkdir(parents=True, exist_ok=True)

    to_remove = managed / "remove_me.tmx"
    to_remove.write_text("x", encoding="utf-8")
    toggle_path = managed / "toggle_me.tmx"
    toggle_path.write_text("x", encoding="utf-8")

    for path, enabled in ((to_remove, True), (toggle_path, True)):
        stat = path.stat()
        store.upsert_import_file(
            tm_path=str(path),
            tm_name=path.stem,
            source_locale="EN",
            target_locale="BE",
            mtime_ns=stat.st_mtime_ns,
            file_size=stat.st_size,
            enabled=enabled,
            status="ready",
        )

    original_unlink = Path.unlink

    def _patched_unlink(path_obj: Path, *args, **kwargs) -> None:
        if path_obj == to_remove:
            raise OSError("cannot remove")
        original_unlink(path_obj, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", _patched_unlink)

    actions = TMPreferencesActions(
        remove_paths={str(to_remove)},
        enabled_map={str(to_remove): False, str(toggle_path): False},
        import_paths=[],
    )
    report = apply_actions(
        store,
        actions,
        copy_to_import_dir=lambda path: path,
    )

    assert len(report.failures) == 1
    assert "cannot remove" in report.failures[0]

    records = {record.tm_path: record for record in store.list_import_files()}
    assert str(to_remove) in records
    assert str(toggle_path) in records
    assert records[str(toggle_path)].enabled is False
    store.close()
