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
    assert report.failures == ()
    assert store.query(
        "Hello world",
        source_locale="EN",
        target_locale="RU",
        origins=["import"],
    )
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
