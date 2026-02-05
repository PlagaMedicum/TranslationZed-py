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
