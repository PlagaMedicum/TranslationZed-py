"""Test module for tm store edge-path coverage."""

from __future__ import annotations

import contextlib
import gc
import sqlite3
import warnings
from pathlib import Path

import translationzed_py.core.tm_store as tm_store_module
from translationzed_py.core.model import Status
from translationzed_py.core.tm_store import (
    TMStore,
    _contains_composed_phrase,
    _exact_token_overlap,
    _normalize_row_status,
    _query_tokens,
    _soft_token_overlap,
    _stem_token,
    _token_matches,
)


def test_tm_store_text_helper_edges_cover_guard_branches() -> None:
    """Verify text helpers handle short tokens and invalid status values."""
    assert _query_tokens("a bb ccc") == ("bb", "ccc")
    assert _stem_token("stories") == "story"
    assert _stem_token("abed") == "abed"
    assert _token_matches("drone", "drxye", use_en_stemming=False) is False
    assert (
        _contains_composed_phrase("alpha beta", "!!!", use_en_stemming=False) is False
    )
    assert _contains_composed_phrase("!!!", "alpha", use_en_stemming=False) is False
    assert _soft_token_overlap(set(), {"alpha"}, use_en_stemming=False) == 0.0
    assert _exact_token_overlap(set(), {"alpha"}) == 0.0

    assert _normalize_row_status(None) is None
    assert _normalize_row_status(Status.TRANSLATED) == int(Status.TRANSLATED)
    assert _normalize_row_status("2") == int(Status.TRANSLATED)
    assert _normalize_row_status("x") is None
    assert _normalize_row_status(object()) is None
    assert _normalize_row_status(99) is None


def test_tm_store_resolve_db_path_covers_primary_and_migration_outcomes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Verify db-path resolution handles primary, migrated, and legacy fallback paths."""
    root = tmp_path / "root"
    root.mkdir()
    config_dir = ".tzp/config"
    primary = root / config_dir / "tm.sqlite"
    legacy = root / ".tzp-config" / "tm.sqlite"
    primary.parent.mkdir(parents=True, exist_ok=True)
    legacy.parent.mkdir(parents=True, exist_ok=True)

    primary.write_text("primary", encoding="utf-8")
    assert TMStore._resolve_db_path(root, config_dir) == primary

    primary.unlink()
    legacy.write_text("legacy", encoding="utf-8")
    monkeypatch.setattr(
        TMStore,
        "_migrate_legacy_db",
        staticmethod(lambda _legacy, _primary: True),
    )
    assert TMStore._resolve_db_path(root, config_dir) == primary

    monkeypatch.setattr(
        TMStore,
        "_migrate_legacy_db",
        staticmethod(lambda _legacy, _primary: False),
    )
    assert TMStore._resolve_db_path(root, config_dir) == legacy


def test_tm_store_migrate_legacy_db_failure_removes_partial_primary(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Verify migration failure removes partially created primary database files."""
    legacy = tmp_path / "legacy.sqlite"
    primary = tmp_path / "primary.sqlite"
    with contextlib.closing(sqlite3.connect(legacy)) as conn:
        conn.execute("CREATE TABLE t(v INTEGER)")
        conn.commit()
    primary.write_text("partial", encoding="utf-8")

    def _boom_connect(_path: Path) -> sqlite3.Connection:
        raise sqlite3.Error("boom")

    monkeypatch.setattr(tm_store_module.sqlite3, "connect", _boom_connect)

    assert TMStore._migrate_legacy_db(legacy, primary) is False
    assert not primary.exists()


def test_tm_store_migrate_legacy_db_success_closes_connections(tmp_path: Path) -> None:
    """Verify successful DB migration does not leak sqlite connections."""
    legacy = tmp_path / "legacy.sqlite"
    primary = tmp_path / "primary.sqlite"
    with contextlib.closing(sqlite3.connect(legacy)) as conn:
        conn.execute("CREATE TABLE t(v INTEGER)")
        conn.execute("INSERT INTO t(v) VALUES (1)")
        conn.commit()

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ResourceWarning)
        assert TMStore._migrate_legacy_db(legacy, primary) is True
        gc.collect()

    resource_warnings = [
        row for row in caught if issubclass(row.category, ResourceWarning)
    ]
    assert not resource_warnings
    with contextlib.closing(sqlite3.connect(primary)) as conn:
        rows = conn.execute("SELECT v FROM t").fetchall()
    assert rows == [(1,)]


def test_tm_store_bootstraps_missing_legacy_columns_and_exports_tmx(
    tmp_path: Path,
) -> None:
    """Verify legacy schema columns are added and TM export includes expected rows."""
    root = tmp_path / "root"
    legacy_db = root / ".tzp-config" / "tm.sqlite"
    legacy_db.parent.mkdir(parents=True, exist_ok=True)
    with contextlib.closing(sqlite3.connect(legacy_db)) as conn:
        conn.execute("""
            CREATE TABLE tm_entries (
                id INTEGER PRIMARY KEY,
                source_text TEXT NOT NULL,
                target_text TEXT NOT NULL,
                source_norm TEXT NOT NULL,
                source_prefix TEXT NOT NULL,
                source_len INTEGER NOT NULL,
                source_locale TEXT NOT NULL,
                target_locale TEXT NOT NULL,
                origin TEXT NOT NULL,
                file_path TEXT,
                key TEXT,
                updated_at INTEGER NOT NULL
            )
            """)
        conn.execute("""
            CREATE TABLE tm_import_files (
                tm_path TEXT PRIMARY KEY,
                tm_name TEXT NOT NULL,
                source_locale TEXT,
                target_locale TEXT,
                mtime_ns INTEGER NOT NULL,
                file_size INTEGER NOT NULL,
                status TEXT NOT NULL,
                note TEXT NOT NULL DEFAULT '',
                updated_at INTEGER NOT NULL
            )
            """)
        conn.commit()

    store = TMStore(root)

    tm_entry_columns = {
        row["name"]
        for row in store._conn.execute("PRAGMA table_info(tm_entries)").fetchall()
    }
    import_file_columns = {
        row["name"]
        for row in store._conn.execute("PRAGMA table_info(tm_import_files)").fetchall()
    }
    assert {"tm_name", "tm_path", "row_status"}.issubset(tm_entry_columns)
    assert {
        "enabled",
        "source_locale_raw",
        "target_locale_raw",
        "segment_count",
    }.issubset(import_file_columns)

    be_path = root / "BE" / "ui.txt"
    be_path.parent.mkdir(parents=True, exist_ok=True)
    store.upsert_project_entries(
        [
            ("dup_1", "Hello", "Прывітанне"),
            ("dup_2", "Hello", "Прывітанне"),
            ("too_long", "x" * 6001, "Long"),
            ("ignored_blank", "", ""),
            ("ignored_wrong", "A", "B", 1, 2),
        ],
        source_locale="EN",
        target_locale="BE",
        file_path=str(be_path),
    )
    store.insert_import_pairs(
        [
            ("Hello", "Import hello"),
            ("", "skip"),
            ("   ", "skip"),
            ("Skip", ""),
        ],
        source_locale="EN",
        target_locale="BE",
        tm_name="pack",
        tm_path=str(root / ".tzp" / "tms" / "pack.tmx"),
    )

    exact = store.query("Hello", source_locale="EN", target_locale="BE", limit=10)
    project_exact = [
        m for m in exact if m.origin == "project" and m.source_text == "Hello"
    ]
    assert len(project_exact) == 1

    assert (
        store.query("Hello", source_locale="EN", target_locale="BE", origins=[]) == []
    )
    assert store.query("   ", source_locale="EN", target_locale="BE") == []

    long_query = "x" * 6001
    long_matches = store.query(
        long_query, source_locale="EN", target_locale="BE", limit=5
    )
    assert any(match.source_text == long_query for match in long_matches)

    out_project = root / "project_only.tmx"
    out_all = root / "all_rows.tmx"
    assert (
        store.export_tmx(
            out_project,
            source_locale="en",
            target_locale="be",
            include_imported=False,
        )
        == 3
    )
    assert (
        store.export_tmx(
            out_all,
            source_locale="en",
            target_locale="be",
            include_imported=True,
        )
        == 4
    )

    assert "Import hello" not in out_project.read_text(encoding="utf-8")
    assert "Import hello" in out_all.read_text(encoding="utf-8")
    store.close()


def test_tm_store_import_tmx_alias_routes_to_import_tm(tmp_path: Path) -> None:
    """Verify import_tmx delegates to TM import pipeline for TMX files."""
    root = tmp_path / "root"
    root.mkdir()
    tmx_path = root / "import.tmx"
    tmx_path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<tmx version="1.4">
  <header creationtool="test" creationtoolversion="1"
          datatype="PlainText" segtype="sentence" srclang="EN" />
  <body>
    <tu>
      <tuv xml:lang="EN"><seg>Hello world</seg></tuv>
      <tuv xml:lang="BE"><seg>Прывітанне свет</seg></tuv>
    </tu>
  </body>
</tmx>
""",
        encoding="utf-8",
    )
    store = TMStore(root)

    count = store.import_tmx(tmx_path, source_locale="EN", target_locale="BE")

    assert count == 1
    assert store.has_import_entries(str(tmx_path)) is True
    store.close()
