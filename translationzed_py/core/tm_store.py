from __future__ import annotations

import contextlib
import re
import sqlite3
import threading
import time
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from .app_config import LEGACY_CONFIG_DIR
from .app_config import load as _load_app_config
from .tmx_io import iter_tmx_pairs, write_tmx

_PROJECT_ORIGIN = "project"
_IMPORT_ORIGIN = "import"
# Store query accepts 5..100 when explicitly requested; GUI default is 50.
_MIN_FUZZY_SCORE = 5
_MAX_FUZZY_CANDIDATES = 1200
_FUZZY_RESERVED_SLOTS = 3
_MAX_FUZZY_SOURCE_LEN = 5000
_IMPORT_VISIBLE_SQL = """
origin != 'import'
OR tm_path IS NULL
OR COALESCE(
    (
        SELECT CASE
            WHEN f.enabled = 1 AND f.status = 'ready' THEN 1
            ELSE 0
        END
        FROM tm_import_files f
        WHERE f.tm_path = tm_entries.tm_path
    ),
    1
) = 1
"""


@dataclass(frozen=True, slots=True)
class TMMatch:
    source_text: str
    target_text: str
    score: int
    origin: str
    tm_name: str | None
    tm_path: str | None
    file_path: str | None
    key: str | None
    updated_at: int


@dataclass(frozen=True, slots=True)
class TMImportFile:
    tm_path: str
    tm_name: str
    source_locale: str
    target_locale: str
    source_locale_raw: str
    target_locale_raw: str
    segment_count: int
    mtime_ns: int
    file_size: int
    enabled: bool
    status: str
    note: str
    updated_at: int


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _prefix(text: str, length: int = 8) -> str:
    return text[:length] if text else ""


def _query_tokens(text: str) -> tuple[str, ...]:
    tokens: list[str] = []
    for token in re.findall(r"\w+", text, flags=re.UNICODE):
        if len(token) < 2:
            continue
        tokens.append(token)
    return tuple(dict.fromkeys(tokens))


def _contains_composed_phrase(text: str, query: str) -> bool:
    if query in text:
        return True
    parts = _query_tokens(query)
    if len(parts) < 2:
        return False
    pos = 0
    for part in parts:
        found = text.find(part, pos)
        if found < 0:
            return False
        pos = found + len(part)
    return True


def _normalize_locale(locale: str) -> str:
    return locale.strip().upper()


def _normalize_origins(origins: Iterable[str] | None) -> tuple[str, ...]:
    if origins is None:
        return (_PROJECT_ORIGIN, _IMPORT_ORIGIN)
    normalized: list[str] = []
    allowed = {_PROJECT_ORIGIN, _IMPORT_ORIGIN}
    for origin in origins:
        if origin in allowed and origin not in normalized:
            normalized.append(origin)
    ordered: list[str] = []
    if _PROJECT_ORIGIN in normalized:
        ordered.append(_PROJECT_ORIGIN)
    if _IMPORT_ORIGIN in normalized:
        ordered.append(_IMPORT_ORIGIN)
    return tuple(ordered)


class TMStore:
    _QUERY_LOCAL = threading.local()

    def __init__(self, root: Path) -> None:
        cfg = _load_app_config(root)
        self._path = self._resolve_db_path(root, cfg.config_dir)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._path)
        self._conn.row_factory = sqlite3.Row
        self._configure()
        self._ensure_schema()

    @staticmethod
    def _resolve_db_path(root: Path, config_dir: str) -> Path:
        primary = root / config_dir / "tm.sqlite"
        legacy = root / LEGACY_CONFIG_DIR / "tm.sqlite"
        if primary.exists():
            return primary
        if legacy == primary or not legacy.exists():
            return primary
        primary.parent.mkdir(parents=True, exist_ok=True)
        if TMStore._migrate_legacy_db(legacy, primary):
            return primary
        return legacy

    @staticmethod
    def _migrate_legacy_db(legacy: Path, primary: Path) -> bool:
        try:
            with sqlite3.connect(legacy) as src, sqlite3.connect(primary) as dst:
                src.backup(dst)
            return True
        except sqlite3.Error:
            with contextlib.suppress(OSError):
                primary.unlink(missing_ok=True)
            return False

    def close(self) -> None:
        self._conn.close()

    @property
    def db_path(self) -> Path:
        return self._path

    def has_entries(self, *, source_locale: str, target_locale: str) -> bool:
        source_locale = _normalize_locale(source_locale)
        target_locale = _normalize_locale(target_locale)
        row = self._conn.execute(
            """
            SELECT 1
            FROM tm_entries
            WHERE source_locale = ? AND target_locale = ?
            LIMIT 1
            """,
            (source_locale, target_locale),
        ).fetchone()
        return row is not None

    @staticmethod
    def _configure_conn(conn: sqlite3.Connection) -> None:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA temp_store=MEMORY")

    def _configure(self) -> None:
        self._configure_conn(self._conn)

    @classmethod
    def _query_conn_for_path(cls, db_path: Path) -> sqlite3.Connection:
        local = cls._QUERY_LOCAL
        conn = getattr(local, "conn", None)
        path = getattr(local, "path", None)
        if conn is None or path != db_path:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cls._configure_conn(conn)
            local.conn = conn
            local.path = db_path
        return conn

    def _ensure_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tm_entries (
                id INTEGER PRIMARY KEY,
                source_text TEXT NOT NULL,
                target_text TEXT NOT NULL,
                source_norm TEXT NOT NULL,
                source_prefix TEXT NOT NULL,
                source_len INTEGER NOT NULL,
                source_locale TEXT NOT NULL,
                target_locale TEXT NOT NULL,
                origin TEXT NOT NULL,
                tm_name TEXT,
                tm_path TEXT,
                file_path TEXT,
                key TEXT,
                updated_at INTEGER NOT NULL
            )
            """
        )
        self._ensure_tm_entries_columns()
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tm_import_files (
                tm_path TEXT PRIMARY KEY,
                tm_name TEXT NOT NULL,
                source_locale TEXT,
                target_locale TEXT,
                source_locale_raw TEXT NOT NULL DEFAULT '',
                target_locale_raw TEXT NOT NULL DEFAULT '',
                segment_count INTEGER NOT NULL DEFAULT 0,
                mtime_ns INTEGER NOT NULL,
                file_size INTEGER NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL,
                note TEXT NOT NULL DEFAULT '',
                updated_at INTEGER NOT NULL
            )
            """
        )
        self._ensure_tm_import_files_columns()
        self._conn.execute("DROP INDEX IF EXISTS tm_project_key")
        self._conn.execute("DROP INDEX IF EXISTS tm_import_unique")
        self._conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS tm_project_key
            ON tm_entries(origin, source_locale, target_locale, file_path, key)
            """
        )
        self._conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS tm_import_unique
            ON tm_entries(
                origin,
                source_locale,
                target_locale,
                tm_name,
                source_norm,
                target_text
            )
            WHERE origin = 'import'
            """
        )
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS tm_exact_lookup
            ON tm_entries(source_locale, target_locale, source_norm, origin)
            """
        )
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS tm_prefix_lookup
            ON tm_entries(source_locale, target_locale, source_prefix, source_len)
            """
        )
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS tm_import_path_lookup
            ON tm_entries(origin, tm_path)
            """
        )
        self._conn.commit()

    def _ensure_tm_entries_columns(self) -> None:
        cols = {
            row["name"]
            for row in self._conn.execute("PRAGMA table_info(tm_entries)").fetchall()
        }
        if "tm_name" not in cols:
            self._conn.execute("ALTER TABLE tm_entries ADD COLUMN tm_name TEXT")
        if "tm_path" not in cols:
            self._conn.execute("ALTER TABLE tm_entries ADD COLUMN tm_path TEXT")

    def _ensure_tm_import_files_columns(self) -> None:
        cols = {
            row["name"]
            for row in self._conn.execute(
                "PRAGMA table_info(tm_import_files)"
            ).fetchall()
        }
        if "enabled" not in cols:
            self._conn.execute(
                "ALTER TABLE tm_import_files ADD COLUMN enabled INTEGER NOT NULL DEFAULT 1"
            )
        if "source_locale_raw" not in cols:
            self._conn.execute(
                "ALTER TABLE tm_import_files ADD COLUMN source_locale_raw TEXT NOT NULL DEFAULT ''"
            )
        if "target_locale_raw" not in cols:
            self._conn.execute(
                "ALTER TABLE tm_import_files ADD COLUMN target_locale_raw TEXT NOT NULL DEFAULT ''"
            )
        if "segment_count" not in cols:
            self._conn.execute(
                "ALTER TABLE tm_import_files ADD COLUMN segment_count INTEGER NOT NULL DEFAULT 0"
            )

    def upsert_project_entries(
        self,
        entries: Iterable[tuple[str, str, str]],
        *,
        source_locale: str,
        target_locale: str,
        file_path: str,
        updated_at: int | None = None,
    ) -> int:
        source_locale = _normalize_locale(source_locale)
        target_locale = _normalize_locale(target_locale)
        now = int(updated_at if updated_at is not None else time.time())
        count = 0
        rows = []
        for key, source_text, target_text in entries:
            if not (source_text or target_text):
                continue
            source_norm = _normalize(source_text)
            if not source_norm:
                continue
            rows.append(
                (
                    source_text,
                    target_text,
                    source_norm,
                    _prefix(source_norm),
                    len(source_norm),
                    source_locale,
                    target_locale,
                    _PROJECT_ORIGIN,
                    None,
                    None,
                    file_path,
                    key,
                    now,
                )
            )
        if not rows:
            return 0
        cur = self._conn.executemany(
            """
            INSERT INTO tm_entries (
                source_text,
                target_text,
                source_norm,
                source_prefix,
                source_len,
                source_locale,
                target_locale,
                origin,
                tm_name,
                tm_path,
                file_path,
                key,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(origin, source_locale, target_locale, file_path, key)
            DO UPDATE SET
                source_text=excluded.source_text,
                target_text=excluded.target_text,
                source_norm=excluded.source_norm,
                source_prefix=excluded.source_prefix,
                source_len=excluded.source_len,
                updated_at=excluded.updated_at
            """,
            rows,
        )
        count += cur.rowcount if cur.rowcount >= 0 else 0
        self._conn.commit()
        return count

    def insert_import_pairs(
        self,
        pairs: Iterable[tuple[str, str]],
        *,
        source_locale: str,
        target_locale: str,
        tm_name: str | None = None,
        tm_path: str | None = None,
        updated_at: int | None = None,
    ) -> int:
        source_locale = _normalize_locale(source_locale)
        target_locale = _normalize_locale(target_locale)
        tm_name = (tm_name or "").strip() or None
        tm_path = str(tm_path).strip() if tm_path else None
        now = int(updated_at if updated_at is not None else time.time())
        rows = []
        for source_text, target_text in pairs:
            if not (source_text and target_text):
                continue
            source_norm = _normalize(source_text)
            if not source_norm:
                continue
            rows.append(
                (
                    source_text,
                    target_text,
                    source_norm,
                    _prefix(source_norm),
                    len(source_norm),
                    source_locale,
                    target_locale,
                    _IMPORT_ORIGIN,
                    tm_name,
                    tm_path,
                    None,
                    None,
                    now,
                )
            )
        if not rows:
            return 0
        cur = self._conn.executemany(
            """
            INSERT OR IGNORE INTO tm_entries (
                source_text,
                target_text,
                source_norm,
                source_prefix,
                source_len,
                source_locale,
                target_locale,
                origin,
                tm_name,
                tm_path,
                file_path,
                key,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        count = cur.rowcount if cur.rowcount >= 0 else 0
        self._conn.commit()
        return count

    def import_tmx(self, path: Path, *, source_locale: str, target_locale: str) -> int:
        source_locale = _normalize_locale(source_locale)
        target_locale = _normalize_locale(target_locale)
        pairs = iter_tmx_pairs(path, source_locale, target_locale)
        return self.insert_import_pairs(
            pairs,
            source_locale=source_locale,
            target_locale=target_locale,
            tm_name=path.stem,
            tm_path=str(path),
        )

    def replace_import_tmx(
        self,
        path: Path,
        *,
        source_locale: str,
        target_locale: str,
        source_locale_raw: str = "",
        target_locale_raw: str = "",
        tm_name: str | None = None,
    ) -> int:
        source_locale = _normalize_locale(source_locale)
        target_locale = _normalize_locale(target_locale)
        name = (tm_name or path.stem).strip() or path.stem
        path_str = str(path)
        enabled = True
        row = self._conn.execute(
            """
            SELECT enabled
            FROM tm_import_files
            WHERE tm_path = ?
            """,
            (path_str,),
        ).fetchone()
        if row is not None:
            enabled = bool(row["enabled"])
        self._conn.execute(
            """
            DELETE FROM tm_entries
            WHERE origin = ? AND tm_path = ?
            """,
            (_IMPORT_ORIGIN, path_str),
        )
        count = self.insert_import_pairs(
            iter_tmx_pairs(path, source_locale, target_locale),
            source_locale=source_locale,
            target_locale=target_locale,
            tm_name=name,
            tm_path=path_str,
        )
        self.upsert_import_file(
            tm_path=path_str,
            tm_name=name,
            source_locale=source_locale,
            target_locale=target_locale,
            source_locale_raw=source_locale_raw.strip(),
            target_locale_raw=target_locale_raw.strip(),
            segment_count=count,
            mtime_ns=path.stat().st_mtime_ns,
            file_size=path.stat().st_size,
            enabled=enabled,
            status="ready",
            note="",
        )
        return count

    def list_import_files(self) -> list[TMImportFile]:
        rows = self._conn.execute(
            """
            SELECT
                tm_path,
                tm_name,
                COALESCE(source_locale, '') AS source_locale,
                COALESCE(target_locale, '') AS target_locale,
                COALESCE(source_locale_raw, '') AS source_locale_raw,
                COALESCE(target_locale_raw, '') AS target_locale_raw,
                COALESCE(segment_count, 0) AS segment_count,
                mtime_ns,
                file_size,
                enabled,
                status,
                note,
                updated_at
            FROM tm_import_files
            ORDER BY tm_name COLLATE NOCASE, tm_path
            """
        ).fetchall()
        return [
            TMImportFile(
                tm_path=row["tm_path"],
                tm_name=row["tm_name"],
                source_locale=row["source_locale"],
                target_locale=row["target_locale"],
                source_locale_raw=row["source_locale_raw"],
                target_locale_raw=row["target_locale_raw"],
                segment_count=int(row["segment_count"]),
                mtime_ns=int(row["mtime_ns"]),
                file_size=int(row["file_size"]),
                enabled=bool(row["enabled"]),
                status=row["status"],
                note=row["note"],
                updated_at=int(row["updated_at"]),
            )
            for row in rows
        ]

    def upsert_import_file(
        self,
        *,
        tm_path: str,
        tm_name: str,
        source_locale: str = "",
        target_locale: str = "",
        source_locale_raw: str = "",
        target_locale_raw: str = "",
        segment_count: int = 0,
        mtime_ns: int,
        file_size: int,
        enabled: bool = True,
        status: str,
        note: str = "",
        updated_at: int | None = None,
    ) -> None:
        now = int(updated_at if updated_at is not None else time.time())
        self._conn.execute(
            """
            INSERT INTO tm_import_files(
                tm_path,
                tm_name,
                source_locale,
                target_locale,
                source_locale_raw,
                target_locale_raw,
                segment_count,
                mtime_ns,
                file_size,
                enabled,
                status,
                note,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(tm_path) DO UPDATE SET
                tm_name=excluded.tm_name,
                source_locale=excluded.source_locale,
                target_locale=excluded.target_locale,
                source_locale_raw=excluded.source_locale_raw,
                target_locale_raw=excluded.target_locale_raw,
                segment_count=excluded.segment_count,
                mtime_ns=excluded.mtime_ns,
                file_size=excluded.file_size,
                enabled=excluded.enabled,
                status=excluded.status,
                note=excluded.note,
                updated_at=excluded.updated_at
            """,
            (
                tm_path,
                tm_name,
                _normalize_locale(source_locale) if source_locale else "",
                _normalize_locale(target_locale) if target_locale else "",
                source_locale_raw.strip(),
                target_locale_raw.strip(),
                max(0, int(segment_count)),
                int(mtime_ns),
                int(file_size),
                1 if enabled else 0,
                status,
                note,
                now,
            ),
        )
        self._conn.commit()

    def set_import_enabled(self, tm_path: str, enabled: bool) -> None:
        self._conn.execute(
            """
            UPDATE tm_import_files
            SET enabled = ?, updated_at = ?
            WHERE tm_path = ?
            """,
            (1 if enabled else 0, int(time.time()), tm_path),
        )
        self._conn.commit()

    def delete_import_file(self, tm_path: str) -> None:
        self._conn.execute(
            """
            DELETE FROM tm_entries
            WHERE origin = ? AND tm_path = ?
            """,
            (_IMPORT_ORIGIN, tm_path),
        )
        self._conn.execute(
            """
            DELETE FROM tm_import_files
            WHERE tm_path = ?
            """,
            (tm_path,),
        )
        self._conn.commit()

    def has_import_entries(self, tm_path: str) -> bool:
        row = self._conn.execute(
            """
            SELECT 1
            FROM tm_entries
            WHERE origin = ? AND tm_path = ?
            LIMIT 1
            """,
            (_IMPORT_ORIGIN, tm_path),
        ).fetchone()
        return row is not None

    def export_tmx(
        self,
        path: Path,
        *,
        source_locale: str,
        target_locale: str,
        include_imported: bool = True,
    ) -> int:
        source_locale = _normalize_locale(source_locale)
        target_locale = _normalize_locale(target_locale)
        origins = (
            (_PROJECT_ORIGIN, _IMPORT_ORIGIN)
            if include_imported
            else (_PROJECT_ORIGIN,)
        )
        rows = self._conn.execute(
            """
            SELECT source_text, target_text
            FROM tm_entries
            WHERE source_locale = ? AND target_locale = ? AND origin IN (?, ?)
            ORDER BY updated_at DESC
            """,
            (source_locale, target_locale, origins[0], origins[-1]),
        ).fetchall()
        pairs = [(row["source_text"], row["target_text"]) for row in rows]
        write_tmx(path, pairs, source_locale=source_locale, target_locale=target_locale)
        return len(pairs)

    def query(
        self,
        source_text: str,
        *,
        source_locale: str,
        target_locale: str,
        limit: int = 10,
        min_score: int | None = None,
        origins: Iterable[str] | None = None,
    ) -> list[TMMatch]:
        return self._query_conn(
            self._conn,
            source_text,
            source_locale=source_locale,
            target_locale=target_locale,
            limit=limit,
            min_score=min_score,
            origins=origins,
        )

    @classmethod
    def query_path(
        cls,
        db_path: Path,
        source_text: str,
        *,
        source_locale: str,
        target_locale: str,
        limit: int = 10,
        min_score: int | None = None,
        origins: Iterable[str] | None = None,
    ) -> list[TMMatch]:
        conn = cls._query_conn_for_path(db_path)
        return cls._query_conn(
            conn,
            source_text,
            source_locale=source_locale,
            target_locale=target_locale,
            limit=limit,
            min_score=min_score,
            origins=origins,
        )

    @classmethod
    def _query_conn(
        cls,
        conn: sqlite3.Connection,
        source_text: str,
        *,
        source_locale: str,
        target_locale: str,
        limit: int,
        min_score: int | None,
        origins: Iterable[str] | None,
    ) -> list[TMMatch]:
        source_locale = _normalize_locale(source_locale)
        target_locale = _normalize_locale(target_locale)
        origin_list = _normalize_origins(origins)
        if not origin_list:
            return []
        if min_score is None:
            min_score = _MIN_FUZZY_SCORE
        min_score = max(_MIN_FUZZY_SCORE, min(100, int(min_score)))
        norm = _normalize(source_text)
        if not norm:
            return []
        origin_params: tuple[str, ...]
        if len(origin_list) == 1:
            origin_clause = "origin = ?"
            origin_params = (origin_list[0],)
        else:
            origin_clause = "origin IN (?, ?)"
            origin_params = (origin_list[0], origin_list[1])
        exact_rows = conn.execute(
            f"""
            SELECT
                source_text,
                target_text,
                origin,
                tm_name,
                tm_path,
                file_path,
                key,
                updated_at
            FROM tm_entries
            WHERE source_locale = ? AND target_locale = ? AND source_norm = ?
              AND ({_IMPORT_VISIBLE_SQL})
              AND {origin_clause}
            ORDER BY CASE origin WHEN 'project' THEN 0 ELSE 1 END, updated_at DESC
            """,
            (source_locale, target_locale, norm, *origin_params),
        ).fetchall()
        matches: list[TMMatch] = []
        seen: set[tuple[str, str, str, str | None]] = set()
        max_exact = max(1, limit - _FUZZY_RESERVED_SLOTS)
        for row in exact_rows:
            key = (
                row["source_text"],
                row["target_text"],
                row["origin"],
                row["tm_name"],
            )
            if key in seen:
                continue
            seen.add(key)
            matches.append(
                TMMatch(
                    source_text=row["source_text"],
                    target_text=row["target_text"],
                    score=100,
                    origin=row["origin"],
                    tm_name=row["tm_name"],
                    tm_path=row["tm_path"],
                    file_path=row["file_path"],
                    key=row["key"],
                    updated_at=row["updated_at"],
                )
            )
            if len(matches) >= max_exact:
                break
        if len(norm) > _MAX_FUZZY_SOURCE_LEN:
            return matches
        candidates = cls._fuzzy_candidates(
            conn,
            norm,
            source_locale,
            target_locale,
            origin_list,
        )
        for cand, score in candidates:
            if cand["source_norm"] == norm:
                continue
            key = (
                cand["source_text"],
                cand["target_text"],
                cand["origin"],
                cand["tm_name"],
            )
            if key in seen:
                continue
            if score < min_score:
                continue
            seen.add(key)
            matches.append(
                TMMatch(
                    source_text=cand["source_text"],
                    target_text=cand["target_text"],
                    score=score,
                    origin=cand["origin"],
                    tm_name=cand["tm_name"],
                    tm_path=cand["tm_path"],
                    file_path=cand["file_path"],
                    key=cand["key"],
                    updated_at=cand["updated_at"],
                )
            )
            if len(matches) >= limit:
                break
        return matches

    @staticmethod
    def _fuzzy_candidates(
        conn: sqlite3.Connection,
        norm: str,
        source_locale: str,
        target_locale: str,
        origins: Iterable[str],
    ) -> list[tuple[sqlite3.Row, int]]:
        from difflib import SequenceMatcher

        query_tokens = set(_query_tokens(norm))
        origin_list = _normalize_origins(origins)
        if not origin_list:
            return []
        origin_params: tuple[str, ...]
        if len(origin_list) == 1:
            origin_clause = "origin = ?"
            origin_params = (origin_list[0],)
        else:
            origin_clause = "origin IN (?, ?)"
            origin_params = (origin_list[0], origin_list[1])
        # Keep lookup prefix length aligned with stored/indexed source_prefix.
        prefix = _prefix(norm)
        length = len(norm)
        min_len = max(1, int(length * 0.6))
        max_len = int(length * 1.4) if length > 5 else length + 10
        rows = conn.execute(
            f"""
                SELECT source_text, source_norm, target_text, origin, file_path, key, updated_at
                     , tm_name, tm_path
                FROM tm_entries
                WHERE source_locale = ? AND target_locale = ? AND source_prefix = ?
                  AND source_len BETWEEN ? AND ?
                  AND ({_IMPORT_VISIBLE_SQL})
                  AND {origin_clause}
                ORDER BY updated_at DESC
            LIMIT ?
            """,
            (
                source_locale,
                target_locale,
                prefix,
                min_len,
                max_len,
                *origin_params,
                _MAX_FUZZY_CANDIDATES,
            ),
        ).fetchall()
        if not rows:
            rows = conn.execute(
                f"""
                SELECT source_text, source_norm, target_text, origin, file_path, key, updated_at
                     , tm_name, tm_path
                FROM tm_entries
                WHERE source_locale = ? AND target_locale = ?
                  AND source_len BETWEEN ? AND ?
                  AND ({_IMPORT_VISIBLE_SQL})
                  AND {origin_clause}
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (
                    source_locale,
                    target_locale,
                    min_len,
                    max_len,
                    *origin_params,
                    _MAX_FUZZY_CANDIDATES,
                ),
            ).fetchall()
        scored: list[tuple[sqlite3.Row, int]] = []
        for row in rows:
            cand_norm = row["source_norm"]
            if query_tokens:
                cand_tokens = set(_query_tokens(cand_norm))
                if cand_tokens:
                    overlap = len(query_tokens & cand_tokens) / max(
                        1, len(query_tokens)
                    )
                    if overlap < 0.5:
                        continue
            ratio = SequenceMatcher(None, norm, cand_norm, autojunk=False).ratio()
            score = int(round(ratio * 100))
            if _contains_composed_phrase(cand_norm, norm):
                score = max(score, 90)
            scored.append((row, score))
        scored.sort(
            key=lambda item: (
                -item[1],
                0 if item[0]["origin"] == _PROJECT_ORIGIN else 1,
                -item[0]["updated_at"],
            )
        )
        return scored
