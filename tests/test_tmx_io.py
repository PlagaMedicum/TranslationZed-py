from pathlib import Path

from translationzed_py.core.tmx_io import (
    detect_tmx_languages,
    iter_tmx_pairs,
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
