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
    assert supported_tm_import_suffixes() == (".tmx", ".xliff", ".po")


def test_iter_tm_pairs_unsupported_extension_raises(tmp_path: Path) -> None:
    path = tmp_path / "sample.csv"
    path.write_text("a,b,c\n", encoding="utf-8")

    try:
        list(iter_tm_pairs(path, "EN", "BE"))
    except ValueError as exc:
        assert "Unsupported TM import format" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unsupported extension")


def test_detect_tm_languages_unsupported_extension_returns_empty(tmp_path: Path) -> None:
    path = tmp_path / "sample.csv"
    path.write_text("a,b,c\n", encoding="utf-8")
    assert detect_tm_languages(path) == set()
