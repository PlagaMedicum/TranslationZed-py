from __future__ import annotations

import re
from pathlib import Path

_LOCALE_RE = re.compile(r"^[A-Z]{2}$")  # folders like EN, BE, RU …


def scan_root(root: Path) -> dict[str, Path]:
    """Return {'EN': Path('…/EN'), …} for every two-letter locale dir in *root*."""
    if not root.is_dir():
        raise NotADirectoryError(root)

    locales: dict[str, Path] = {}
    for child in root.iterdir():
        if child.is_dir() and _LOCALE_RE.fullmatch(child.name):
            locales[child.name] = child.resolve()
    return locales
