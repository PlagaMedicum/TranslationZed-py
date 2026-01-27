from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_IGNORE_DIRS = {"_TVRADIO_TRANSLATIONS", ".tzp-cache"}
_IGNORE_FILES = {"language.txt", "credits.txt"}


@dataclass(frozen=True, slots=True)
class LocaleMeta:
    code: str
    path: Path
    display_name: str
    charset: str


def _parse_language_file(path: Path) -> tuple[str, str]:
    display_name = path.parent.name
    charset = "utf-8"
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return display_name, charset

    for line in content.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().lower()
        value = value.strip().rstrip(",")
        value = value.strip('"').strip("'")
        if key == "text":
            display_name = value or display_name
        elif key == "charset":
            charset = value or charset
    return display_name, charset


def list_translatable_files(locale_path: Path) -> list[Path]:
    """Return .txt files under *locale_path*, excluding non-translatables."""
    files = []
    for path in locale_path.rglob("*.txt"):
        if path.name in _IGNORE_FILES:
            continue
        files.append(path)
    return sorted(files)


def scan_root(root: Path) -> dict[str, LocaleMeta]:
    """Return mapping {locale_code: LocaleMeta} for locale dirs in *root*."""
    if not root.is_dir():
        raise NotADirectoryError(root)

    locales: dict[str, LocaleMeta] = {}
    for child in root.iterdir():
        if not child.is_dir():
            continue
        if child.name in _IGNORE_DIRS:
            continue
        lang_file = child / "language.txt"
        display_name, charset = _parse_language_file(lang_file)
        locales[child.name] = LocaleMeta(
            code=child.name,
            path=child.resolve(),
            display_name=display_name,
            charset=charset,
        )
    return locales
