from __future__ import annotations

from pathlib import Path

from translationzed_py.core.encoding_diagnostics import (
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
    root = _init_project(tmp_path)
    be = _init_locale(root, "BE", charset="UTF-8")
    path = be / "ui.txt"
    path.write_bytes('UI_OK = "Привет"\n'.encode("cp1251"))

    language_errors, issues = scan_encoding_issues(root)

    assert language_errors == []
    assert any(issue.code == "decode_error" and issue.path == path for issue in issues)


def test_scan_encoding_issues_reports_utf16_bomless_warning(tmp_path: Path) -> None:
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
    root = _init_project(tmp_path)
    ru = _init_locale(root, "RU", charset="CP1251")
    path = ru / "ui.txt"
    path.write_bytes('UI_OK = "test"\n'.encode("utf-16"))

    language_errors, issues = scan_encoding_issues(root)

    assert language_errors == []
    assert any(issue.code == "bom_mismatch" and issue.path == path for issue in issues)


def test_format_encoding_report_is_copyable_text(tmp_path: Path) -> None:
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
