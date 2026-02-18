"""Test module for tm rebuild."""

from pathlib import Path
from types import SimpleNamespace
from typing import cast

from translationzed_py.core.model import Entry, Status
from translationzed_py.core.project_scanner import LocaleMeta
from translationzed_py.core.tm_rebuild import (
    TMRebuildLocale,
    TMRebuildResult,
    _source_target_for_entry,
    collect_rebuild_locales,
    format_rebuild_status,
    rebuild_project_tm,
)
from translationzed_py.core.tm_store import TMStore


def test_collect_rebuild_locales_uses_en_encoding_and_skips_missing(
    tmp_path: Path,
) -> None:
    """Verify collect rebuild locales uses en encoding and skips missing."""
    locales = {
        "EN": LocaleMeta("EN", tmp_path / "EN", "English", "utf-16"),
        "BE": LocaleMeta("BE", tmp_path / "BE", "Belarusian", "utf-8"),
    }
    specs, en_encoding = collect_rebuild_locales(locales, ["EN", "BE", "RU"])
    assert en_encoding == "utf-16"
    assert specs == [TMRebuildLocale("BE", tmp_path / "BE", "utf-8")]


def test_rebuild_project_tm_writes_entries_and_counts_skips(tmp_path: Path) -> None:
    """Verify rebuild project tm writes entries and counts skips."""
    root = tmp_path / "root"
    (root / "EN").mkdir(parents=True)
    (root / "BE").mkdir(parents=True)
    (root / "EN" / "ui.txt").write_text(
        'HELLO = "Hello"\nBYE = "Bye"\n',
        encoding="utf-8",
    )
    (root / "BE" / "ui.txt").write_text(
        'HELLO = "Прывітанне"\nBYE = ""\n',
        encoding="utf-8",
    )
    (root / "BE" / "only_be.txt").write_text(
        'ONLY = "Толькі"\n',
        encoding="utf-8",
    )

    result = rebuild_project_tm(
        root,
        [TMRebuildLocale("BE", root / "BE", "utf-8")],
        source_locale="EN",
        en_encoding="utf-8",
        batch_size=1,
    )

    assert result.files == 1
    assert result.entries == 1
    assert result.skipped_empty == 1
    assert result.skipped_missing_source >= 1

    store = TMStore(root)
    matches = store.query(
        "Hello",
        source_locale="EN",
        target_locale="BE",
        origins=["project"],
    )
    assert matches
    assert matches[0].target_text == "Прывітанне"
    store.close()


def test_format_rebuild_status_includes_skip_summary() -> None:
    """Verify format rebuild status includes skip summary."""
    text = format_rebuild_status(
        TMRebuildResult(
            entries=10,
            files=2,
            skipped_missing_source=3,
            skipped_parse=1,
            skipped_empty=4,
        )
    )
    assert "10 entries" in text
    assert "2 files" in text
    assert "missing source 3" in text
    assert "parse errors 1" in text
    assert "empty values 4" in text


def test_collect_rebuild_locales_defaults_to_utf8_without_en(tmp_path: Path) -> None:
    """Verify locale collection defaults EN encoding when EN metadata is missing."""
    locales = {
        "BE": LocaleMeta("BE", tmp_path / "BE", "Belarusian", "cp1251"),
    }

    specs, en_encoding = collect_rebuild_locales(locales, ["BE"])

    assert specs == [TMRebuildLocale("BE", tmp_path / "BE", "cp1251")]
    assert en_encoding == "utf-8"


def test_rebuild_project_tm_counts_parse_errors_and_flushes_tail_batch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Verify rebuild increments parse skips and flushes non-full batches."""
    root = tmp_path / "root"
    (root / "EN").mkdir(parents=True)
    (root / "BE").mkdir(parents=True)
    (root / "EN" / "ok.txt").write_text('HELLO = "Hello"\n', encoding="utf-8")
    (root / "EN" / "broken.txt").write_text('BROKEN = "Broken"\n', encoding="utf-8")
    (root / "BE" / "ok.txt").write_text(
        'HELLO = "Прывітанне"\nONLY_BE = "Толькі"\n',
        encoding="utf-8",
    )
    (root / "BE" / "broken.txt").write_text(
        "# parse error source\n" "NO_EQUALS_HERE\n",
        encoding="utf-8",
    )

    def _parse_with_error(path: Path, *, encoding: str):  # type: ignore[no-untyped-def]
        if path.name == "broken.txt":
            raise ValueError("forced parse error")
        from translationzed_py.core.parser import parse as real_parse

        return real_parse(path, encoding=encoding)

    monkeypatch.setattr("translationzed_py.core.tm_rebuild.parse", _parse_with_error)

    result = rebuild_project_tm(
        root,
        [TMRebuildLocale("BE", root / "BE", "utf-8")],
        source_locale="EN",
        en_encoding="utf-8",
        batch_size=50,
    )

    assert result.files == 1
    assert result.entries == 1
    assert result.skipped_parse == 1
    assert result.skipped_missing_source >= 1


def test_format_rebuild_status_without_skips_omits_skip_clause() -> None:
    """Verify summary does not include skip text when all skip counters are zero."""
    text = format_rebuild_status(TMRebuildResult(entries=3, files=1))
    assert "3 entries" in text
    assert "1 files" in text
    assert "skipped" not in text


def test_source_target_for_entry_handles_missing_none_and_empty_values() -> None:
    """Verify source/target extraction handles defensive fallback cases."""
    source_by_key = {"HELLO": "Hello"}

    missing = _source_target_for_entry(
        Entry(
            key="MISSING",
            value="Target",
            status=Status.UNTOUCHED,
            span=(0, 0),
            segments=(),
            gaps=(),
        ),
        source_by_key,
    )
    assert missing == (None, None)

    none_value_entry = cast(Entry, SimpleNamespace(key="HELLO", value=None))
    empty_value_entry = cast(Entry, SimpleNamespace(key="HELLO", value=""))
    normal_entry = cast(Entry, SimpleNamespace(key="HELLO", value="Прывітанне"))

    assert _source_target_for_entry(none_value_entry, source_by_key) == ("Hello", None)
    assert _source_target_for_entry(empty_value_entry, source_by_key) == ("Hello", None)
    assert _source_target_for_entry(normal_entry, source_by_key) == (
        "Hello",
        "Прывітанне",
    )
