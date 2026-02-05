from __future__ import annotations

import sqlite3
import time
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from .app_config import load as _load_app_config
from .tmx_io import iter_tmx_pairs, write_tmx

_PROJECT_ORIGIN = "project"
_IMPORT_ORIGIN = "import"
_MIN_FUZZY_SCORE = 30
_MAX_FUZZY_CANDIDATES = 200
_MAX_FUZZY_SOURCE_LEN = 5000


@dataclass(frozen=True, slots=True)
class TMMatch:
    source_text: str
    target_text: str
    score: int
    origin: str
    file_path: str | None
    key: str | None
    updated_at: int


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _prefix(text: str, length: int = 8) -> str:
    return text[:length] if text else ""


def _normalize_locale(locale: str) -> str:
    return locale.strip().upper()


class TMStore:
    def __init__(self, root: Path) -> None:
        cfg = _load_app_config(root)
        self._path = root / cfg.config_dir / "tm.sqlite"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._path)
        self._conn.row_factory = sqlite3.Row
        self._configure()
        self._ensure_schema()

    def close(self) -> None:
        self._conn.close()

    def _configure(self) -> None:
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA temp_store=MEMORY")

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
                file_path TEXT,
                key TEXT,
                updated_at INTEGER NOT NULL
            )
            """
        )
        self._conn.execute("DROP INDEX IF EXISTS tm_project_key")
        self._conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS tm_project_key
            ON tm_entries(origin, source_locale, target_locale, file_path, key)
            """
        )
        self._conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS tm_import_unique
            ON tm_entries(origin, source_locale, target_locale, source_norm, target_text)
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
        self._conn.commit()

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
                file_path,
                key,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        updated_at: int | None = None,
    ) -> int:
        source_locale = _normalize_locale(source_locale)
        target_locale = _normalize_locale(target_locale)
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
                file_path,
                key,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            pairs, source_locale=source_locale, target_locale=target_locale
        )

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
    ) -> list[TMMatch]:
        source_locale = _normalize_locale(source_locale)
        target_locale = _normalize_locale(target_locale)
        norm = _normalize(source_text)
        if not norm:
            return []
        exact_rows = self._conn.execute(
            """
            SELECT source_text, target_text, origin, file_path, key, updated_at
            FROM tm_entries
            WHERE source_locale = ? AND target_locale = ? AND source_norm = ?
            ORDER BY CASE origin WHEN 'project' THEN 0 ELSE 1 END, updated_at DESC
            """,
            (source_locale, target_locale, norm),
        ).fetchall()
        matches: list[TMMatch] = []
        seen: set[tuple[str, str, str]] = set()
        for row in exact_rows:
            key = (row["source_text"], row["target_text"], row["origin"])
            if key in seen:
                continue
            seen.add(key)
            matches.append(
                TMMatch(
                    source_text=row["source_text"],
                    target_text=row["target_text"],
                    score=100,
                    origin=row["origin"],
                    file_path=row["file_path"],
                    key=row["key"],
                    updated_at=row["updated_at"],
                )
            )
            if len(matches) >= limit:
                return matches
        if len(norm) > _MAX_FUZZY_SOURCE_LEN:
            return matches
        candidates = self._fuzzy_candidates(norm, source_locale, target_locale)
        for cand, score in candidates:
            key = (cand["source_text"], cand["target_text"], cand["origin"])
            if key in seen:
                continue
            if score < _MIN_FUZZY_SCORE:
                continue
            seen.add(key)
            matches.append(
                TMMatch(
                    source_text=cand["source_text"],
                    target_text=cand["target_text"],
                    score=score,
                    origin=cand["origin"],
                    file_path=cand["file_path"],
                    key=cand["key"],
                    updated_at=cand["updated_at"],
                )
            )
            if len(matches) >= limit:
                break
        return matches

    def _fuzzy_candidates(
        self, norm: str, source_locale: str, target_locale: str
    ) -> list[tuple[sqlite3.Row, int]]:
        from difflib import SequenceMatcher

        prefix = _prefix(norm, 6)
        length = len(norm)
        min_len = max(1, int(length * 0.6))
        max_len = int(length * 1.4) if length > 5 else length + 10
        rows = self._conn.execute(
            """
            SELECT source_text, source_norm, target_text, origin, file_path, key, updated_at
            FROM tm_entries
            WHERE source_locale = ? AND target_locale = ? AND source_prefix = ?
              AND source_len BETWEEN ? AND ?
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (
                source_locale,
                target_locale,
                prefix,
                min_len,
                max_len,
                _MAX_FUZZY_CANDIDATES,
            ),
        ).fetchall()
        if not rows:
            rows = self._conn.execute(
                """
                SELECT source_text, source_norm, target_text, origin, file_path, key, updated_at
                FROM tm_entries
                WHERE source_locale = ? AND target_locale = ?
                  AND source_len BETWEEN ? AND ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (source_locale, target_locale, min_len, max_len, _MAX_FUZZY_CANDIDATES),
            ).fetchall()
        scored: list[tuple[sqlite3.Row, int]] = []
        for row in rows:
            cand_norm = row["source_norm"]
            ratio = SequenceMatcher(None, norm, cand_norm, autojunk=False).ratio()
            score = int(round(ratio * 100))
            scored.append((row, score))
        scored.sort(
            key=lambda item: (
                -item[1],
                0 if item[0]["origin"] == _PROJECT_ORIGIN else 1,
                -item[0]["updated_at"],
            )
        )
        return scored
