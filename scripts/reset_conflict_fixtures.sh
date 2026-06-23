#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

python - <<'PY'
from pathlib import Path

from translationzed_py.core.model import Entry, Status
from translationzed_py.core.parser import parse
from translationzed_py.core.status_cache import write


def write_lang(path: Path, text: str, charset: str, encoding: str = "utf-8") -> None:
    path.write_text(f"text = {text},\ncharset = {charset},\n", encoding=encoding)


def write_kv_file(path: Path, rows: list[tuple[str, str]], *, encoding: str) -> None:
    payload = "".join(f'{key} = "{value}"\n' for key, value in rows)
    path.write_text(payload, encoding=encoding)


def seed_conflict_cache(
    *,
    root: Path,
    locale_path: Path,
    encoding: str,
    cache_values: dict[str, str],
    cache_statuses: dict[str, Status],
    original_values: dict[str, str],
) -> None:
    pf = parse(locale_path, encoding=encoding)
    entries: list[Entry] = []
    for row in pf.entries:
        key = row.key
        if key in cache_values:
            entries.append(
                Entry(
                    key,
                    cache_values[key],
                    cache_statuses.get(key, Status.FOR_REVIEW),
                    row.span,
                    row.segments,
                    row.gaps,
                    row.raw,
                )
            )
        else:
            entries.append(row)
    write(
        root,
        locale_path,
        entries,
        changed_keys=set(cache_values),
        original_values=original_values,
    )


def reset_utf8_fixture() -> None:
    root = Path("tests/fixtures/conflict_manual")
    (root / "EN").mkdir(parents=True, exist_ok=True)
    (root / "BE").mkdir(parents=True, exist_ok=True)
    (root / "RU").mkdir(parents=True, exist_ok=True)
    write_lang(root / "EN" / "language.txt", "English", "UTF-8")
    write_lang(root / "BE" / "language.txt", "Belarusian", "UTF-8")
    write_lang(root / "RU" / "language.txt", "Russian", "UTF-8")

    # Shared UI file used by non-conflict manual scenarios.
    write_kv_file(
        root / "EN" / "ui.txt",
        [("HELLO", "Hello"), ("BYE", "Bye")],
        encoding="utf-8",
    )
    write_kv_file(
        root / "BE" / "ui.txt",
        [("HELLO", "Привет!!"), ("BYE", "Пока...")],
        encoding="utf-8",
    )
    write_kv_file(
        root / "RU" / "ui.txt",
        [("HELLO", "Привет!!"), ("BYE", "Пока...")],
        encoding="utf-8",
    )
    # Keep ui.txt as a neutral file-switch target for the manual conflict flow.
    for stale_cache in (
        root / ".tzp" / "cache" / "BE" / "ui.bin",
        root / ".tzp" / "cache" / "RU" / "ui.bin",
    ):
        stale_cache.unlink(missing_ok=True)

    # Dedicated conflict files for path-specific manual scenarios.
    write_kv_file(
        root / "EN" / "conflict_drop_cache.txt",
        [("DC_A", "Drop cache source A"), ("DC_B", "Drop cache source B")],
        encoding="utf-8",
    )
    write_kv_file(
        root / "BE" / "conflict_drop_cache.txt",
        [("DC_A", "Диск вариант A!!"), ("DC_B", "Диск вариант B...")],
        encoding="utf-8",
    )
    write_kv_file(
        root / "RU" / "conflict_drop_cache.txt",
        [("DC_A", "Файл вариант A!!"), ("DC_B", "Файл вариант B...")],
        encoding="utf-8",
    )
    seed_conflict_cache(
        root=root,
        locale_path=root / "BE" / "conflict_drop_cache.txt",
        encoding="utf-8",
        cache_values={"DC_A": "Кэш вариант A", "DC_B": "Кэш вариант B"},
        cache_statuses={"DC_A": Status.FOR_REVIEW, "DC_B": Status.TRANSLATED},
        original_values={"DC_A": "Диск вариант A", "DC_B": "Диск вариант B"},
    )
    seed_conflict_cache(
        root=root,
        locale_path=root / "RU" / "conflict_drop_cache.txt",
        encoding="utf-8",
        cache_values={"DC_A": "Черновик вариант A", "DC_B": "Черновик вариант B"},
        cache_statuses={"DC_A": Status.FOR_REVIEW, "DC_B": Status.TRANSLATED},
        original_values={"DC_A": "Файл вариант A", "DC_B": "Файл вариант B"},
    )

    write_kv_file(
        root / "EN" / "conflict_drop_original.txt",
        [("DO_A", "Drop original source A"), ("DO_B", "Drop original source B")],
        encoding="utf-8",
    )
    write_kv_file(
        root / "BE" / "conflict_drop_original.txt",
        [("DO_A", "Файл вариант A!!"), ("DO_B", "Файл вариант B...")],
        encoding="utf-8",
    )
    write_kv_file(
        root / "RU" / "conflict_drop_original.txt",
        [("DO_A", "Файл вариант A!!"), ("DO_B", "Файл вариант B...")],
        encoding="utf-8",
    )
    seed_conflict_cache(
        root=root,
        locale_path=root / "BE" / "conflict_drop_original.txt",
        encoding="utf-8",
        cache_values={"DO_A": "Черновик вариант A", "DO_B": "Черновик вариант B"},
        cache_statuses={"DO_A": Status.FOR_REVIEW, "DO_B": Status.TRANSLATED},
        original_values={"DO_A": "Файл вариант A", "DO_B": "Файл вариант B"},
    )
    seed_conflict_cache(
        root=root,
        locale_path=root / "RU" / "conflict_drop_original.txt",
        encoding="utf-8",
        cache_values={"DO_A": "Черновик вариант A", "DO_B": "Черновик вариант B"},
        cache_statuses={"DO_A": Status.FOR_REVIEW, "DO_B": Status.TRANSLATED},
        original_values={"DO_A": "Файл вариант A", "DO_B": "Файл вариант B"},
    )

    write_kv_file(
        root / "EN" / "conflict_merge_mixed.txt",
        [("MERGE_A", "Merge source A"), ("MERGE_B", "Merge source B")],
        encoding="utf-8",
    )
    write_kv_file(
        root / "BE" / "conflict_merge_mixed.txt",
        [("MERGE_A", "Файл merge A!!"), ("MERGE_B", "Файл merge B...")],
        encoding="utf-8",
    )
    write_kv_file(
        root / "RU" / "conflict_merge_mixed.txt",
        [("MERGE_A", "Файл merge A!!"), ("MERGE_B", "Файл merge B...")],
        encoding="utf-8",
    )
    seed_conflict_cache(
        root=root,
        locale_path=root / "BE" / "conflict_merge_mixed.txt",
        encoding="utf-8",
        cache_values={"MERGE_A": "Кэш merge A", "MERGE_B": "Кэш merge B"},
        cache_statuses={"MERGE_A": Status.FOR_REVIEW, "MERGE_B": Status.TRANSLATED},
        original_values={"MERGE_A": "Файл merge A", "MERGE_B": "Файл merge B"},
    )
    seed_conflict_cache(
        root=root,
        locale_path=root / "RU" / "conflict_merge_mixed.txt",
        encoding="utf-8",
        cache_values={"MERGE_A": "Кэш merge A", "MERGE_B": "Кэш merge B"},
        cache_statuses={"MERGE_A": Status.FOR_REVIEW, "MERGE_B": Status.TRANSLATED},
        original_values={"MERGE_A": "Файл merge A", "MERGE_B": "Файл merge B"},
    )


def reset_cp1251_fixture() -> None:
    root = Path("tests/fixtures/conflict_manual_cp1251")
    (root / "EN").mkdir(parents=True, exist_ok=True)
    (root / "RU").mkdir(parents=True, exist_ok=True)
    write_lang(root / "EN" / "language.txt", "English", "UTF-8")
    write_lang(root / "RU" / "language.txt", "Russian", "CP1251")

    write_kv_file(
        root / "EN" / "ui.txt",
        [("HELLO", "Hello"), ("BYE", "Bye")],
        encoding="utf-8",
    )
    write_kv_file(
        root / "RU" / "ui.txt",
        [("HELLO", "Привет!!"), ("BYE", "Пока...")],
        encoding="cp1251",
    )
    seed_conflict_cache(
        root=root,
        locale_path=root / "RU" / "ui.txt",
        encoding="cp1251",
        cache_values={"HELLO": "Здравствуйте", "BYE": "До свидания"},
        cache_statuses={"HELLO": Status.FOR_REVIEW, "BYE": Status.TRANSLATED},
        original_values={"HELLO": "Привет", "BYE": "Пока"},
    )


def reset_utf16_fixture() -> None:
    root = Path("tests/fixtures/conflict_manual_utf16")
    (root / "EN").mkdir(parents=True, exist_ok=True)
    (root / "KO").mkdir(parents=True, exist_ok=True)
    write_lang(root / "EN" / "language.txt", "English", "UTF-8")
    write_lang(root / "KO" / "language.txt", "Korean", "UTF-16")

    write_kv_file(
        root / "EN" / "ui.txt",
        [("HELLO", "Hello"), ("BYE", "Bye")],
        encoding="utf-8",
    )
    write_kv_file(
        root / "KO" / "ui.txt",
        [("HELLO", "안녕!!"), ("BYE", "잘가...")],
        encoding="utf-16",
    )
    seed_conflict_cache(
        root=root,
        locale_path=root / "KO" / "ui.txt",
        encoding="utf-16",
        cache_values={"HELLO": "안녕하세요", "BYE": "안녕히 가세요"},
        cache_statuses={"HELLO": Status.FOR_REVIEW, "BYE": Status.TRANSLATED},
        original_values={"HELLO": "안녕", "BYE": "잘가"},
    )


reset_utf8_fixture()
reset_cp1251_fixture()
reset_utf16_fixture()
print("Conflict fixtures reset.")
PY
