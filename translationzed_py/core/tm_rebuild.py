from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from .model import Entry
from .parser import parse
from .project_scanner import LocaleMeta, list_translatable_files
from .tm_store import TMStore


@dataclass(frozen=True, slots=True)
class TMRebuildLocale:
    locale: str
    locale_path: Path
    target_encoding: str


@dataclass(frozen=True, slots=True)
class TMRebuildResult:
    files: int = 0
    entries: int = 0
    skipped_missing_source: int = 0
    skipped_parse: int = 0
    skipped_empty: int = 0


def collect_rebuild_locales(
    locale_map: Mapping[str, LocaleMeta],
    selected_locales: list[str] | tuple[str, ...] | set[str],
) -> tuple[list[TMRebuildLocale], str]:
    en_meta = locale_map.get("EN")
    en_encoding = en_meta.charset if en_meta else "utf-8"
    specs: list[TMRebuildLocale] = []
    for locale in selected_locales:
        if locale == "EN":
            continue
        meta = locale_map.get(locale)
        if not meta:
            continue
        specs.append(
            TMRebuildLocale(
                locale=locale,
                locale_path=meta.path,
                target_encoding=meta.charset,
            )
        )
    return specs, en_encoding


def rebuild_project_tm(
    root: Path,
    locales: list[TMRebuildLocale],
    *,
    source_locale: str,
    en_encoding: str,
    batch_size: int = 1000,
) -> TMRebuildResult:
    store = TMStore(root)
    files = 0
    entries = 0
    skipped_missing_source = 0
    skipped_parse = 0
    skipped_empty = 0
    try:
        for spec in locales:
            for target_path in list_translatable_files(spec.locale_path):
                en_path = _tm_en_path_for(root, spec.locale, target_path)
                if en_path is None:
                    skipped_missing_source += 1
                    continue
                try:
                    target_pf = parse(target_path, encoding=spec.target_encoding)
                    en_pf = parse(en_path, encoding=en_encoding)
                except Exception:
                    skipped_parse += 1
                    continue
                source_by_key = {entry.key: entry.value for entry in en_pf.entries}
                batch: list[tuple[str, str, str, int]] = []
                for entry in target_pf.entries:
                    source_text, target_text = _source_target_for_entry(
                        entry, source_by_key
                    )
                    if source_text is None:
                        skipped_missing_source += 1
                        continue
                    if target_text is None:
                        skipped_empty += 1
                        continue
                    batch.append(
                        (entry.key, source_text, target_text, int(entry.status))
                    )
                    if len(batch) >= batch_size:
                        entries += store.upsert_project_entries(
                            batch,
                            source_locale=source_locale,
                            target_locale=spec.locale,
                            file_path=str(target_path),
                        )
                        batch.clear()
                if batch:
                    entries += store.upsert_project_entries(
                        batch,
                        source_locale=source_locale,
                        target_locale=spec.locale,
                        file_path=str(target_path),
                    )
                files += 1
    finally:
        store.close()
    return TMRebuildResult(
        files=files,
        entries=entries,
        skipped_missing_source=skipped_missing_source,
        skipped_parse=skipped_parse,
        skipped_empty=skipped_empty,
    )


def format_rebuild_status(result: TMRebuildResult) -> str:
    parts = [
        f"TM rebuild complete: {result.entries} entries",
        f"{result.files} files",
    ]
    skipped = []
    if result.skipped_missing_source:
        skipped.append(f"missing source {result.skipped_missing_source}")
    if result.skipped_parse:
        skipped.append(f"parse errors {result.skipped_parse}")
    if result.skipped_empty:
        skipped.append(f"empty values {result.skipped_empty}")
    if skipped:
        parts.append(f"skipped {', '.join(skipped)}")
    return " · ".join(parts)


def _source_target_for_entry(
    entry: Entry, source_by_key: dict[str, str]
) -> tuple[str | None, str | None]:
    source_text = source_by_key.get(entry.key)
    if not source_text:
        return None, None
    value = entry.value
    if value is None:
        return source_text, None
    value_text = str(value)
    if not value_text:
        return source_text, None
    return str(source_text), value_text


def _tm_en_path_for(root: Path, locale: str, path: Path) -> Path | None:
    locale_root = root / locale
    try:
        rel = path.relative_to(locale_root)
    except ValueError:
        try:
            rel_full = path.relative_to(root)
            if rel_full.parts and rel_full.parts[0] == locale:
                rel = Path(*rel_full.parts[1:])
            else:
                return None
        except ValueError:
            return None
    candidate = root / "EN" / rel
    if candidate.exists():
        return candidate
    stem = rel.stem
    for token in (locale, locale.replace(" ", "_")):
        suffix = f"_{token}"
        if stem.endswith(suffix):
            new_stem = stem[: -len(suffix)] + "_EN"
            alt = rel.with_name(new_stem + rel.suffix)
            alt_path = root / "EN" / alt
            if alt_path.exists():
                return alt_path
    return None
