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


def reset_utf8_fixture() -> None:
    root = Path("tests/fixtures/conflict_manual")
    (root / "EN").mkdir(parents=True, exist_ok=True)
    (root / "BE").mkdir(parents=True, exist_ok=True)
    write_lang(root / "EN" / "language.txt", "English", "UTF-8")
    write_lang(root / "BE" / "language.txt", "Belarusian", "UTF-8")

    (root / "EN" / "ui.txt").write_text(
        'HELLO = "Hello"\nBYE = "Bye"\n', encoding="utf-8"
    )
    (root / "BE" / "ui.txt").write_text(
        'HELLO = "Привет!!"\nBYE = "Пока..."\n', encoding="utf-8"
    )

    pf = parse(root / "BE" / "ui.txt", encoding="utf-8")
    entries: list[Entry] = []
    for e in pf.entries:
        if e.key == "HELLO":
            entries.append(
                Entry(
                    e.key,
                    "Здравствуйте",
                    Status.FOR_REVIEW,
                    e.span,
                    e.segments,
                    e.gaps,
                    e.raw,
                )
            )
        elif e.key == "BYE":
            entries.append(
                Entry(
                    e.key,
                    "До свидания",
                    Status.TRANSLATED,
                    e.span,
                    e.segments,
                    e.gaps,
                    e.raw,
                )
            )
        else:
            entries.append(e)
    write(
        root,
        root / "BE" / "ui.txt",
        entries,
        changed_keys={"HELLO", "BYE"},
        original_values={"HELLO": "Привет", "BYE": "Пока"},
    )


def reset_cp1251_fixture() -> None:
    root = Path("tests/fixtures/conflict_manual_cp1251")
    (root / "EN").mkdir(parents=True, exist_ok=True)
    (root / "RU").mkdir(parents=True, exist_ok=True)
    write_lang(root / "EN" / "language.txt", "English", "UTF-8")
    write_lang(root / "RU" / "language.txt", "Russian", "CP1251")

    (root / "EN" / "ui.txt").write_text(
        'HELLO = "Hello"\nBYE = "Bye"\n', encoding="utf-8"
    )
    (root / "RU" / "ui.txt").write_text(
        'HELLO = "Привет!!"\nBYE = "Пока..."\n', encoding="cp1251"
    )

    pf = parse(root / "RU" / "ui.txt", encoding="cp1251")
    entries: list[Entry] = []
    for e in pf.entries:
        if e.key == "HELLO":
            entries.append(
                Entry(
                    e.key,
                    "Здравствуйте",
                    Status.FOR_REVIEW,
                    e.span,
                    e.segments,
                    e.gaps,
                    e.raw,
                )
            )
        elif e.key == "BYE":
            entries.append(
                Entry(
                    e.key,
                    "До свидания",
                    Status.TRANSLATED,
                    e.span,
                    e.segments,
                    e.gaps,
                    e.raw,
                )
            )
        else:
            entries.append(e)
    write(
        root,
        root / "RU" / "ui.txt",
        entries,
        changed_keys={"HELLO", "BYE"},
        original_values={"HELLO": "Привет", "BYE": "Пока"},
    )


def reset_utf16_fixture() -> None:
    root = Path("tests/fixtures/conflict_manual_utf16")
    (root / "EN").mkdir(parents=True, exist_ok=True)
    (root / "KO").mkdir(parents=True, exist_ok=True)
    write_lang(root / "EN" / "language.txt", "English", "UTF-8")
    write_lang(root / "KO" / "language.txt", "Korean", "UTF-16")

    (root / "EN" / "ui.txt").write_text(
        'HELLO = "Hello"\nBYE = "Bye"\n', encoding="utf-8"
    )
    (root / "KO" / "ui.txt").write_text(
        'HELLO = "안녕!!"\nBYE = "잘가..."\n', encoding="utf-16"
    )

    pf = parse(root / "KO" / "ui.txt", encoding="utf-16")
    entries: list[Entry] = []
    for e in pf.entries:
        if e.key == "HELLO":
            entries.append(
                Entry(
                    e.key,
                    "안녕하세요",
                    Status.FOR_REVIEW,
                    e.span,
                    e.segments,
                    e.gaps,
                    e.raw,
                )
            )
        elif e.key == "BYE":
            entries.append(
                Entry(
                    e.key,
                    "안녕히 가세요",
                    Status.TRANSLATED,
                    e.span,
                    e.segments,
                    e.gaps,
                    e.raw,
                )
            )
        else:
            entries.append(e)
    write(
        root,
        root / "KO" / "ui.txt",
        entries,
        changed_keys={"HELLO", "BYE"},
        original_values={"HELLO": "안녕", "BYE": "잘가"},
    )


reset_utf8_fixture()
reset_cp1251_fixture()
reset_utf16_fixture()
print("Conflict fixtures reset.")
PY
