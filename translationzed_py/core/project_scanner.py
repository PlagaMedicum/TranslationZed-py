from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from translationzed_py.core.app_config import load as _load_app_config

_IGNORE_DIRS = {"_TVRADIO_TRANSLATIONS"}
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
    """Return translatable files under *locale_path*, excluding non-translatables."""
    cfg = _load_app_config(locale_path.parent)
    files = []
    pattern = f"*{cfg.translation_ext}"
    for path in locale_path.rglob(pattern):
        if path.name in _IGNORE_FILES:
            continue
        files.append(path)
    return sorted(files)


def scan_root(root: Path) -> dict[str, LocaleMeta]:
    """Return mapping {locale_code: LocaleMeta} for locale dirs in *root*."""
    if not root.is_dir():
        raise NotADirectoryError(root)

    cfg = _load_app_config(root)
    locales: dict[str, LocaleMeta] = {}
    for child in root.iterdir():
        if not child.is_dir():
            continue
        if child.name in _IGNORE_DIRS:
            continue
        if child.name in {cfg.cache_dir, cfg.config_dir}:
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
