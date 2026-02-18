"""Test module for encoding diagnostics."""

from __future__ import annotations

from pathlib import Path

from translationzed_py.core.encoding_diagnostics import (
    EncodingIssue,
    _bom_matches_declared,
    _detect_bom,
    _scan_file,
    format_encoding_report,
    scan_encoding_issues,
)


def _init_locale(root: Path, code: str, *, charset: str) -> Path:
    loc = root / code
    loc.mkdir(parents=True, exist_ok=True)
    (loc / "language.txt").write_text(
        f"text = {code},\ncharset = {charset},\n",
        encoding="utf-8",
    )
    return loc


def _init_project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    _init_locale(root, "EN", charset="UTF-8")
    (root / "EN" / "ui.txt").write_text('UI_OK = "OK"\n', encoding="utf-8")
    return root


def test_scan_encoding_issues_reports_decode_error(tmp_path: Path) -> None:
    """Verify scan encoding issues reports decode error."""
    root = _init_project(tmp_path)
    be = _init_locale(root, "BE", charset="UTF-8")
    path = be / "ui.txt"
    path.write_bytes('UI_OK = "Привет"\n'.encode("cp1251"))

    language_errors, issues = scan_encoding_issues(root)

    assert language_errors == []
    assert any(issue.code == "decode_error" and issue.path == path for issue in issues)


def test_scan_encoding_issues_reports_utf16_bomless_warning(tmp_path: Path) -> None:
    """Verify scan encoding issues reports utf16 bomless warning."""
    root = _init_project(tmp_path)
    ko = _init_locale(root, "KO", charset="UTF-16")
    path = ko / "ui.txt"
    path.write_bytes('UI_OK = "테스트"\n'.encode("utf-16-le"))

    language_errors, issues = scan_encoding_issues(root)

    assert language_errors == []
    assert any(
        issue.code == "utf16_bomless_fallback" and issue.path == path
        for issue in issues
    )
    assert not any(
        issue.code == "decode_error" and issue.path == path for issue in issues
    )


def test_scan_encoding_issues_reports_bom_mismatch(tmp_path: Path) -> None:
    """Verify scan encoding issues reports bom mismatch."""
    root = _init_project(tmp_path)
    ru = _init_locale(root, "RU", charset="CP1251")
    path = ru / "ui.txt"
    path.write_bytes('UI_OK = "test"\n'.encode("utf-16"))

    language_errors, issues = scan_encoding_issues(root)

    assert language_errors == []
    assert any(issue.code == "bom_mismatch" and issue.path == path for issue in issues)


def test_format_encoding_report_is_copyable_text(tmp_path: Path) -> None:
    """Verify format encoding report is copyable text."""
    root = _init_project(tmp_path)
    be = _init_locale(root, "BE", charset="UTF-8")
    path = be / "ui.txt"
    path.write_bytes('UI_OK = "Привет"\n'.encode("cp1251"))
    language_errors, issues = scan_encoding_issues(root)

    report = format_encoding_report(
        root=root,
        language_errors=language_errors,
        issues=issues,
    )

    assert "Encoding diagnostics" in report
    assert "decode_error" in report
    assert "BE/ui.txt" in report


def test_encoding_helpers_detect_bom_and_match_declared_charset() -> None:
    """Verify BOM helper logic covers UTF-8 and UTF-16 compatibility rules."""
    assert _detect_bom(b"\xef\xbb\xbfabc") == "utf-8"
    assert _detect_bom(b"\xff\xfeA\x00") == "utf-16-le"
    assert _detect_bom(b"\xfe\xff\x00A") == "utf-16-be"
    assert _detect_bom(b"plain") == ""

    assert _bom_matches_declared("", "anything")
    assert _bom_matches_declared("utf-8", "UTF-8")
    assert _bom_matches_declared("utf-8", "CP1251") is False
    assert _bom_matches_declared("utf-16-le", "UTF-16")
    assert _bom_matches_declared("utf-16-be", "UTF-16-BE")
    assert _bom_matches_declared("utf-16-be", "UTF-8") is False
    assert _bom_matches_declared("other", "UTF-8")


def test_scan_file_reports_read_error_when_file_cannot_be_opened(tmp_path: Path) -> None:
    """Verify scan file returns read_error issues for missing files."""
    missing = tmp_path / "missing.txt"
    issues = _scan_file(path=missing, locale="EN", declared="UTF-8")
    assert len(issues) == 1
    assert issues[0].code == "read_error"


def test_format_encoding_report_includes_language_errors_and_empty_state() -> None:
    """Verify formatting covers metadata-error and no-conflict report modes."""
    root = Path("/tmp/project-root")

    report_with_language_errors = format_encoding_report(
        root=root,
        language_errors=["missing charset in EN/language.txt"],
        issues=[],
    )
    assert "Language metadata issues: 1" in report_with_language_errors
    assert "missing charset in EN/language.txt" in report_with_language_errors

    report_clean = format_encoding_report(root=root, language_errors=[], issues=[])
    assert "No encoding conflicts detected." in report_clean


def test_format_encoding_report_uses_absolute_path_for_external_issue() -> None:
    """Verify report falls back to absolute paths outside the project root."""
    root = Path("/tmp/project-root")
    external = Path("/var/tmp/outside.txt")
    issues = [
        EncodingIssue(
            severity="warning",
            code="bom_mismatch",
            path=external,
            locale="EN",
            declared_charset="UTF-8",
            detected="utf-16-le",
            detail="outside root path",
        )
    ]
    report = format_encoding_report(root=root, language_errors=[], issues=issues)
    assert external.as_posix() in report
