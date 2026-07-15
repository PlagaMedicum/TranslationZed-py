"""Tests for rollback-safe locale creation."""

from __future__ import annotations

import codecs
from pathlib import Path

import pytest

from translationzed_py.core.locale_creation import (
    LocaleCreationError,
    apply_creation_plan,
    build_creation_plan,
)
from translationzed_py.core.project_scanner import LocaleMeta, scan_root


def _source(root: Path, *, charset: str = "cp1251") -> LocaleMeta:
    path = root / "RU"
    path.mkdir(parents=True)
    (path / "language.txt").write_bytes(
        'VERSION = 1,\ntext = "Russian",\ncharset = CP1251,\n'.encode(charset)
    )
    (path / "ui.txt").write_bytes('A = "Текст"\n'.encode(charset))
    (path / "asset.bin").write_bytes(b"\x00\xff")
    return LocaleMeta("RU", path, "Russian", charset)


def test_clone_locale_transcodes_text_and_rewrites_metadata(tmp_path: Path) -> None:
    """Clone text and binary files while rewriting locale metadata safely."""
    source = _source(tmp_path)
    plan = build_creation_plan(
        project_root=tmp_path,
        source=source,
        code="UA",
        display_name="Ukrainian",
        charset="utf-8",
    )

    result = apply_creation_plan(plan)

    assert result.destination == tmp_path / "UA"
    assert 'A = "Текст"' in (result.destination / "ui.txt").read_text(encoding="utf-8")
    language = (result.destination / "language.txt").read_text(encoding="utf-8")
    assert 'text = "Ukrainian",' in language
    assert "charset = utf-8," in language
    assert (result.destination / "asset.bin").read_bytes() == b"\x00\xff"
    assert scan_root(tmp_path)["UA"].display_name == "Ukrainian"


def test_language_metadata_stays_utf8_for_non_utf8_locale(tmp_path: Path) -> None:
    """Keep scanner metadata UTF-8 while locale content uses its declared charset."""
    source = _source(tmp_path)
    plan = build_creation_plan(
        project_root=tmp_path,
        source=source,
        code="UA",
        display_name="Українська",
        charset="cp1251",
    )

    result = apply_creation_plan(plan)

    language = (result.destination / "language.txt").read_text(encoding="utf-8")
    assert 'text = "Українська",' in language
    assert scan_root(tmp_path)["UA"].display_name == "Українська"


def test_creation_adds_missing_metadata_and_preserves_utf8_bom(tmp_path: Path) -> None:
    """Append required metadata safely when a BOM-prefixed file omits it."""
    source = _source(tmp_path)
    (source.path / "language.txt").write_bytes(
        codecs.BOM_UTF8 + b"-- header\nVERSION = 1,"
    )
    plan = build_creation_plan(
        project_root=tmp_path,
        source=source,
        code="UA",
        display_name="Ukrainian",
        charset="utf-8",
    )

    result = apply_creation_plan(plan)

    raw = (result.destination / "language.txt").read_bytes()
    assert raw.startswith(codecs.BOM_UTF8)
    assert 'text = "Ukrainian",' in raw.decode("utf-8-sig")
    assert "charset = utf-8," in raw.decode("utf-8-sig")


@pytest.mark.parametrize(
    ("display_name", "charset"),
    [("", "utf-8"), ('Bad " name', "utf-8"), ("Name", ""), ("Name", "not-a-codec")],
)
def test_creation_rejects_invalid_metadata(
    tmp_path: Path, display_name: str, charset: str
) -> None:
    """Reject metadata that cannot be serialized or encoded safely."""
    source = _source(tmp_path)

    with pytest.raises(LocaleCreationError):
        build_creation_plan(
            project_root=tmp_path,
            source=source,
            code="UA",
            display_name=display_name,
            charset=charset,
        )


@pytest.mark.parametrize(
    "code", ["../UA", ".tzp", "_TVRADIO_TRANSLATIONS", "EN", "en", "BAD CODE", "9BAD"]
)
def test_creation_rejects_unsafe_or_reserved_codes(tmp_path: Path, code: str) -> None:
    """Reject unsafe, hidden, runtime, and malformed locale codes."""
    source = _source(tmp_path)

    with pytest.raises(LocaleCreationError):
        build_creation_plan(
            project_root=tmp_path,
            source=source,
            code=code,
            display_name="Name",
            charset="utf-8",
        )


def test_creation_never_overwrites_existing_destination(tmp_path: Path) -> None:
    """Never replace an existing locale directory."""
    source = _source(tmp_path)
    (tmp_path / "UA").mkdir()

    with pytest.raises(LocaleCreationError, match="already exists"):
        build_creation_plan(
            project_root=tmp_path,
            source=source,
            code="UA",
            display_name="Ukrainian",
            charset="utf-8",
        )


def test_creation_rejects_case_insensitive_collision(tmp_path: Path) -> None:
    """Reject a destination that differs only by filesystem case."""
    source = _source(tmp_path)
    (tmp_path / "ua").mkdir()

    with pytest.raises(LocaleCreationError, match="already exists: ua"):
        build_creation_plan(
            project_root=tmp_path,
            source=source,
            code="UA",
            display_name="Ukrainian",
            charset="utf-8",
        )


def test_creation_rechecks_destination_before_writing(tmp_path: Path) -> None:
    """Preserve a destination created after planning and leave no staging tree."""
    source = _source(tmp_path)
    plan = build_creation_plan(
        project_root=tmp_path,
        source=source,
        code="UA",
        display_name="Ukrainian",
        charset="utf-8",
    )
    plan.destination.mkdir()
    marker = plan.destination / "keep.txt"
    marker.write_text("keep", encoding="utf-8")

    with pytest.raises(LocaleCreationError, match="already exists"):
        apply_creation_plan(plan)

    assert marker.read_text(encoding="utf-8") == "keep"
    assert not plan.staging.exists()


def test_creation_rejects_invalid_source_and_staging_collision(tmp_path: Path) -> None:
    """Require an in-project source and never reuse a staging directory."""
    outside = tmp_path.parent / "outside"
    outside.mkdir()
    source = LocaleMeta("RU", outside, "Russian", "utf-8")
    with pytest.raises(LocaleCreationError, match="Source locale"):
        build_creation_plan(
            project_root=tmp_path,
            source=source,
            code="UA",
            display_name="Ukrainian",
            charset="utf-8",
        )

    source = _source(tmp_path)
    staging = tmp_path / ".tzp-locale-UA.tmp"
    staging.mkdir()
    with pytest.raises(LocaleCreationError, match="Staging path"):
        build_creation_plan(
            project_root=tmp_path,
            source=source,
            code="UA",
            display_name="Ukrainian",
            charset="utf-8",
        )


def test_creation_rolls_back_decode_failure(tmp_path: Path) -> None:
    """Remove only staging when source text cannot be decoded."""
    source = _source(tmp_path, charset="utf-8")
    (source.path / "ui.txt").write_bytes(b"\xff")
    plan = build_creation_plan(
        project_root=tmp_path,
        source=source,
        code="UA",
        display_name="Ukrainian",
        charset="utf-8",
    )

    with pytest.raises(LocaleCreationError, match="Failed to create"):
        apply_creation_plan(plan)

    assert not plan.staging.exists()
    assert not plan.destination.exists()
