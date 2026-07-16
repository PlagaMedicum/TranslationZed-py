"""B42 flat JSON parsing, lossless saving, and format-identity contracts."""

from __future__ import annotations

from pathlib import Path

import pytest

from translationzed_py.core import list_translatable_files, parse, parse_lazy, scan_root
from translationzed_py.core.model import Status
from translationzed_py.core.saver import save
from translationzed_py.core.status_cache import cache_path, write
from translationzed_py.core.translation_format import (
    supported_extensions,
    translation_relative_path,
)
from translationzed_py.core.translation_json import (
    TranslationJSONError,
    build_insert_plan,
    insert_missing,
)


def _fixture_root() -> Path:
    return Path(__file__).parent / "fixtures" / "b42_json"


def test_b42_fixture_scans_without_legacy_charset() -> None:
    """JSON-only B42 fixtures should scan with their implicit UTF-8 encoding."""
    locales = scan_root(_fixture_root())

    assert set(locales) == {"BE", "EN"}
    assert locales["BE"].charset == "utf-8"
    assert locales["EN"].charset == "utf-8"
    assert [path.name for path in list_translatable_files(locales["BE"].path)] == [
        "UI.json"
    ]


def test_b42_json_eager_and_lazy_parsers_preserve_order_and_values() -> None:
    """Eager and lazy JSON parsing should expose identical ordered values."""
    path = _fixture_root() / "BE" / "UI.json"
    before = path.read_bytes()

    eager = parse(path, encoding="cp1251")
    lazy = parse_lazy(path, encoding="cp1251")

    expected_keys = [
        "UI_fixture_greeting",
        "UI_fixture_escaped",
        "UI_fixture_unicode",
    ]
    assert [entry.key for entry in eager.entries] == expected_keys
    assert [entry.key for entry in lazy.entries] == expected_keys
    assert eager.entries[1].value == 'Першы радок\n"цытата" і \\ шлях'
    assert lazy.entries[1].value == eager.entries[1].value
    assert lazy.entries.preview_at(1, 12) == eager.entries[1].value[:12]
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (b"[]", "top-level object"),
        (b'{"A": 1}', "values must be JSON strings"),
        (b'{"A": {"nested": "no"}}', "values must be JSON strings"),
        (b'{"A": "one", "A": "two"}', "Duplicate translation key"),
        (b'{1: "one"}', "keys must be JSON strings"),
        (b'{"A" "one"}', "Expected ':'"),
        (b'{"A": "one"', "Unterminated top-level"),
        (b'{"A": "one" "B": "two"}', "Expected ',' or '}'"),
        (b'{"A": "\\q"}', "Invalid JSON string literal"),
        (b'{"A": "\\ud800"}', "unpaired surrogates"),
        (b'{"A": "unterminated}', "Unterminated JSON string"),
        (b'{"A": "one",}', "Trailing commas"),
        (b'{"A": "one"} trailing', "Unexpected content"),
    ],
)
def test_b42_json_rejects_unsupported_or_malformed_shapes(
    tmp_path: Path, payload: bytes, message: str
) -> None:
    """Unsupported JSON shapes should fail before a document can be edited."""
    path = tmp_path / "UI.json"
    path.write_bytes(payload)

    with pytest.raises(TranslationJSONError, match=message):
        parse(path)


def test_b42_json_accepts_empty_eager_and_lazy_objects(tmp_path: Path) -> None:
    """An empty string map should remain a safe, ordered zero-row document."""
    path = tmp_path / "UI.json"
    path.write_bytes(b"{}\n")

    assert list(parse(path).entries) == []
    assert list(parse_lazy(path).entries) == []


def test_b42_json_rejects_bom_invalid_utf8_and_oversize(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Encoding and size violations should produce bounded parse failures."""
    path = tmp_path / "UI.json"
    path.write_bytes(b'\xef\xbb\xbf{"A": "one"}')
    with pytest.raises(TranslationJSONError, match="BOM"):
        parse(path)

    path.write_bytes(b'{"A": "\xff"}')
    with pytest.raises(TranslationJSONError, match="valid UTF-8"):
        parse(path)

    path.write_bytes(b'{"A": "one"}')
    monkeypatch.setattr(
        "translationzed_py.core.translation_json.MAX_JSON_FILE_BYTES", 4
    )
    with pytest.raises(TranslationJSONError, match="safety limit"):
        parse(path)


def test_b42_json_save_changes_only_value_literals_and_refreshes_spans(
    tmp_path: Path,
) -> None:
    """JSON Save should preserve untouched literals and support repeated edits."""
    path = tmp_path / "UI.json"
    original = b'{\n  "A" : "one",\n  "B": "\\u0411\\nline"\n}'
    path.write_bytes(original)
    parsed = parse_lazy(path)

    save(
        parsed,
        {"A": 'two "quoted"\npath', "B": "Б\nline"},
        write_tzp_status_comments=True,
        status_by_key={"A": Status.TRANSLATED},
    )

    assert path.read_bytes() == (
        b'{\n  "A" : "two \\"quoted\\"\\npath",\n  "B": "\\u0411\\nline"\n}'
    )
    save(parsed, {"B": "Другі"})
    assert (
        path.read_bytes()
        == ('{\n  "A" : "two \\"quoted\\"\\npath",\n  "B": "Другі"\n}').encode()
    )
    assert parsed.entries[0].value == 'two "quoted"\npath'
    assert parsed.entries[1].value == "Другі"


def test_b42_json_atomic_save_failure_preserves_file_and_parsed_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed atomic replacement must not expose a partial file or model state."""
    path = tmp_path / "UI.json"
    original = b'{"A": "one"}'
    path.write_bytes(original)
    parsed = parse(path)
    original_entry = parsed.entries[0]

    def _fail_write(_path: Path, _data: bytes) -> None:
        raise OSError("simulated replacement failure")

    monkeypatch.setattr(
        "translationzed_py.core.translation_json.write_bytes_atomic", _fail_write
    )

    with pytest.raises(OSError, match="replacement failure"):
        save(parsed, {"A": "two"})

    assert path.read_bytes() == original
    assert parsed.raw_bytes() == original
    assert parsed.entries[0] == original_entry


def test_b42_json_save_rejects_invalid_values_and_skips_noop_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Save should reject unsafe runtime values and avoid writes for unchanged text."""
    path = tmp_path / "UI.json"
    path.write_bytes(b'{"A": "one"}')
    parsed = parse(path)
    writes: list[bytes] = []
    monkeypatch.setattr(
        "translationzed_py.core.translation_json.write_bytes_atomic",
        lambda _path, data: writes.append(data),
    )

    save(parsed, {"A": "one"})
    assert writes == []
    with pytest.raises(TranslationJSONError, match="must be a string"):
        save(parsed, {"A": 1})  # type: ignore[dict-item]
    with pytest.raises(TranslationJSONError, match="invalid Unicode"):
        save(parsed, {"A": "\ud800"})


def test_b42_json_insert_plan_uses_source_order_and_existing_anchors() -> None:
    """Missing members should keep source order without reordering target members."""
    plan = build_insert_plan(
        source_order=("A", "B", "C", "D"),
        target_order=("A", "D"),
        edited_new_values={"C": "three", "B": "two", "ignored": "value"},
    )

    assert [(item.key, item.anchor_key) for item in plan.items] == [
        ("B", "A"),
        ("C", "A"),
    ]


def test_b42_json_insert_missing_preserves_existing_bytes(
    tmp_path: Path,
) -> None:
    """JSON insertion should add only planned member bytes around an existing anchor."""
    path = tmp_path / "UI.json"
    path.write_bytes(b'{\n  "A" : "\\u0410",\n  "D":"last"\n}\n')

    inserted = insert_missing(
        path,
        source_order=("A", "B", "C", "D"),
        edited_new_values={"B": "Б", "C": "three"},
    )

    assert inserted == ("B", "C")
    assert (
        path.read_bytes()
        == (
            '{\n  "A" : "\\u0410",\n  "B": "Б",\n  "C": "three",\n  "D":"last"\n}\n'
        ).encode()
    )


@pytest.mark.parametrize(
    ("payload", "source_order", "values", "expected"),
    [
        (
            b'{"B":"bee"}',
            ("A", "B", "C"),
            {"A": "aye", "C": "see"},
            b'{"A": "aye", "B":"bee", "C": "see"}',
        ),
        (
            b"{\n}\n",
            ("A",),
            {"A": "one"},
            b'{\n    "A": "one"\n}\n',
        ),
    ],
)
def test_b42_json_insert_missing_handles_edge_positions(
    tmp_path: Path,
    payload: bytes,
    source_order: tuple[str, ...],
    values: dict[str, str],
    expected: bytes,
) -> None:
    """Insertion should handle members before, after, and without existing keys."""
    path = tmp_path / "UI.json"
    path.write_bytes(payload)

    insert_missing(path, source_order=source_order, edited_new_values=values)

    assert path.read_bytes() == expected


def test_b42_json_insert_missing_is_idempotent_and_atomic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Retries should not duplicate keys and failed replacement should preserve the file."""
    path = tmp_path / "UI.json"
    path.write_bytes(b'{"A":"one"}')
    insert_missing(path, source_order=("A", "B"), edited_new_values={"B": "two"})
    after_insert = path.read_bytes()
    writes: list[bytes] = []
    monkeypatch.setattr(
        "translationzed_py.core.translation_json.write_bytes_atomic",
        lambda _path, data: writes.append(data),
    )

    assert (
        insert_missing(
            path,
            source_order=("A", "B"),
            edited_new_values={"B": "two"},
        )
        == ()
    )
    assert writes == []

    path.write_bytes(b'{"A":"one"}')

    def _fail_write(_path: Path, _data: bytes) -> None:
        raise OSError("simulated insertion failure")

    monkeypatch.setattr(
        "translationzed_py.core.translation_json.write_bytes_atomic", _fail_write
    )
    with pytest.raises(OSError, match="insertion failure"):
        insert_missing(
            path,
            source_order=("A", "B"),
            edited_new_values={"B": "two"},
        )
    assert path.read_bytes() == b'{"A":"one"}'
    assert after_insert == b'{"A":"one", "B": "two"}'


def test_translation_format_handles_json_only_config_and_unrelated_cache() -> None:
    """Format helpers should deduplicate JSON and reject unknown cache suffixes."""
    assert supported_extensions(".json") == (".json",)
    assert (
        translation_relative_path(
            Path("BE/UI.cache"),
            legacy_extension=".txt",
            cache_extension=".bin",
        )
        is None
    )


def test_b42_json_cache_identity_cannot_collide_with_legacy_file(
    tmp_path: Path,
) -> None:
    """Same-named JSON and legacy files should always use distinct caches."""
    root = tmp_path / "project"
    locale = root / "BE"
    locale.mkdir(parents=True)
    legacy = locale / "UI.txt"
    legacy_with_json_stem = locale / "UI.json.txt"
    json_path = locale / "UI.json"
    legacy.write_text('A = "Адзін"\n', encoding="utf-8")
    legacy_with_json_stem.write_text('A = "Адзін"\n', encoding="utf-8")
    json_path.write_text('{"A": "Адзін"}', encoding="utf-8")
    legacy_pf = parse(legacy)
    json_pf = parse(json_path)
    object.__setattr__(legacy_pf.entries[0], "status", Status.TRANSLATED)
    object.__setattr__(json_pf.entries[0], "status", Status.PROOFREAD)

    write(root, legacy, legacy_pf.entries)
    write(root, json_path, json_pf.entries)

    assert cache_path(root, legacy).name == "UI.bin"
    assert cache_path(root, json_path).name == "UI.json.bin"
    assert cache_path(root, legacy) != cache_path(root, json_path)
    guarded_legacy_cache = cache_path(root, legacy_with_json_stem)
    assert guarded_legacy_cache.name == "UI.json.txt.bin"
    assert translation_relative_path(
        guarded_legacy_cache.relative_to(root / ".tzp" / "cache"),
        legacy_extension=".txt",
        cache_extension=".bin",
    ) == Path("BE/UI.json.txt")
