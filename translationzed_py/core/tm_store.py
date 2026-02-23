"""Tm store module."""

from __future__ import annotations

import contextlib
import re
import sqlite3
import time
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from .app_config import LEGACY_CONFIG_DIR
from .app_config import load as _load_app_config
from .model import Status
from .tmx_io import iter_tm_pairs, write_tmx

_PROJECT_ORIGIN = "project"
_IMPORT_ORIGIN = "import"
# Store query accepts 5..100 when explicitly requested; GUI default is 50.
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


def _normalize(text: str) -> str:
    """Execute normalize."""
    return " ".join(text.lower().split())


def _prefix(text: str, length: int = 8) -> str:
    """Execute prefix."""
    return text[:length] if text else ""


def _query_tokens(text: str) -> tuple[str, ...]:
    """Execute query tokens."""
    tokens: list[str] = []
    for token in re.findall(r"\w+", text, flags=re.UNICODE):
        if len(token) < 2:
            continue
        tokens.append(token)
    return tuple(dict.fromkeys(tokens))


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


def _token_matches(
    query_token: str,
    candidate_token: str,
    *,
    use_en_stemming: bool,
) -> bool:
    """Execute token matches."""
    if query_token == candidate_token:
        return True
    if use_en_stemming:
        query_stem = _stem_token(query_token)
        candidate_stem = _stem_token(candidate_token)
        if len(query_stem) >= 3 and query_stem == candidate_stem:
            return True
    if len(query_token) == len(candidate_token) and len(query_token) >= 4:
        if query_token[:2] != candidate_token[:2]:
            return False
        if query_token[-1] != candidate_token[-1]:
            return False
        mismatches = 0
        for q_char, c_char in zip(query_token, candidate_token, strict=False):
            if q_char != c_char:
                mismatches += 1
                if mismatches > 1:
                    break
        if mismatches == 1:
            return True
    shorter, longer = (
        (query_token, candidate_token)
        if len(query_token) <= len(candidate_token)
        else (candidate_token, query_token)
    )
    if len(shorter) < 4:
        return False
    ratio = len(shorter) / len(longer)
    if (longer.startswith(shorter) or longer.endswith(shorter)) and ratio >= 0.50:
        return True
    if shorter in longer:
        return ratio >= 0.67
    return False


def _contains_composed_phrase(
    text: str,
    query: str,
    *,
    use_en_stemming: bool,
) -> bool:
    """Execute contains composed phrase."""
    parts = _query_tokens(query)
    if not parts:
        return False
    text_tokens = _query_tokens(text)
    if not text_tokens:
        return False
    if len(parts) == 1:
        token = parts[0]
        return any(
            _token_matches(token, cand, use_en_stemming=use_en_stemming)
            for cand in text_tokens
        )
    pos = 0
    for part in parts:
        found = False
        while pos < len(text_tokens):
            if _token_matches(
                part,
                text_tokens[pos],
                use_en_stemming=use_en_stemming,
            ):
                found = True
                pos += 1
                break
            pos += 1
        if not found:
            return False
    return True


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


def _normalize_locale(locale: str) -> str:
    """Normalize locale."""
    return locale.strip().upper()


def _normalize_row_status(value: object) -> int | None:
    """Normalize row status."""
    if value is None:
        return None
    if isinstance(value, Status):
        return int(value)
    if isinstance(value, int):
        raw = value
    elif isinstance(value, str):
        with contextlib.suppress(ValueError):
            raw = int(value.strip())
            with contextlib.suppress(ValueError):
                return int(Status(raw))
        return None
    else:
        return None
    with contextlib.suppress(ValueError):
        return int(Status(raw))
    return None


def _normalize_origins(origins: Iterable[str] | None) -> tuple[str, ...]:
    """Normalize origins."""
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


def _is_project_upsert_conflict_mismatch(exc: sqlite3.OperationalError) -> bool:
    """Return whether sqlite error indicates missing ON CONFLICT target support."""
    return "ON CONFLICT clause does not match any PRIMARY KEY or UNIQUE constraint" in str(
        exc
    )


class TMStore:
    """Represent TMStore."""

    def __init__(self, root: Path) -> None:
        """Initialize the instance."""
        cfg = _load_app_config(root)
        self._path = self._resolve_db_path(root, cfg.config_dir)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._path)
        self._closed = False
        self._conn.row_factory = sqlite3.Row
        self._configure()
        self._ensure_schema()

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
        rows = []
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
            return count
        except sqlite3.OperationalError as exc:
            if not _is_project_upsert_conflict_mismatch(exc):
                raise
            return self._upsert_project_entries_fallback(rows)

    def _upsert_project_entries_fallback(
        self, rows: list[tuple[object, ...]]
    ) -> int:
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
    ) -> list[TMMatch]:
        """Execute query conn."""
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
                row_status,
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
        fuzzy_reserved = (
            _SHORT_QUERY_RESERVED_SLOTS
            if len(norm) <= _SHORT_QUERY_LEN
            else _FUZZY_RESERVED_SLOTS
        )
        max_exact = max(1, limit - fuzzy_reserved)
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
                    raw_score=100,
                    row_status=row["row_status"],
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
        for cand, score, raw_score in candidates:
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
                    raw_score=raw_score,
                    row_status=cand["row_status"],
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
    ) -> list[tuple[sqlite3.Row, int, int]]:
        """Execute fuzzy candidates."""
        from difflib import SequenceMatcher

        query_tokens = set(_query_tokens(norm))
        use_en_stemming = source_locale == "EN"
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
        if len(query_tokens) > 1:
            # Allow phrase-expansion neighbors (e.g. "make item" -> "make new item").
            max_len = max(
                max_len,
                length + max(_MULTI_TOKEN_LEN_PADDING, len(query_tokens) * 2),
            )
        max_candidates = _MAX_FUZZY_CANDIDATES
        bucket_candidates = _FUZZY_BUCKET_CANDIDATES
        if length <= _SHORT_QUERY_LEN:
            min_len = 1
            max_len = max(max_len, 40)
            max_candidates = _SHORT_QUERY_MAX_CANDIDATES
            bucket_candidates = _SHORT_QUERY_BUCKET_CANDIDATES
        rows: list[sqlite3.Row] = []
        seen_rows: set[tuple[object, ...]] = set()

        def _select_rows(
            where_sql: str,
            order_sql: str,
            where_params: tuple[object, ...],
            *,
            order_params: tuple[object, ...] = (),
            limit: int,
        ) -> list[sqlite3.Row]:
            """Execute select rows."""
            return conn.execute(
                f"""
                SELECT
                    source_text, source_norm, target_text, origin, file_path, key
                    , row_status, updated_at, tm_name, tm_path
                FROM tm_entries
                WHERE source_locale = ? AND target_locale = ?
                  AND {where_sql}
                  AND ({_IMPORT_VISIBLE_SQL})
                  AND {origin_clause}
                ORDER BY {order_sql}
                LIMIT ?
                """,
                (
                    source_locale,
                    target_locale,
                    *where_params,
                    *origin_params,
                    *order_params,
                    limit,
                ),
            ).fetchall()

        def _append_unique(candidates: list[sqlite3.Row]) -> None:
            """Execute append unique."""
            for row in candidates:
                row_key = (
                    row["source_text"],
                    row["target_text"],
                    row["origin"],
                    row["tm_name"],
                    row["tm_path"],
                    row["file_path"],
                    row["key"],
                )
                if row_key in seen_rows:
                    continue
                seen_rows.add(row_key)
                rows.append(row)
                if len(rows) >= max_candidates:
                    return

        prefix_rows = _select_rows(
            "source_prefix = ? AND source_len BETWEEN ? AND ?",
            "ABS(source_len - ?) ASC, updated_at DESC",
            (prefix, min_len, max_len),
            order_params=(length,),
            limit=bucket_candidates,
        )
        fallback_rows = _select_rows(
            "source_len BETWEEN ? AND ?",
            "ABS(source_len - ?) ASC, updated_at DESC",
            (min_len, max_len),
            order_params=(length,),
            limit=bucket_candidates,
        )
        token_rows: list[sqlite3.Row] = []
        if query_tokens:
            # Query by longest token first to keep phrase neighbors visible even
            # when source_prefix diverges ("drop one" -> "drop-all").
            token = max(query_tokens, key=len)
            if len(token) >= 3:
                token_rows = _select_rows(
                    "instr(source_norm, ?) > 0 AND source_len BETWEEN ? AND ?",
                    (
                        "CASE WHEN source_norm = ? THEN 0 "
                        "WHEN source_norm LIKE ? THEN 1 "
                        "WHEN source_norm LIKE ? THEN 2 "
                        "WHEN source_norm LIKE ? THEN 3 "
                        "ELSE 4 END, ABS(source_len - ?) ASC, updated_at DESC"
                    ),
                    (
                        token,
                        min_len,
                        max_len,
                    ),
                    order_params=(
                        token,
                        f"{token} %",
                        f"% {token} %",
                        f"% {token}",
                        length,
                    ),
                    limit=bucket_candidates,
                )
        if length <= _SHORT_QUERY_LEN:
            # For tiny queries, prefix-only retrieval is too strict
            # (e.g. "all" vs "apply all").
            # Seed token-containing rows first to keep close phrase neighbors visible.
            if token_rows:
                _append_unique(token_rows)
            if len(rows) < max_candidates:
                _append_unique(prefix_rows)
            if len(rows) < max_candidates:
                _append_unique(fallback_rows)
        else:
            _append_unique(prefix_rows)
            if len(rows) < max_candidates and token_rows:
                _append_unique(token_rows)
            if len(rows) < max_candidates:
                _append_unique(fallback_rows)
        scored: list[tuple[sqlite3.Row, int, int, int]] = []
        for row in rows:
            cand_norm = row["source_norm"]
            ratio = SequenceMatcher(None, norm, cand_norm, autojunk=False).ratio()
            composed = _contains_composed_phrase(
                cand_norm,
                norm,
                use_en_stemming=use_en_stemming,
            )
            overlap = 0.0
            exact_overlap = 0.0
            token_count_delta = 999
            if query_tokens:
                cand_tokens = set(_query_tokens(cand_norm))
                token_count_delta = abs(len(cand_tokens) - len(query_tokens))
                if cand_tokens:
                    overlap = _soft_token_overlap(
                        query_tokens,
                        cand_tokens,
                        use_en_stemming=use_en_stemming,
                    )
                    exact_overlap = _exact_token_overlap(query_tokens, cand_tokens)
                    if len(query_tokens) == 1:
                        if overlap < 0.5 and not composed:
                            continue
                    elif overlap < 0.34 and ratio < 0.75 and not composed:
                        continue
                elif not composed:
                    continue
            raw_score = int(round(ratio * 100))
            score = raw_score
            token_bonus = int(round((overlap * 6.0) + (exact_overlap * 4.0)))
            score = min(100, score + token_bonus)
            if composed:
                score = max(score, 90 if len(query_tokens) > 1 else 85)
            if score >= 100 and cand_norm != norm:
                score = 99
            scored.append((row, score, raw_score, token_count_delta))
        if len(query_tokens) > 1:
            scored.sort(
                key=lambda item: (
                    item[3],
                    -item[1],
                    abs(len(item[0]["source_norm"]) - length),
                    0 if item[0]["origin"] == _PROJECT_ORIGIN else 1,
                    -item[0]["updated_at"],
                )
            )
        else:
            scored.sort(
                key=lambda item: (
                    -item[1],
                    abs(len(item[0]["source_norm"]) - length),
                    0 if item[0]["origin"] == _PROJECT_ORIGIN else 1,
                    -item[0]["updated_at"],
                )
            )
        return [(row, score, raw_score) for row, score, raw_score, _delta in scored]
