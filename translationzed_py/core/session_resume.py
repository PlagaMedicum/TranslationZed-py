"""Project-scoped session-resume snapshot contracts."""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from translationzed_py.core.atomic_io import write_text_atomic

SESSION_RESUME_FILENAME = "session.resume.json"
SESSION_RESUME_VERSION = 1
_STARTUP_LEFT_PANEL_INDEX = 0
_VALID_TM_GROUPING_MODES = frozenset({"none", "origin", "score_band"})


@dataclass(frozen=True, slots=True)
class SessionResumeSnapshot:
    """Represent one persisted workspace snapshot for startup resume."""

    version: int
    generated_at_ms: int
    selected_locales: tuple[str, ...]
    active_file_relpath: str | None
    active_row: int | None
    left_panel_index: int
    detail_visible: bool
    search_text: str
    replace_text: str
    search_case_sensitive: bool
    tm_min_score: int
    tm_grouping_mode: str
    tm_origin_project: bool
    tm_origin_import: bool

    def to_payload(self) -> dict[str, object]:
        """Serialize snapshot to deterministic JSON payload."""
        return {
            "version": self.version,
            "generated_at_ms": self.generated_at_ms,
            "selected_locales": list(self.selected_locales),
            "active_file_relpath": self.active_file_relpath,
            "active_row": self.active_row,
            "left_panel_index": self.left_panel_index,
            "detail_visible": self.detail_visible,
            "search_text": self.search_text,
            "replace_text": self.replace_text,
            "search_case_sensitive": self.search_case_sensitive,
            "tm_min_score": self.tm_min_score,
            "tm_grouping_mode": self.tm_grouping_mode,
            "tm_origin_project": self.tm_origin_project,
            "tm_origin_import": self.tm_origin_import,
        }


def session_resume_snapshot_path(*, root: Path, cache_dir: str) -> Path:
    """Return canonical snapshot path under project cache root."""
    return root / cache_dir / SESSION_RESUME_FILENAME


def write_session_resume_snapshot(
    *,
    root: Path,
    cache_dir: str,
    snapshot: SessionResumeSnapshot,
    write_text: Callable[[Path, str], None] | None = None,
) -> Path:
    """Persist one snapshot payload as UTF-8 JSON."""
    path = session_resume_snapshot_path(root=root, cache_dir=cache_dir)
    text = json.dumps(snapshot.to_payload(), ensure_ascii=False, indent=2) + "\n"
    if write_text is None:
        write_text_atomic(path, text, encoding="utf-8")
    else:
        write_text(path, text)
    return path


def read_session_resume_snapshot(
    *,
    root: Path,
    cache_dir: str,
    read_text: Callable[[Path], str] | None = None,
) -> SessionResumeSnapshot | None:
    """Read snapshot payload, returning None for any invalid/unusable state."""
    path = session_resume_snapshot_path(root=root, cache_dir=cache_dir)
    try:
        raw = path.read_text(encoding="utf-8") if read_text is None else read_text(path)
    except OSError:
        return None
    try:
        payload = json.loads(raw)
    except Exception:
        return None
    return parse_session_resume_snapshot(payload)


def delete_session_resume_snapshot(
    *,
    root: Path,
    cache_dir: str,
    unlink_path: Callable[[Path], None] | None = None,
) -> bool:
    """Delete snapshot file when present. Returns False if unlink fails."""
    path = session_resume_snapshot_path(root=root, cache_dir=cache_dir)
    try:
        if unlink_path is None:
            path.unlink(missing_ok=True)
        else:
            unlink_path(path)
    except Exception:
        return False
    return True


def parse_session_resume_snapshot(payload: object) -> SessionResumeSnapshot | None:
    """Validate and parse one snapshot payload object."""
    if not isinstance(payload, dict):
        return None
    version = _as_int(payload.get("version"))
    if version != SESSION_RESUME_VERSION:
        return None
    generated_at_ms = _as_int(payload.get("generated_at_ms"))
    if generated_at_ms is None or generated_at_ms < 0:
        return None
    selected_locales = _as_str_list(payload.get("selected_locales"))
    if selected_locales is None:
        return None
    active_file_relpath = _as_optional_str(payload.get("active_file_relpath"))
    active_row = _as_optional_int(payload.get("active_row"), minimum=0)
    left_panel_index = _as_int(payload.get("left_panel_index"))
    if left_panel_index is None or left_panel_index < 0:
        return None
    detail_visible = _as_bool(payload.get("detail_visible"))
    if detail_visible is None:
        return None
    search_text = _as_str(payload.get("search_text"))
    replace_text = _as_str(payload.get("replace_text"))
    if search_text is None or replace_text is None:
        return None
    search_case_sensitive = _as_bool(payload.get("search_case_sensitive"))
    if search_case_sensitive is None:
        return None
    tm_min_score = _as_int(payload.get("tm_min_score"))
    if tm_min_score is None or tm_min_score < 5 or tm_min_score > 100:
        return None
    tm_grouping_mode = _as_str(payload.get("tm_grouping_mode"))
    if tm_grouping_mode not in _VALID_TM_GROUPING_MODES:
        return None
    tm_origin_project = _as_bool(payload.get("tm_origin_project"))
    tm_origin_import = _as_bool(payload.get("tm_origin_import"))
    if tm_origin_project is None or tm_origin_import is None:
        return None
    return SessionResumeSnapshot(
        version=version,
        generated_at_ms=generated_at_ms,
        selected_locales=tuple(selected_locales),
        active_file_relpath=active_file_relpath,
        active_row=active_row,
        # Startup always returns to Project.  Keep accepting the persisted field so
        # version-1 snapshots written by older builds remain usable without letting
        # a restored heavyweight panel run its activation work during startup.
        left_panel_index=_STARTUP_LEFT_PANEL_INDEX,
        detail_visible=detail_visible,
        search_text=search_text,
        replace_text=replace_text,
        search_case_sensitive=search_case_sensitive,
        tm_min_score=tm_min_score,
        tm_grouping_mode=tm_grouping_mode,
        tm_origin_project=tm_origin_project,
        tm_origin_import=tm_origin_import,
    )


def resolve_session_resume_active_path(
    *,
    root: Path,
    active_file_relpath: str | None,
) -> Path | None:
    """Resolve relative active file path to in-root absolute path."""
    rel = str(active_file_relpath or "").strip()
    if not rel:
        return None
    try:
        path = (root / rel).resolve()
        path.relative_to(root.resolve())
    except Exception:
        return None
    return path


def build_session_resume_snapshot(
    *,
    generated_at_ms: int,
    selected_locales: Sequence[str],
    active_file_relpath: str | None,
    active_row: int | None,
    left_panel_index: int,
    detail_visible: bool,
    search_text: str,
    replace_text: str,
    search_case_sensitive: bool,
    tm_min_score: int,
    tm_grouping_mode: str,
    tm_origin_project: bool,
    tm_origin_import: bool,
) -> SessionResumeSnapshot:
    """Construct normalized snapshot DTO for persistence."""
    locales: list[str] = []
    seen: set[str] = set()
    for value in selected_locales:
        code = str(value or "").strip()
        if not code or code in seen:
            continue
        seen.add(code)
        locales.append(code)
    relpath = str(active_file_relpath or "").strip() or None
    row = None if active_row is None else max(0, int(active_row))
    return SessionResumeSnapshot(
        version=SESSION_RESUME_VERSION,
        generated_at_ms=max(0, int(generated_at_ms)),
        selected_locales=tuple(locales),
        active_file_relpath=relpath,
        active_row=row,
        # Retain the public argument and serialized field for schema compatibility,
        # but sidebar activation is intentionally not part of workspace resume.
        left_panel_index=_STARTUP_LEFT_PANEL_INDEX,
        detail_visible=bool(detail_visible),
        search_text=str(search_text or ""),
        replace_text=str(replace_text or ""),
        search_case_sensitive=bool(search_case_sensitive),
        tm_min_score=max(5, min(100, int(tm_min_score))),
        tm_grouping_mode=(
            str(tm_grouping_mode or "none")
            if str(tm_grouping_mode or "none") in _VALID_TM_GROUPING_MODES
            else "none"
        ),
        tm_origin_project=bool(tm_origin_project),
        tm_origin_import=bool(tm_origin_import),
    )


def _as_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def _as_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return int(value)


def _as_str(value: object) -> str | None:
    if isinstance(value, str):
        return value
    return None


def _as_optional_str(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed or None


def _as_optional_int(value: object, *, minimum: int = 0) -> int | None:
    if value is None:
        return None
    parsed = _as_int(value)
    if parsed is None:
        return None
    if parsed < minimum:
        return None
    return parsed


def _as_str_list(value: object) -> list[str] | None:
    if not isinstance(value, list):
        return None
    out: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            return None
        code = item.strip()
        if not code:
            continue
        if code in seen:
            continue
        seen.add(code)
        out.append(code)
    return out
