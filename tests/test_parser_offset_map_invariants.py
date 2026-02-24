"""Parser offset-map invariants for fast-path encoding builders."""

from __future__ import annotations

from pathlib import Path

import pytest

from translationzed_py.core.parser import (
    Kind,
    _build_offset_map,
    _build_offset_map_legacy,
    _ensure_offset_map,
    _tokenise,
)


@pytest.mark.parametrize(
    ("encoding", "text"),
    [
        ("utf-8", 'Alpha Бета 😀 "quoted"'),
        ("utf-16-le", 'Alpha Бета 😀 "quoted"'),
        ("utf-16-be", 'Alpha Бета 😀 "quoted"'),
        ("cp1251", "Привет мир"),
    ],
)
def test_fast_offset_map_matches_legacy_for_supported_encodings(
    encoding: str,
    text: str,
) -> None:
    """Verify fast offset-map builders are byte-identical to legacy mapping."""
    raw = text.encode(encoding)
    fast = _build_offset_map(text, encoding)
    legacy = _build_offset_map_legacy(text, encoding)

    assert fast == legacy
    assert fast[0] == 0
    assert fast[-1] == len(raw)
    assert all(curr >= prev for prev, curr in zip(fast, fast[1:], strict=False))
    for idx, ch in enumerate(text):
        assert fast[idx + 1] - fast[idx] == len(ch.encode(encoding))


def test_ensure_offset_map_falls_back_when_hint_path_is_wrong() -> None:
    """Verify false single-byte hints recover through legacy offset fallback."""
    text = "日本語のテキスト"
    encoding = "cp932"
    raw = text.encode(encoding)

    offsets = _ensure_offset_map(text, encoding, expected_len=len(raw))

    assert offsets[-1] == len(raw)
    assert offsets == _build_offset_map_legacy(text, encoding)


@pytest.mark.parametrize("encoding", ["utf-8", "utf-16-le", "utf-16-be"])  # noqa: PT006
def test_token_spans_are_monotonic_and_decodable(encoding: str, tmp_path: Path) -> None:
    """Verify token spans are ordered and map back to original byte slices."""
    text = 'A = "Бэта😀" .. " tail" -- TRANSLATED\nB = "Two"\n'
    raw = text.encode(encoding)
    path = tmp_path / f"sample_{encoding}.txt"
    path.write_bytes(raw)

    tokens = list(_tokenise(raw, encoding=encoding))

    previous_start = 0
    for token in tokens:
        start, end = token.span
        assert 0 <= start <= end <= len(raw)
        assert start >= previous_start
        previous_start = start
        if token.kind is Kind.STRING:
            assert raw[start:end].decode(encoding) == token.text
