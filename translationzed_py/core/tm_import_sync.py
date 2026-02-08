from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .tm_store import TMImportFile, TMStore
from .tmx_io import detect_tmx_languages

LocaleResolver = Callable[[Path, set[str]], tuple[tuple[str, str] | None, bool]]


@dataclass(frozen=True, slots=True)
class TMImportSyncReport:
    imported_segments: int
    imported_files: tuple[str, ...]
    unresolved_files: tuple[str, ...]
    failures: tuple[str, ...]
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
    files = sorted(path.resolve() for path in tm_dir.glob("*.tmx") if path.is_file())
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
    failures: list[str] = []
    skip_remaining_mappings = False
    for path in files:
        stat = path.stat()
        record = records.get(path)
        if pending_only and (record is None or record.status != "needs_mapping"):
            continue
        if _is_up_to_date_ready(record, stat.st_mtime_ns, stat.st_size, pending_only):
            continue
        try:
            langs = detect_tmx_languages(path)
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
        if record and record.source_locale and record.target_locale:
            pair = (record.source_locale, record.target_locale)
        if pair is None:
            if skip_remaining_mappings:
                pair = None
            else:
                pair, skip_all = resolve_locales(path, langs)
                if skip_all:
                    skip_remaining_mappings = True
        if pair is None:
            unresolved.append(path.name)
            store.upsert_import_file(
                tm_path=str(path),
                tm_name=path.stem,
                mtime_ns=stat.st_mtime_ns,
                file_size=stat.st_size,
                status="needs_mapping",
                note=(
                    "Locale pair is unresolved for this TMX file. "
                    "Use TM menu to resolve."
                ),
            )
            continue
        source_locale, target_locale = pair
        try:
            count = store.replace_import_tmx(
                path,
                source_locale=source_locale,
                target_locale=target_locale,
                tm_name=path.stem,
            )
            imported += count
            imported_files.append(f"{path.name} ({count} segment(s))")
            changed = True
        except Exception as exc:
            failures.append(f"{path.name}: {exc}")
            store.upsert_import_file(
                tm_path=str(path),
                tm_name=path.stem,
                source_locale=source_locale,
                target_locale=target_locale,
                mtime_ns=stat.st_mtime_ns,
                file_size=stat.st_size,
                status="error",
                note=str(exc),
            )

    return TMImportSyncReport(
        imported_segments=imported,
        imported_files=tuple(imported_files),
        unresolved_files=tuple(unresolved),
        failures=tuple(failures),
        changed=changed,
    )


def _is_up_to_date_ready(
    record: TMImportFile | None,
    mtime_ns: int,
    file_size: int,
    pending_only: bool,
) -> bool:
    if pending_only or record is None or record.status != "ready":
        return False
    return record.mtime_ns == mtime_ns and record.file_size == file_size
