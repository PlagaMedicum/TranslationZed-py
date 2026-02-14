from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .tm_store import TMImportFile, TMStore
from .tmx_io import detect_tm_languages, supported_tm_import_suffixes

LocaleResolver = Callable[[Path, set[str]], tuple[tuple[str, str] | None, bool]]
_SUPPORTED_TM_IMPORT_SUFFIXES = frozenset(supported_tm_import_suffixes())


@dataclass(frozen=True, slots=True)
class TMImportSyncReport:
    imported_segments: int
    imported_files: tuple[str, ...]
    unresolved_files: tuple[str, ...]
    zero_segment_files: tuple[str, ...]
    failures: tuple[str, ...]
    checked_files: tuple[str, ...]
    changed: bool


def sync_import_folder(
    store: TMStore,
    tm_dir: Path,
    *,
    resolve_locales: LocaleResolver,
    only_paths: set[Path] | None = None,
    pending_only: bool = False,
) -> TMImportSyncReport:
    target_paths = {
        path.resolve()
        for path in only_paths or set()
        if path.exists() and path.is_file()
    }
    files = sorted(
        path.resolve()
        for path in tm_dir.iterdir()
        if path.is_file() and path.suffix.lower() in _SUPPORTED_TM_IMPORT_SUFFIXES
    )
    if target_paths:
        files = [path for path in files if path in target_paths]
    records = {
        Path(rec.tm_path).resolve(): rec
        for rec in store.list_import_files()
        if rec.tm_path
    }
    changed = False
    if not target_paths:
        existing_files = set(files)
        for rec_path in list(records):
            if rec_path not in existing_files:
                store.delete_import_file(str(rec_path))
                records.pop(rec_path, None)
                changed = True

    imported = 0
    imported_files: list[str] = []
    unresolved: list[str] = []
    zero_segment_files: list[str] = []
    failures: list[str] = []
    checked_files: list[str] = []
    skip_remaining_mappings = False
    for path in files:
        checked_files.append(path.name)
        stat = path.stat()
        record = records.get(path)
        if pending_only and (record is None or record.status != "needs_mapping"):
            continue
        has_entries = bool(record) and store.has_import_entries(str(path))
        if _is_up_to_date_ready(
            record,
            stat.st_mtime_ns,
            stat.st_size,
            pending_only,
            has_entries=has_entries,
        ):
            continue
        try:
            langs = detect_tm_languages(path)
        except Exception as exc:
            failures.append(f"{path.name}: {exc}")
            store.upsert_import_file(
                tm_path=str(path),
                tm_name=path.stem,
                mtime_ns=stat.st_mtime_ns,
                file_size=stat.st_size,
                status="error",
                note=str(exc),
            )
            continue
        pair: tuple[str, str] | None = None
        source_locale_raw = ""
        target_locale_raw = ""
        if record and record.source_locale and record.target_locale:
            pair = (record.source_locale, record.target_locale)
            source_locale_raw = record.source_locale_raw or record.source_locale
            target_locale_raw = record.target_locale_raw or record.target_locale
        if pair is None:
            if skip_remaining_mappings:
                pair = None
            else:
                pair, skip_all = resolve_locales(path, langs)
                if skip_all:
                    skip_remaining_mappings = True
            if pair is not None:
                source_locale_raw, target_locale_raw = _pick_raw_pair(
                    pair[0], pair[1], langs
                )
        if pair is None:
            unresolved.append(path.name)
            store.upsert_import_file(
                tm_path=str(path),
                tm_name=path.stem,
                mtime_ns=stat.st_mtime_ns,
                file_size=stat.st_size,
                status="needs_mapping",
                note=(
                    "Locale pair is unresolved for this TM file. "
                    "Use TM menu to resolve."
                ),
            )
            continue
        source_locale, target_locale = pair
        try:
            count = store.replace_import_tm(
                path,
                source_locale=source_locale,
                target_locale=target_locale,
                source_locale_raw=source_locale_raw,
                target_locale_raw=target_locale_raw,
                tm_name=path.stem,
            )
            imported += count
            imported_files.append(f"{path.name} ({count} segment(s))")
            if count == 0:
                zero_segment_files.append(path.name)
            changed = True
        except Exception as exc:
            failures.append(f"{path.name}: {exc}")
            store.upsert_import_file(
                tm_path=str(path),
                tm_name=path.stem,
                source_locale=source_locale,
                target_locale=target_locale,
                source_locale_raw=source_locale_raw,
                target_locale_raw=target_locale_raw,
                mtime_ns=stat.st_mtime_ns,
                file_size=stat.st_size,
                status="error",
                note=str(exc),
            )

    return TMImportSyncReport(
        imported_segments=imported,
        imported_files=tuple(imported_files),
        unresolved_files=tuple(unresolved),
        zero_segment_files=tuple(zero_segment_files),
        failures=tuple(failures),
        checked_files=tuple(checked_files),
        changed=changed,
    )


def _normalize_locale_tag(value: str) -> str:
    raw = value.strip().upper().replace("_", "-")
    if not raw:
        return ""
    return raw.split("-", 1)[0]


def _pick_raw_pair(
    source_locale: str,
    target_locale: str,
    langs: set[str],
) -> tuple[str, str]:
    source_norm = _normalize_locale_tag(source_locale)
    target_norm = _normalize_locale_tag(target_locale)
    raw_langs = [raw.strip() for raw in sorted(langs) if raw.strip()]

    def _best_raw(norm_locale: str, preferred: str) -> str:
        exact = ""
        fallback = ""
        preferred_norm = preferred.strip().upper().replace("_", "-")
        for raw in raw_langs:
            normalized = _normalize_locale_tag(raw)
            if normalized != norm_locale:
                continue
            raw_norm = raw.upper().replace("_", "-")
            if raw_norm == preferred_norm:
                exact = raw
                break
            if not fallback:
                fallback = raw
        return exact or fallback

    source_raw = _best_raw(source_norm, source_locale)
    target_raw = _best_raw(target_norm, target_locale)
    if not source_raw and raw_langs:
        source_raw = raw_langs[0]
    if not target_raw and raw_langs:
        for raw in raw_langs:
            if raw != source_raw:
                target_raw = raw
                break
        if not target_raw:
            target_raw = raw_langs[0]
    if not source_raw:
        source_raw = source_locale
    if not target_raw:
        target_raw = target_locale
    return source_raw, target_raw


def _is_up_to_date_ready(
    record: TMImportFile | None,
    mtime_ns: int,
    file_size: int,
    pending_only: bool,
    *,
    has_entries: bool,
) -> bool:
    if pending_only or record is None or record.status != "ready":
        return False
    if not has_entries:
        return False
    return record.mtime_ns == mtime_ns and record.file_size == file_size
