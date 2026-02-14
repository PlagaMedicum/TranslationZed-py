from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from translationzed_py.core.parse_utils import _resolve_encoding
from translationzed_py.core.project_scanner import (
    list_translatable_files,
    scan_root_with_errors,
)

_BOM_UTF8 = b"\xef\xbb\xbf"
_BOM_UTF16_LE = b"\xff\xfe"
_BOM_UTF16_BE = b"\xfe\xff"


@dataclass(frozen=True, slots=True)
class EncodingIssue:
    severity: str
    code: str
    path: Path
    locale: str
    declared_charset: str
    detected: str
    detail: str


def _normalize_charset(value: str) -> str:
    return value.strip().lower().replace("_", "-")


def _detect_bom(raw: bytes) -> str:
    if raw.startswith(_BOM_UTF8):
        return "utf-8"
    if raw.startswith(_BOM_UTF16_LE):
        return "utf-16-le"
    if raw.startswith(_BOM_UTF16_BE):
        return "utf-16-be"
    return ""


def _bom_matches_declared(bom_encoding: str, declared: str) -> bool:
    if not bom_encoding:
        return True
    declared_norm = _normalize_charset(declared)
    if bom_encoding == "utf-8":
        return declared_norm in {"utf-8", "utf8"}
    if bom_encoding in {"utf-16-le", "utf-16-be"}:
        return declared_norm in {"utf-16", "utf16", "utf-16-le", "utf-16-be"}
    return True


def scan_encoding_issues(root: Path) -> tuple[list[str], list[EncodingIssue]]:
    locales, language_errors = scan_root_with_errors(root)
    issues: list[EncodingIssue] = []
    for locale, meta in sorted(locales.items()):
        for path in list_translatable_files(meta.path):
            issues.extend(_scan_file(path=path, locale=locale, declared=meta.charset))
    issues.sort(key=lambda item: (item.path.as_posix(), item.code, item.severity))
    return language_errors, issues


def _scan_file(*, path: Path, locale: str, declared: str) -> list[EncodingIssue]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return [
            EncodingIssue(
                severity="error",
                code="read_error",
                path=path,
                locale=locale,
                declared_charset=declared,
                detected="",
                detail=str(exc),
            )
        ]
    issues: list[EncodingIssue] = []
    bom_encoding = _detect_bom(raw)
    if bom_encoding and not _bom_matches_declared(bom_encoding, declared):
        issues.append(
            EncodingIssue(
                severity="warning",
                code="bom_mismatch",
                path=path,
                locale=locale,
                declared_charset=declared,
                detected=bom_encoding,
                detail="BOM encoding differs from locale language.txt charset.",
            )
        )
    declared_norm = _normalize_charset(declared)
    if declared_norm in {"utf-16", "utf16"} and raw and not bom_encoding:
        issues.append(
            EncodingIssue(
                severity="warning",
                code="utf16_bomless_fallback",
                path=path,
                locale=locale,
                declared_charset=declared,
                detected="utf-16 (no BOM)",
                detail="Parser uses BOM-less UTF-16 fallback heuristic for this file.",
            )
        )
    resolved, bom_len = _resolve_encoding(declared, raw)
    payload = raw[bom_len:] if bom_len else raw
    try:
        payload.decode(resolved, errors="strict")
    except UnicodeDecodeError as exc:
        issues.append(
            EncodingIssue(
                severity="error",
                code="decode_error",
                path=path,
                locale=locale,
                declared_charset=declared,
                detected=resolved,
                detail=f"{exc.reason} at byte {exc.start}",
            )
        )
    return issues


def format_encoding_report(
    *,
    root: Path,
    language_errors: list[str],
    issues: list[EncodingIssue],
) -> str:
    lines = [f"Encoding diagnostics: {root.as_posix()}"]
    if language_errors:
        lines.append(f"Language metadata issues: {len(language_errors)}")
        for err in language_errors:
            lines.append(f"- {err}")
    if issues:
        lines.append(f"Encoding issues: {len(issues)}")
        for issue in issues:
            try:
                rel = issue.path.relative_to(root)
                rel_path = rel.as_posix()
            except ValueError:
                rel_path = issue.path.as_posix()
            detected = f" detected={issue.detected}" if issue.detected else ""
            lines.append(
                f"- [{issue.severity}] {issue.code}: {rel_path}"
                f" (locale={issue.locale}, declared={issue.declared_charset};{detected})"
            )
            lines.append(f"  {issue.detail}")
    if not language_errors and not issues:
        lines.append("No encoding conflicts detected.")
    return "\n".join(lines)
