"""Rollback-safe locale cloning without GUI dependencies."""

from __future__ import annotations

import codecs
import contextlib
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from .project_scanner import LocaleMeta

OFFICIAL_TRANSLATIONS_README_URL = (
    "https://github.com/TheIndieStone/ProjectZomboidTranslations"
)
COMMUNITY_TRANSLATIONS_FORUM_URL = (
    "https://theindiestone.com/forums/index.php?/forum/56-pz-community-translations/"
)

_LOCALE_CODE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,31}$")
_RESERVED_CODES = {".git", ".tzp", ".vscode", "EN", "_TVRADIO_TRANSLATIONS"}


class LocaleCreationError(ValueError):
    """Report an invalid or failed locale creation request."""


@dataclass(frozen=True, slots=True)
class LocaleCreationPlan:
    """Describe one validated locale-clone operation."""

    project_root: Path
    source: LocaleMeta
    code: str
    display_name: str
    charset: str
    destination: Path
    staging: Path


@dataclass(frozen=True, slots=True)
class LocaleCreationResult:
    """Describe a successfully created locale."""

    destination: Path


def _validated_charset(value: str) -> str:
    raw = str(value).strip()
    if not raw:
        raise LocaleCreationError("Charset is required.")
    try:
        return codecs.lookup(raw).name
    except LookupError as exc:
        raise LocaleCreationError(f"Unknown charset: {raw}") from exc


def build_creation_plan(
    *,
    project_root: Path,
    source: LocaleMeta,
    code: str,
    display_name: str,
    charset: str,
) -> LocaleCreationPlan:
    """Validate a locale-clone request without changing the filesystem."""
    root = project_root.resolve()
    normalized_code = str(code).strip()
    if not _LOCALE_CODE_RE.fullmatch(normalized_code):
        raise LocaleCreationError(
            "Locale code must start with a letter and use only letters, numbers, _ or -."
        )
    if normalized_code.casefold() in {item.casefold() for item in _RESERVED_CODES}:
        raise LocaleCreationError(f"Reserved locale code: {normalized_code}")
    name = str(display_name).strip()
    if not name:
        raise LocaleCreationError("Display name is required.")
    if any(char in name for char in '\r\n"'):
        raise LocaleCreationError("Display name cannot contain quotes or line breaks.")
    source_path = source.path.resolve()
    if source_path.parent != root or not source_path.is_dir():
        raise LocaleCreationError(
            "Source locale must be an existing child of the project root."
        )
    target_charset = _validated_charset(charset)
    destination = root / normalized_code
    staging = root / f".tzp-locale-{normalized_code}.tmp"
    collision = next(
        (
            child.name
            for child in root.iterdir()
            if child.name.casefold() == normalized_code.casefold()
        ),
        None,
    )
    if collision is not None:
        raise LocaleCreationError(f"Locale already exists: {collision}")
    if staging.exists():
        raise LocaleCreationError(f"Staging path already exists: {staging.name}")
    return LocaleCreationPlan(
        project_root=root,
        source=source,
        code=normalized_code,
        display_name=name,
        charset=target_charset,
        destination=destination,
        staging=staging,
    )


def _rewrite_language_metadata(text: str, *, display_name: str, charset: str) -> str:
    lines = text.splitlines(keepends=True)
    saw_text = False
    saw_charset = False
    for idx, line in enumerate(lines):
        ending = (
            "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
        )
        body = line[: -len(ending)] if ending else line
        if "=" not in body:
            continue
        key, _value = body.split("=", 1)
        normalized = key.strip().lower()
        if normalized == "text":
            lines[idx] = f'{key}= "{display_name}",{ending}'
            saw_text = True
        elif normalized == "charset":
            lines[idx] = f"{key}= {charset},{ending}"
            saw_charset = True
    newline = "\r\n" if any(line.endswith("\r\n") for line in lines) else "\n"
    if lines and not lines[-1].endswith(("\n", "\r")):
        lines[-1] += newline
    if not saw_text:
        lines.append(f'text = "{display_name}",{newline}')
    if not saw_charset:
        lines.append(f"charset = {charset},{newline}")
    return "".join(lines)


def apply_creation_plan(plan: LocaleCreationPlan) -> LocaleCreationResult:
    """Clone and atomically publish a locale described by *plan*."""
    source_charset = _validated_charset(plan.source.charset)
    if plan.destination.exists():
        raise LocaleCreationError(f"Locale already exists: {plan.code}")
    if plan.staging.exists():
        raise LocaleCreationError(f"Staging path already exists: {plan.staging.name}")
    try:
        shutil.copytree(plan.source.path, plan.staging, copy_function=shutil.copy2)
        for path in sorted(plan.staging.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() != ".txt":
                continue
            raw = path.read_bytes()
            if path.name == "language.txt":
                had_bom = raw.startswith(codecs.BOM_UTF8)
                text = raw.decode("utf-8-sig")
                text = _rewrite_language_metadata(
                    text,
                    display_name=plan.display_name,
                    charset=plan.charset,
                )
                encoded = text.encode("utf-8")
                path.write_bytes(codecs.BOM_UTF8 + encoded if had_bom else encoded)
                continue
            text = raw.decode(source_charset)
            path.write_bytes(text.encode(plan.charset))
        if plan.destination.exists():
            raise LocaleCreationError(f"Locale already exists: {plan.code}")
        plan.staging.rename(plan.destination)
    except Exception as exc:
        with contextlib.suppress(OSError):
            shutil.rmtree(plan.staging)
        if isinstance(exc, LocaleCreationError):
            raise
        raise LocaleCreationError(
            f"Failed to create locale {plan.code}: {exc}"
        ) from exc
    return LocaleCreationResult(destination=plan.destination)


__all__ = [
    "COMMUNITY_TRANSLATIONS_FORUM_URL",
    "OFFICIAL_TRANSLATIONS_README_URL",
    "LocaleCreationError",
    "LocaleCreationPlan",
    "LocaleCreationResult",
    "apply_creation_plan",
    "build_creation_plan",
]
