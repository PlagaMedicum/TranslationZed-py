from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from translationzed_py.core.app_config import load as _load_app_config

_IGNORE_DIRS = {"_TVRADIO_TRANSLATIONS", ".git", ".vscode"}
_IGNORE_FILES = {"language.txt", "credits.txt"}


class LanguageFileError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class LocaleMeta:
    code: str
    path: Path
    display_name: str
    charset: str


def _top_level_dir(path_value: str) -> str | None:
    normalized = path_value.replace("\\", "/").strip("/")
    if not normalized:
        return None
    head = normalized.split("/", 1)[0].strip()
    return head or None


def _parse_language_file(path: Path) -> tuple[str, str]:
    if not path.exists():
        raise LanguageFileError(f"Missing language.txt: {path}")
    display_name = path.parent.name
    charset: str | None = None
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise LanguageFileError(f"Failed to read language.txt: {path}") from exc

    for line in content.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().lower()
        value = value.strip().rstrip(",")
        value = value.strip('"').strip("'")
        if key == "text":
            display_name = value or display_name
        elif key == "charset" and value:
            charset = value
    if not charset:
        raise LanguageFileError(f"Missing charset in language.txt: {path}")
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
    locales, errors = _scan_root_collect(root)
    if errors:
        detail = "\n".join(errors)
        raise LanguageFileError(f"Invalid language.txt:\n{detail}")
    return locales


def scan_root_with_errors(root: Path) -> tuple[dict[str, LocaleMeta], list[str]]:
    """Return locales plus language.txt errors, skipping invalid locales."""
    return _scan_root_collect(root)


def _scan_root_collect(root: Path) -> tuple[dict[str, LocaleMeta], list[str]]:
    if not root.is_dir():
        raise NotADirectoryError(root)

    cfg = _load_app_config(root)
    runtime_dirs = {
        name
        for name in (_top_level_dir(cfg.cache_dir), _top_level_dir(cfg.config_dir))
        if name
    }
    locales: dict[str, LocaleMeta] = {}
    errors: list[str] = []
    for child in root.iterdir():
        if not child.is_dir():
            continue
        if child.name in _IGNORE_DIRS:
            continue
        if child.name in runtime_dirs:
            continue
        lang_file = child / "language.txt"
        try:
            display_name, charset = _parse_language_file(lang_file)
        except LanguageFileError as exc:
            errors.append(f"{child.name}: {exc}")
            continue
        locales[child.name] = LocaleMeta(
            code=child.name,
            path=child.resolve(),
            display_name=display_name,
            charset=charset,
        )
    return locales, errors
