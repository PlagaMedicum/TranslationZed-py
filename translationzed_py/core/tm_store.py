"""Tm store module."""

from __future__ import annotations

import contextlib
import functools
import re
import sqlite3
import time
from collections import OrderedDict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from .app_config import LEGACY_CONFIG_DIR
from .app_config import load as _load_app_config
from .model import Status
from .tm_query_contracts import (
    TMFuzzyCallbacks,
    TMFuzzyRuntime,
    TMQueryCallbacks,
    TMQueryRuntime,
)
from .tm_query_engine import fuzzy_candidates as _fuzzy_candidates_engine
from .tm_query_engine import query_conn as _query_conn_engine
from .tm_query_policy import normalize_for_match as _normalize
from .tm_query_policy import strip_tm_wrappers as _strip_tm_wrappers_impl
from .tm_query_text import (
    contains_composed_phrase_uncached as _contains_phrase_uncached,
)
from .tm_query_text import token_matches_uncached as _token_matches_uncached_impl
from .tm_store_support import (
    is_project_upsert_conflict_mismatch as _is_project_upsert_conflict_mismatch,
)
from .tm_store_support import normalize_locale as _normalize_locale
from .tm_store_support import normalize_origins as _normalize_origins
from .tm_store_support import normalize_row_status as _normalize_row_status
from .tm_store_support import prefix as _prefix
from .tmx_io import iter_tm_pairs, write_tmx

_PROJECT_ORIGIN = "project"
_IMPORT_ORIGIN = "import"
_MIN_FUZZY_SCORE = 5
_MAX_FUZZY_CANDIDATES = 1200
_FUZZY_RESERVED_SLOTS = 3
_FUZZY_BUCKET_CANDIDATES = 600
_SHORT_QUERY_LEN = 4
_SHORT_QUERY_RESERVED_SLOTS = 6
_SHORT_QUERY_MAX_CANDIDATES = 5000
_SHORT_QUERY_BUCKET_CANDIDATES = 2500
_MULTI_TOKEN_LEN_PADDING = 4
_MAX_FUZZY_SOURCE_LEN = 5000
_TOKEN_CACHE_CAP = 8192
_STEM_CACHE_CAP = 4096
_PHRASE_MATCH_CACHE_CAP = 2048
_TOKEN_MATCH_CACHE_CAP = 8192
_QUERY_RESULT_CACHE_CAP = 256
_TOKEN_RE = re.compile(r"\w+", flags=re.UNICODE)
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
_QUERY_RUNTIME = TMQueryRuntime(
    min_fuzzy_score=_MIN_FUZZY_SCORE,
    short_query_len=_SHORT_QUERY_LEN,
    fuzzy_reserved_slots=_FUZZY_RESERVED_SLOTS,
    short_query_reserved_slots=_SHORT_QUERY_RESERVED_SLOTS,
    max_fuzzy_source_len=_MAX_FUZZY_SOURCE_LEN,
    project_origin=_PROJECT_ORIGIN,
    import_visible_sql=_IMPORT_VISIBLE_SQL,
)
_FUZZY_RUNTIME = TMFuzzyRuntime(
    max_fuzzy_candidates=_MAX_FUZZY_CANDIDATES,
    fuzzy_bucket_candidates=_FUZZY_BUCKET_CANDIDATES,
    short_query_len=_SHORT_QUERY_LEN,
    short_query_max_candidates=_SHORT_QUERY_MAX_CANDIDATES,
    short_query_bucket_candidates=_SHORT_QUERY_BUCKET_CANDIDATES,
    multi_token_len_padding=_MULTI_TOKEN_LEN_PADDING,
    project_origin=_PROJECT_ORIGIN,
    import_visible_sql=_IMPORT_VISIBLE_SQL,
)

ProjectEntryRow = (
    tuple[str, str, str] | tuple[str, str, str, int] | tuple[str, str, str, Status]
)


@dataclass(frozen=True, slots=True)
class TMMatch:
    """Represent TMMatch."""

    source_text: str
    target_text: str
    score: int
    origin: str
    tm_name: str | None
    tm_path: str | None
    file_path: str | None
    key: str | None
    updated_at: int
    raw_score: int | None = None
    row_status: int | None = None


@dataclass(frozen=True, slots=True)
class TMImportFile:
    """Represent TMImportFile."""

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


_strip_tm_wrappers = _strip_tm_wrappers_impl


def _query_tokens(text: str) -> tuple[str, ...]:
    """Execute query tokens."""
    tokens: list[str] = []
    seen: set[str] = set()
    for token in _TOKEN_RE.findall(text):
        if len(token) < 2:
            continue
        if token in seen:
            continue
        seen.add(token)
        tokens.append(token)
    return tuple(tokens)


@functools.lru_cache(maxsize=_TOKEN_CACHE_CAP)
def _query_tokens_cached(text: str) -> tuple[str, ...]:
    """Cache tokenization for repeated query/candidate normalization."""
    return _query_tokens(text)


def _stem_token(token: str) -> str:
    """Execute stem token."""
    if len(token) <= 3:
        return token
    if token.endswith("ies") and len(token) > 4:
        return token[:-3] + "y"
    for suffix in ("ing", "ed", "ers", "er", "es", "s", "ly"):
        if not token.endswith(suffix):
            continue
        if len(token) - len(suffix) < 3:
            continue
        stem = token[: -len(suffix)]
        # Normalize doubled trailing consonants: "running" -> "run".
        if len(stem) >= 3 and stem[-1] == stem[-2]:
            stem = stem[:-1]
        return stem
    return token


@functools.lru_cache(maxsize=_STEM_CACHE_CAP)
def _stem_token_cached(token: str) -> str:
    """Cache normalized stems used by token-matching heuristics."""
    return _stem_token(token)


def _token_matches(
    query_token: str,
    candidate_token: str,
    *,
    use_en_stemming: bool,
) -> bool:
    return _token_matches_cached(query_token, candidate_token, use_en_stemming)


def _token_matches_uncached(
    query_token: str,
    candidate_token: str,
    use_en_stemming: bool,
) -> bool:
    """Execute token matches."""
    return _token_matches_uncached_impl(
        query_token,
        candidate_token,
        use_en_stemming=use_en_stemming,
        stem_token_cached=_stem_token_cached,
    )


@functools.lru_cache(maxsize=_TOKEN_MATCH_CACHE_CAP)
def _token_matches_cached(
    query_token: str,
    candidate_token: str,
    use_en_stemming: bool,
) -> bool:
    return _token_matches_uncached(query_token, candidate_token, use_en_stemming)


def _contains_composed_phrase(
    text: str,
    query: str,
    *,
    use_en_stemming: bool,
) -> bool:
    """Execute contains composed phrase."""
    return _contains_composed_phrase_cached(text, query, use_en_stemming)


def _contains_composed_phrase_uncached(
    text: str,
    query: str,
    use_en_stemming: bool,
) -> bool:
    return _contains_phrase_uncached(
        text,
        query,
        use_en_stemming=use_en_stemming,
        query_tokens_cached=_query_tokens_cached,
        token_matches=lambda query_token, candidate_token: _token_matches(
            query_token,
            candidate_token,
            use_en_stemming=use_en_stemming,
        ),
    )


@functools.lru_cache(maxsize=_PHRASE_MATCH_CACHE_CAP)
def _contains_composed_phrase_cached(
    text: str,
    query: str,
    use_en_stemming: bool,
) -> bool:
    return _contains_composed_phrase_uncached(text, query, use_en_stemming)


def _soft_token_overlap(
    query_tokens: set[str],
    candidate_tokens: set[str],
    *,
    use_en_stemming: bool,
) -> float:
    """Execute soft token overlap."""
    if not query_tokens or not candidate_tokens:
        return 0.0
    matched = 0
    for query_token in query_tokens:
        if any(
            _token_matches(
                query_token,
                cand,
                use_en_stemming=use_en_stemming,
            )
            for cand in candidate_tokens
        ):
            matched += 1
    return matched / max(1, len(query_tokens))


def _exact_token_overlap(
    query_tokens: set[str],
    candidate_tokens: set[str],
) -> float:
    """Execute exact token overlap."""
    if not query_tokens or not candidate_tokens:
        return 0.0
    matched = sum(1 for token in query_tokens if token in candidate_tokens)
    return matched / max(1, len(query_tokens))


def clear_query_caches() -> None:
    """Clear TM fuzzy-query helper caches."""
    _query_tokens_cached.cache_clear()
    _stem_token_cached.cache_clear()
    _token_matches_cached.cache_clear()
    _contains_composed_phrase_cached.cache_clear()


def query_cache_stats() -> dict[str, object]:
    """Return LRU cache stats for TM fuzzy-query helper caches."""
    return {
        "token": _query_tokens_cached.cache_info(),
        "stem": _stem_token_cached.cache_info(),
        "token_match": _token_matches_cached.cache_info(),
        "phrase": _contains_composed_phrase_cached.cache_info(),
    }


class TMStore:
    """Represent TMStore."""

    def __init__(self, root: Path) -> None:
        """Initialize the instance."""
        cfg = _load_app_config(root)
        self._path = self._resolve_db_path(root, cfg.config_dir)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._path)
        self._closed = False
        self._query_revision = 0
        self._query_cache: OrderedDict[tuple[object, ...], tuple[TMMatch, ...]] = (
            OrderedDict()
        )
        self._conn.row_factory = sqlite3.Row
        self._configure()
        self._ensure_schema()

    def _invalidate_query_cache(self) -> None:
        self._query_revision += 1
        self._query_cache.clear()

    def clear_runtime_caches(self) -> None:
        """Clear query result cache and fuzzy-helper caches for this runtime."""
        self._invalidate_query_cache()
        clear_query_caches()

    def _query_cache_get(self, key: tuple[object, ...]) -> list[TMMatch] | None:
        if _QUERY_RESULT_CACHE_CAP <= 0:
            return None
        cached = self._query_cache.get(key)
        if cached is None:
            return None
        self._query_cache.move_to_end(key)
        return list(cached)

    def _query_cache_put(self, key: tuple[object, ...], matches: list[TMMatch]) -> None:
        if _QUERY_RESULT_CACHE_CAP <= 0:
            return
        self._query_cache[key] = tuple(matches)
        self._query_cache.move_to_end(key)
        while len(self._query_cache) > _QUERY_RESULT_CACHE_CAP:
            self._query_cache.popitem(last=False)

    @staticmethod
    def _resolve_db_path(root: Path, config_dir: str) -> Path:
        """Resolve db path."""
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
        """Execute migrate legacy db."""
        try:
            with (
                contextlib.closing(sqlite3.connect(legacy)) as src,
                contextlib.closing(sqlite3.connect(primary)) as dst,
            ):
                src.backup(dst)
            return True
        except sqlite3.Error:
            with contextlib.suppress(OSError):
                primary.unlink(missing_ok=True)
            return False

    def close(self) -> None:
        """Execute close."""
        if self._closed:
            return
        self._conn.close()
        self._closed = True

    def __del__(self) -> None:
        """Clean up resources."""
        with contextlib.suppress(Exception):
            self.close()

    @property
    def db_path(self) -> Path:
        """Execute db path."""
        return self._path

    def has_entries(self, *, source_locale: str, target_locale: str) -> bool:
        """Return whether entries."""
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
        """Execute configure conn."""
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA temp_store=MEMORY")

    def _configure(self) -> None:
        """Execute configure."""
        self._configure_conn(self._conn)

    @classmethod
    def _query_conn_for_path(cls, db_path: Path) -> sqlite3.Connection:
        """Execute query conn for path."""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cls._configure_conn(conn)
        return conn

    def _ensure_schema(self) -> None:
        """Execute ensure schema."""
        self._conn.execute("""
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
                row_status INTEGER,
                updated_at INTEGER NOT NULL
            )
            """)
        self._ensure_tm_entries_columns()
        self._conn.execute("""
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
            """)
        self._ensure_tm_import_files_columns()
        self._conn.execute("DROP INDEX IF EXISTS tm_project_key")
        self._conn.execute("DROP INDEX IF EXISTS tm_import_unique")
        self._conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS tm_project_key
            ON tm_entries(origin, source_locale, target_locale, file_path, key)
            """)
        self._conn.execute("""
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
            """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS tm_exact_lookup
            ON tm_entries(source_locale, target_locale, source_norm, origin)
            """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS tm_prefix_lookup
            ON tm_entries(source_locale, target_locale, source_prefix, source_len)
            """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS tm_len_lookup
            ON tm_entries(source_locale, target_locale, source_len, origin)
            """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS tm_import_path_lookup
            ON tm_entries(origin, tm_path)
            """)
        self._conn.commit()

    def _ensure_tm_entries_columns(self) -> None:
        """Execute ensure tm entries columns."""
        cols = {
            row["name"]
            for row in self._conn.execute("PRAGMA table_info(tm_entries)").fetchall()
        }
        if "file_path" not in cols:
            self._conn.execute("ALTER TABLE tm_entries ADD COLUMN file_path TEXT")
        if "key" not in cols:
            self._conn.execute("ALTER TABLE tm_entries ADD COLUMN key TEXT")
        if "tm_name" not in cols:
            self._conn.execute("ALTER TABLE tm_entries ADD COLUMN tm_name TEXT")
        if "tm_path" not in cols:
            self._conn.execute("ALTER TABLE tm_entries ADD COLUMN tm_path TEXT")
        if "row_status" not in cols:
            self._conn.execute("ALTER TABLE tm_entries ADD COLUMN row_status INTEGER")

    def _ensure_tm_import_files_columns(self) -> None:
        """Execute ensure tm import files columns."""
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
        entries: Iterable[ProjectEntryRow],
        *,
        source_locale: str,
        target_locale: str,
        file_path: str,
        updated_at: int | None = None,
    ) -> int:
        """Upsert project entries."""
        source_locale = _normalize_locale(source_locale)
        target_locale = _normalize_locale(target_locale)
        now = int(updated_at if updated_at is not None else time.time())
        count = 0
        rows: list[tuple[object, ...]] = []
        for row in entries:
            if len(row) == 3:
                key, source_text, target_text = row
                row_status: int | None = None
            elif len(row) == 4:
                key, source_text, target_text, status_raw = row
                row_status = _normalize_row_status(status_raw)
            else:
                continue
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
                    row_status,
                    now,
                )
            )
        if not rows:
            return 0
        try:
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
                    row_status,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(origin, source_locale, target_locale, file_path, key)
                DO UPDATE SET
                    source_text=excluded.source_text,
                    target_text=excluded.target_text,
                    source_norm=excluded.source_norm,
                    source_prefix=excluded.source_prefix,
                    source_len=excluded.source_len,
                    row_status=excluded.row_status,
                    updated_at=excluded.updated_at
                """,
                rows,
            )
            count += cur.rowcount if cur.rowcount >= 0 else 0
            self._conn.commit()
            self._invalidate_query_cache()
            return count
        except sqlite3.OperationalError as exc:
            if not _is_project_upsert_conflict_mismatch(exc):
                raise
            return self._upsert_project_entries_fallback(rows)

    def _upsert_project_entries_fallback(self, rows: list[tuple[object, ...]]) -> int:
        """Compatibility fallback for stores missing the expected upsert constraint."""
        count = 0
        for row in rows:
            (
                source_text,
                target_text,
                source_norm,
                source_prefix,
                source_len,
                source_locale,
                target_locale,
                origin,
                _tm_name,
                _tm_path,
                file_path,
                key,
                row_status,
                updated_at,
            ) = row
            cur = self._conn.execute(
                """
                UPDATE tm_entries
                SET
                    source_text = ?,
                    target_text = ?,
                    source_norm = ?,
                    source_prefix = ?,
                    source_len = ?,
                    row_status = ?,
                    updated_at = ?
                WHERE origin = ?
                  AND source_locale = ?
                  AND target_locale = ?
                  AND file_path IS ?
                  AND key IS ?
                """,
                (
                    source_text,
                    target_text,
                    source_norm,
                    source_prefix,
                    source_len,
                    row_status,
                    updated_at,
                    origin,
                    source_locale,
                    target_locale,
                    file_path,
                    key,
                ),
            )
            if cur.rowcount > 0:
                count += cur.rowcount
                continue
            self._conn.execute(
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
                    row_status,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                row,
            )
            count += 1
        self._conn.commit()
        self._invalidate_query_cache()
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
        """Insert import pairs."""
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
                row_status,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        count = cur.rowcount if cur.rowcount >= 0 else 0
        self._conn.commit()
        self._invalidate_query_cache()
        return count

    def import_tmx(self, path: Path, *, source_locale: str, target_locale: str) -> int:
        """Execute import tmx."""
        return self.import_tm(
            path,
            source_locale=source_locale,
            target_locale=target_locale,
        )

    def import_tm(self, path: Path, *, source_locale: str, target_locale: str) -> int:
        """Execute import tm."""
        source_locale = _normalize_locale(source_locale)
        target_locale = _normalize_locale(target_locale)
        pairs = iter_tm_pairs(path, source_locale, target_locale)
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
        """Execute replace import tmx."""
        return self.replace_import_tm(
            path,
            source_locale=source_locale,
            target_locale=target_locale,
            source_locale_raw=source_locale_raw,
            target_locale_raw=target_locale_raw,
            tm_name=tm_name,
        )

    def replace_import_tm(
        self,
        path: Path,
        *,
        source_locale: str,
        target_locale: str,
        source_locale_raw: str = "",
        target_locale_raw: str = "",
        tm_name: str | None = None,
    ) -> int:
        """Execute replace import tm."""
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
            iter_tm_pairs(path, source_locale, target_locale),
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
        self._invalidate_query_cache()
        return count

    def list_import_files(self) -> list[TMImportFile]:
        """Execute list import files."""
        rows = self._conn.execute("""
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
            """).fetchall()
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
        """Upsert import file."""
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
        self._invalidate_query_cache()

    def set_import_enabled(self, tm_path: str, enabled: bool) -> None:
        """Set import enabled."""
        self._conn.execute(
            """
            UPDATE tm_import_files
            SET enabled = ?, updated_at = ?
            WHERE tm_path = ?
            """,
            (1 if enabled else 0, int(time.time()), tm_path),
        )
        self._conn.commit()
        self._invalidate_query_cache()

    def delete_import_file(self, tm_path: str) -> None:
        """Delete import file."""
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
        self._invalidate_query_cache()

    def has_import_entries(self, tm_path: str) -> bool:
        """Return whether import entries."""
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
        """Execute export tmx."""
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
        """Execute query."""
        source_locale_norm = _normalize_locale(source_locale)
        target_locale_norm = _normalize_locale(target_locale)
        origin_list = _normalize_origins(origins)
        normalized_source = _normalize(source_text)
        cache_key = (
            self._query_revision,
            normalized_source,
            source_locale_norm,
            target_locale_norm,
            int(limit),
            min_score if min_score is None else int(min_score),
            origin_list,
        )
        cached = self._query_cache_get(cache_key)
        if cached is not None:
            return cached
        matches = self._query_conn(
            self._conn,
            source_text,
            source_locale=source_locale_norm,
            target_locale=target_locale_norm,
            limit=limit,
            min_score=min_score,
            origins=origin_list,
            normalized_source=normalized_source,
        )
        self._query_cache_put(cache_key, matches)
        return matches

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
        """Execute query path."""
        conn = cls._query_conn_for_path(db_path)
        try:
            return cls._query_conn(
                conn,
                source_text,
                source_locale=source_locale,
                target_locale=target_locale,
                limit=limit,
                min_score=min_score,
                origins=origins,
            )
        finally:
            with contextlib.suppress(Exception):
                conn.close()

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
        normalized_source: str | None = None,
    ) -> list[TMMatch]:
        """Execute query conn."""
        return cast(
            list[TMMatch],
            _query_conn_engine(
                conn,
                source_text,
                source_locale=source_locale,
                target_locale=target_locale,
                limit=limit,
                min_score=min_score,
                origins=origins,
                normalized_source=normalized_source,
                runtime=_QUERY_RUNTIME,
                callbacks=TMQueryCallbacks(
                    normalize_locale=_normalize_locale,
                    normalize_origins=_normalize_origins,
                    normalize_text=_normalize,
                ),
                fuzzy_candidates_fn=cls._fuzzy_candidates,
                match_cls=TMMatch,
            ),
        )

    @staticmethod
    def _fuzzy_candidates(
        conn: sqlite3.Connection,
        norm: str,
        source_locale: str,
        target_locale: str,
        origins: Iterable[str],
    ) -> list[tuple[sqlite3.Row, int, int]]:
        """Execute fuzzy candidates."""
        return _fuzzy_candidates_engine(
            conn,
            norm,
            source_locale,
            target_locale,
            origins,
            runtime=_FUZZY_RUNTIME,
            callbacks=TMFuzzyCallbacks(
                normalize_origins=_normalize_origins,
                query_tokens_cached=_query_tokens_cached,
                contains_composed_phrase_cached=_contains_composed_phrase_cached,
                soft_token_overlap=lambda query_tokens, candidate_tokens, use_en: (
                    _soft_token_overlap(
                        query_tokens,
                        candidate_tokens,
                        use_en_stemming=use_en,
                    )
                ),
                exact_token_overlap=_exact_token_overlap,
            ),
        )
