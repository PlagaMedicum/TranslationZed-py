import struct
from pathlib import Path

from translationzed_py.core.tmx_io import (
    detect_tm_languages,
    detect_tmx_languages,
    iter_tm_pairs,
    iter_tmx_pairs,
    supported_tm_import_suffixes,
    write_tmx,
)


def test_tmx_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "sample.tmx"
    pairs = [("Hello", "Privet"), ("Bye", "Poka")]
    write_tmx(path, pairs, source_locale="EN", target_locale="BE")
    parsed = list(iter_tmx_pairs(path, "EN", "BE"))
    assert parsed == pairs
    langs = detect_tmx_languages(path)
    assert "EN" in langs
    assert "BE" in langs


def test_iter_tmx_pairs_matches_bcp47_region_variants(tmp_path: Path) -> None:
    path = tmp_path / "variants.tmx"
    path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<tmx version="1.4">
  <header
    creationtool="test"
    creationtoolversion="1"
    datatype="PlainText"
    segtype="sentence"
    srclang="en-US"
  />
  <body>
    <tu>
      <tuv xml:lang="en-US"><seg>Hello world</seg></tuv>
      <tuv xml:lang="be-BY"><seg>Прывітанне свет</seg></tuv>
    </tu>
  </body>
</tmx>
""",
        encoding="utf-8",
    )
    parsed = list(iter_tmx_pairs(path, "EN", "BE"))
    assert parsed == [("Hello world", "Прывітанне свет")]


def test_iter_tm_pairs_xliff_and_detect_languages(tmp_path: Path) -> None:
    path = tmp_path / "sample.xliff"
    path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2">
  <file source-language="en-US" target-language="be-BY" datatype="plaintext">
    <body>
      <trans-unit id="1">
        <source>Hello world</source>
        <target>Прывітанне свет</target>
      </trans-unit>
    </body>
  </file>
</xliff>
""",
        encoding="utf-8",
    )
    parsed = list(iter_tm_pairs(path, "EN", "BE"))
    assert parsed == [("Hello world", "Прывітанне свет")]
    langs = detect_tm_languages(path)
    assert "en-US" in langs
    assert "be-BY" in langs


def test_iter_tm_pairs_po_and_detect_languages(tmp_path: Path) -> None:
    path = tmp_path / "sample.po"
    path.write_text(
        """
msgid ""
msgstr ""
"Language: be\\n"
"X-Source-Language: en\\n"

msgid "Hello world"
msgstr "Прывітанне свет"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    parsed = list(iter_tm_pairs(path, "EN", "BE"))
    assert parsed == [("Hello world", "Прывітанне свет")]
    langs = detect_tm_languages(path)
    assert "en" in langs
    assert "be" in langs


def test_supported_tm_import_suffixes() -> None:
    assert supported_tm_import_suffixes() == (
        ".tmx",
        ".xliff",
        ".xlf",
        ".po",
        ".pot",
        ".csv",
        ".mo",
        ".xml",
    )


def test_iter_tm_pairs_xlf_alias(tmp_path: Path) -> None:
    path = tmp_path / "sample.xlf"
    path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2">
  <file source-language="en-US" target-language="be-BY" datatype="plaintext">
    <body>
      <trans-unit id="1">
        <source>Hello world</source>
        <target>Прывітанне свет</target>
      </trans-unit>
    </body>
  </file>
</xliff>
""",
        encoding="utf-8",
    )
    parsed = list(iter_tm_pairs(path, "EN", "BE"))
    assert parsed == [("Hello world", "Прывітанне свет")]
    langs = detect_tm_languages(path)
    assert "en-US" in langs
    assert "be-BY" in langs


def test_iter_tm_pairs_pot_alias(tmp_path: Path) -> None:
    path = tmp_path / "sample.pot"
    path.write_text(
        """
msgid ""
msgstr ""
"Language: be\\n"
"X-Source-Language: en\\n"

msgid "Hello world"
msgstr "Прывітанне свет"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    parsed = list(iter_tm_pairs(path, "EN", "BE"))
    assert parsed == [("Hello world", "Прывітанне свет")]
    langs = detect_tm_languages(path)
    assert "en" in langs
    assert "be" in langs


def test_iter_tm_pairs_csv_with_header(tmp_path: Path) -> None:
    path = tmp_path / "sample.csv"
    path.write_text(
        "source,target\n" "Hello world,Прывітанне свет\n" "Drop all,Скінуць усё\n",
        encoding="utf-8",
    )
    parsed = list(iter_tm_pairs(path, "EN", "BE"))
    assert parsed == [
        ("Hello world", "Прывітанне свет"),
        ("Drop all", "Скінуць усё"),
    ]


def test_iter_tm_pairs_csv_without_header(tmp_path: Path) -> None:
    path = tmp_path / "sample.csv"
    path.write_text(
        "Hello world,Прывітанне свет\n" "Drop all,Скінуць усё\n",
        encoding="utf-8",
    )
    parsed = list(iter_tm_pairs(path, "EN", "BE"))
    assert parsed == [
        ("Hello world", "Прывітанне свет"),
        ("Drop all", "Скінуць усё"),
    ]


def test_detect_tm_languages_csv_from_locale_columns(tmp_path: Path) -> None:
    path = tmp_path / "sample.csv"
    path.write_text(
        "source_locale,target_locale,source,target\n"
        "en,be,Hello world,Прывітанне свет\n"
        "en,be,Drop all,Скінуць усё\n",
        encoding="utf-8",
    )
    langs = detect_tm_languages(path)
    assert langs == {"en", "be"}


def test_iter_tm_pairs_mo_and_detect_languages(tmp_path: Path) -> None:
    path = tmp_path / "sample.mo"
    _write_mo(
        path,
        {
            "": (
                "Content-Type: text/plain; charset=UTF-8\n"
                "Language: be\n"
                "X-Source-Language: en\n"
            ),
            "Hello world": "Прывітанне свет",
            "Drop all": "Скінуць усё",
        },
    )
    parsed = list(iter_tm_pairs(path, "EN", "BE"))
    assert parsed == [
        ("Drop all", "Скінуць усё"),
        ("Hello world", "Прывітанне свет"),
    ]
    langs = detect_tm_languages(path)
    assert "en" in langs
    assert "be" in langs


def test_iter_tm_pairs_xml_and_detect_languages(tmp_path: Path) -> None:
    path = tmp_path / "sample.xml"
    path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<xliff source-language="en-US" target-language="be-BY">
  <file source-language="en-US" target-language="be-BY">
    <body>
      <trans-unit id="1">
        <source>Hello world</source>
        <target>Прывітанне свет</target>
      </trans-unit>
    </body>
  </file>
</xliff>
""",
        encoding="utf-8",
    )
    parsed = list(iter_tm_pairs(path, "EN", "BE"))
    assert parsed == [("Hello world", "Прывітанне свет")]
    langs = detect_tm_languages(path)
    assert "en-US" in langs
    assert "be-BY" in langs


def test_iter_tm_pairs_unsupported_extension_raises(tmp_path: Path) -> None:
    path = tmp_path / "sample.json"
    path.write_text('{"a": 1}\n', encoding="utf-8")

    try:
        list(iter_tm_pairs(path, "EN", "BE"))
    except ValueError as exc:
        assert "Unsupported TM import format" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unsupported extension")


def test_detect_tm_languages_unsupported_extension_returns_empty(
    tmp_path: Path,
) -> None:
    path = tmp_path / "sample.json"
    path.write_text('{"a": 1}\n', encoding="utf-8")
    assert detect_tm_languages(path) == set()


def _write_mo(path: Path, entries: dict[str, str]) -> None:
    items = sorted(entries.items(), key=lambda item: item[0])
    ids = b""
    strings = b""
    id_offsets: list[tuple[int, int]] = []
    str_offsets: list[tuple[int, int]] = []
    original_base = 28 + len(items) * 16
    for source, _target in items:
        raw = source.encode("utf-8")
        id_offsets.append((len(raw), original_base + len(ids)))
        ids += raw + b"\x00"
    translation_base = original_base + len(ids)
    for _source, target in items:
        raw = target.encode("utf-8")
        str_offsets.append((len(raw), translation_base + len(strings)))
        strings += raw + b"\x00"
    with path.open("wb") as handle:
        handle.write(
            struct.pack("<7I", 0x950412DE, 0, len(items), 28, 28 + len(items) * 8, 0, 0)
        )
        for length, offset in id_offsets:
            handle.write(struct.pack("<2I", length, offset))
        for length, offset in str_offsets:
            handle.write(struct.pack("<2I", length, offset))
        handle.write(ids)
        handle.write(strings)
