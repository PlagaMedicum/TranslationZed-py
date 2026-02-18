"""Test module for source reference service."""

from __future__ import annotations

from pathlib import Path

from translationzed_py.core.lazy_entries import EntryMeta, LazyEntries
from translationzed_py.core.model import Entry, ParsedFile, Status
from translationzed_py.core.source_reference_service import (
    build_source_lookup_materialized,
    dump_source_reference_file_overrides,
    load_reference_lookup,
    load_source_reference_file_overrides,
    normalize_source_reference_mode,
    reference_path_for,
    resolve_source_reference_locale,
    resolve_source_reference_mode_for_path,
    source_reference_path_key,
)


def test_normalize_source_reference_mode() -> None:
    """Verify normalize source reference mode."""
    assert normalize_source_reference_mode(" en ") == "EN"
    assert normalize_source_reference_mode("be") == "BE"
    assert normalize_source_reference_mode("", default="EN") == "EN"


def test_resolve_source_reference_locale_prefers_requested_available() -> None:
    """Verify resolve source reference locale prefers requested available."""
    resolution = resolve_source_reference_locale(
        "BE",
        available_locales=("EN", "BE", "RU"),
    )
    assert resolution.requested_mode == "BE"
    assert resolution.resolved_locale == "BE"
    assert resolution.fallback_used is False


def test_resolve_source_reference_locale_falls_back_to_default_then_locale() -> None:
    """Verify expected behavior."""
    resolution = resolve_source_reference_locale(
        "KO",
        available_locales=("BE", "RU"),
        fallback_locale="RU",
    )
    assert resolution.requested_mode == "KO"
    assert resolution.resolved_locale == "RU"
    assert resolution.fallback_used is True


def test_reference_path_for_mirror_layout(tmp_path: Path) -> None:
    """Verify reference path for mirror layout."""
    root = tmp_path / "proj"
    be = root / "BE"
    en = root / "EN"
    be.mkdir(parents=True)
    en.mkdir(parents=True)
    target = be / "ui.txt"
    source = en / "ui.txt"
    target.write_text('UI = "B"\n', encoding="utf-8")
    source.write_text('UI = "E"\n', encoding="utf-8")

    assert (
        reference_path_for(
            root,
            target,
            target_locale="BE",
            reference_locale="EN",
        )
        == source
    )


def test_reference_path_for_suffix_rewrite(tmp_path: Path) -> None:
    """Verify reference path for suffix rewrite."""
    root = tmp_path / "proj"
    be = root / "BE"
    en = root / "EN"
    be.mkdir(parents=True)
    en.mkdir(parents=True)
    target = be / "IG_UI_BE.txt"
    source = en / "IG_UI_EN.txt"
    target.write_text('UI = "B"\n', encoding="utf-8")
    source.write_text('UI = "E"\n', encoding="utf-8")

    assert (
        reference_path_for(
            root,
            target,
            target_locale="BE",
            reference_locale="EN",
        )
        == source
    )


def test_reference_path_for_returns_none_when_outside_root(tmp_path: Path) -> None:
    """Verify reference path for returns none when outside root."""
    root = tmp_path / "proj"
    root.mkdir()
    outside = tmp_path.parent / "outside.txt"
    assert (
        reference_path_for(
            root,
            outside,
            target_locale="BE",
            reference_locale="EN",
        )
        is None
    )


def test_build_source_lookup_materialized_by_row_when_keys_match() -> None:
    """Verify build source lookup materialized by row when keys match."""
    entries = [
        Entry("K1", "One", Status.UNTOUCHED, (0, 0), (), ()),
        Entry("K2", "Two", Status.UNTOUCHED, (0, 0), (), ()),
    ]
    target = [
        Entry("K1", "A", Status.UNTOUCHED, (0, 0), (), ()),
        Entry("K2", "B", Status.UNTOUCHED, (0, 0), (), ()),
    ]
    result = build_source_lookup_materialized(
        entries,
        target_entries=target,
        path_name="ui.txt",
    )
    assert result.by_row_values == ["One", "Two"]
    assert result.keys == ["K1", "K2"]
    assert result.by_key is None


def test_build_source_lookup_materialized_raw_single_entry() -> None:
    """Verify build source lookup materialized raw single entry."""
    reference = [
        Entry("News_BE.txt", "RAW", Status.UNTOUCHED, (0, 0), (), (), raw=True),
    ]
    target = [
        Entry("News_BE.txt", "X", Status.UNTOUCHED, (0, 0), (), (), raw=True),
    ]
    result = build_source_lookup_materialized(
        reference,
        target_entries=target,
        path_name="News_BE.txt",
    )
    assert result.by_row_values == ["RAW"]
    assert result.keys == ["News_BE.txt"]


def test_load_reference_lookup_uses_cache_and_returns_materialized(
    tmp_path: Path,
) -> None:
    """Verify load reference lookup uses cache and returns materialized."""
    root = tmp_path / "proj"
    for loc in ("EN", "BE"):
        (root / loc).mkdir(parents=True, exist_ok=True)
    target_path = root / "BE" / "ui.txt"
    source_path = root / "EN" / "ui.txt"
    target_path.write_text('K = "B"\n', encoding="utf-8")
    source_path.write_text('K = "E"\n', encoding="utf-8")

    target_entries = [Entry("K", "B", Status.UNTOUCHED, (0, 0), (), ())]
    cached_pf = ParsedFile(
        source_path,
        [Entry("K", "E", Status.UNTOUCHED, (0, 0), (), ())],
        b"",
    )
    cache = {source_path: cached_pf}

    result = load_reference_lookup(
        root=root,
        path=target_path,
        target_locale="BE",
        reference_locale="EN",
        locale_encodings={"EN": "utf-8", "BE": "utf-8"},
        target_entries=target_entries,
        parsed_cache=cache,
        should_parse_lazy=lambda _p: False,
        parse_eager=lambda _p, _enc: (_ for _ in ()).throw(RuntimeError("no parse")),
        parse_lazy=lambda _p, _enc: (_ for _ in ()).throw(RuntimeError("no parse")),
    )
    assert result is not None
    assert result.by_row_values == ["E"]
    assert result.keys == ["K"]


def test_source_reference_path_key_is_posix_relative(tmp_path: Path) -> None:
    """Verify source reference path key is posix relative."""
    root = tmp_path / "proj"
    path = root / "BE" / "ui.txt"
    assert source_reference_path_key(root, path) == "BE/ui.txt"


def test_source_reference_file_overrides_round_trip() -> None:
    """Verify source reference file overrides round trip."""
    encoded = dump_source_reference_file_overrides(
        {"BE\\ui.txt": "ru", "BE/menu.txt": "EN", "": "RU"}
    )
    loaded = load_source_reference_file_overrides(encoded)
    assert loaded == {"BE/ui.txt": "RU", "BE/menu.txt": "EN"}


def test_resolve_source_reference_mode_for_path_uses_override(tmp_path: Path) -> None:
    """Verify resolve source reference mode for path uses override."""
    root = tmp_path / "proj"
    path = root / "BE" / "ui.txt"
    mode = resolve_source_reference_mode_for_path(
        root=root,
        path=path,
        default_mode="EN",
        overrides={"BE/ui.txt": "RU"},
    )
    assert mode == "RU"


def test_source_reference_path_key_falls_back_for_external_paths() -> None:
    """Verify source reference path keys use absolute posix outside root."""
    root = Path("/tmp/project-root")
    path = Path("/var/tmp/external.txt")
    assert source_reference_path_key(root, path) == path.as_posix()


def test_load_source_reference_file_overrides_rejects_invalid_payloads() -> None:
    """Verify source reference overrides loader ignores invalid raw payloads."""
    assert load_source_reference_file_overrides("") == {}
    assert load_source_reference_file_overrides("not-json") == {}
    assert load_source_reference_file_overrides('["EN"]') == {}


def test_reference_path_for_handles_same_locale_and_invalid_modes(
    tmp_path: Path,
) -> None:
    """Verify reference path lookup handles same-locale and invalid mode cases."""
    root = tmp_path / "proj"
    en = root / "EN"
    en.mkdir(parents=True)
    same_path = en / "ui.txt"
    same_path.write_text('UI = "E"\n', encoding="utf-8")

    assert (
        reference_path_for(
            root,
            same_path,
            target_locale="EN",
            reference_locale="EN",
        )
        == same_path
    )
    assert (
        reference_path_for(
            root,
            same_path.with_name("missing.txt"),
            target_locale="EN",
            reference_locale="EN",
        )
        is None
    )
    assert (
        reference_path_for(
            root,
            same_path,
            target_locale="",
            reference_locale="EN",
        )
        is None
    )


def test_build_source_lookup_materialized_uses_lazy_row_entries_when_available() -> (
    None
):
    """Verify source lookup returns lazy row entries when keys align."""
    raw = b'"One"|"Two"'
    metas = [
        EntryMeta("K1", Status.UNTOUCHED, (0, 5), (3,), (), False, ((0, 5),), 1),
        EntryMeta("K2", Status.UNTOUCHED, (6, 11), (3,), (), False, ((6, 11),), 2),
    ]
    reference_lazy = LazyEntries(raw=raw, encoding="utf-8", metas=metas)
    target_entries = [
        Entry("K1", "A", Status.UNTOUCHED, (0, 0), (), ()),
        Entry("K2", "B", Status.UNTOUCHED, (0, 0), (), ()),
    ]

    result = build_source_lookup_materialized(
        reference_lazy,
        target_entries=target_entries,
        path_name="ui.txt",
    )

    assert result.by_row_entries is reference_lazy
    assert result.by_row_values is None
    assert result.keys == ["K1", "K2"]


def test_load_reference_lookup_short_circuits_missing_context(tmp_path: Path) -> None:
    """Verify load reference lookup returns none for missing required context."""
    root = tmp_path / "proj"
    root.mkdir()
    path = root / "BE" / "ui.txt"

    common_kwargs = {
        "root": root,
        "path": path,
        "parsed_cache": {},
        "should_parse_lazy": lambda _p: False,
        "parse_eager": lambda _p, _enc: (_ for _ in ()).throw(
            RuntimeError("unexpected")
        ),
        "parse_lazy": lambda _p, _enc: (_ for _ in ()).throw(
            RuntimeError("unexpected")
        ),
    }

    assert (
        load_reference_lookup(
            **common_kwargs,
            target_locale=None,
            reference_locale="EN",
            locale_encodings={"EN": "utf-8"},
            target_entries=None,
        )
        is None
    )
    assert (
        load_reference_lookup(
            **common_kwargs,
            target_locale="BE",
            reference_locale="EN",
            locale_encodings={"BE": "utf-8"},
            target_entries=None,
        )
        is None
    )
