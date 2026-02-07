from pathlib import Path

from translationzed_py.core.project_scanner import LocaleMeta
from translationzed_py.core.tm_rebuild import (
    TMRebuildLocale,
    TMRebuildResult,
    collect_rebuild_locales,
    format_rebuild_status,
    rebuild_project_tm,
)
from translationzed_py.core.tm_store import TMStore


def test_collect_rebuild_locales_uses_en_encoding_and_skips_missing(
    tmp_path: Path,
) -> None:
    locales = {
        "EN": LocaleMeta("EN", tmp_path / "EN", "English", "utf-16"),
        "BE": LocaleMeta("BE", tmp_path / "BE", "Belarusian", "utf-8"),
    }
    specs, en_encoding = collect_rebuild_locales(locales, ["EN", "BE", "RU"])
    assert en_encoding == "utf-16"
    assert specs == [TMRebuildLocale("BE", tmp_path / "BE", "utf-8")]


def test_rebuild_project_tm_writes_entries_and_counts_skips(tmp_path: Path) -> None:
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
