"""Support helpers for TMStore normalization and sqlite compatibility checks."""

from __future__ import annotations

import contextlib
import sqlite3
from collections.abc import Iterable

from .model import Status

_PROJECT_ORIGIN = "project"
_IMPORT_ORIGIN = "import"


def normalize_locale(locale: str) -> str:
    """Normalize locale code for TM persistence/query APIs."""
    return locale.strip().upper()


def prefix(text: str, length: int = 8) -> str:
    """Return indexed prefix value used by TM lookup SQL."""
    return text[:length] if text else ""


def normalize_row_status(value: object) -> int | None:
    """Normalize persisted row status value into canonical int enum value."""
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


def normalize_origins(origins: Iterable[str] | None) -> tuple[str, ...]:
    """Normalize origin filter preserving project-first deterministic ordering."""
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


def is_project_upsert_conflict_mismatch(exc: sqlite3.OperationalError) -> bool:
    """Return whether sqlite error indicates missing ON CONFLICT target support."""
    return (
        "ON CONFLICT clause does not match any PRIMARY KEY or UNIQUE constraint"
        in str(exc)
    )
