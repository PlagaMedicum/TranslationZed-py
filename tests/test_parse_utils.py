"""Test module for parse utils."""

from __future__ import annotations

from translationzed_py.core.parse_utils import (
    _decode_text,
    _hash_key_u64,
    _resolve_encoding,
    _unescape,
    _unescape_prefix,
)


def test_unescape_returns_input_without_escape_markers() -> None:
    """Verify unescape fast path for plain input."""
    assert _unescape("alpha beta") == "alpha beta"


def test_unescape_handles_quotes_backslashes_and_unknown_sequences() -> None:
    """Verify unescape applies supported escapes and keeps others literal."""
    raw = 'He said \\"hi\\" and \\\\ path and \\n marker'
    assert _unescape(raw) == 'He said "hi" and \\ path and \\n marker'
    assert _unescape('a ""quoted"" value') == 'a "quoted" value'


def test_unescape_prefix_obeys_limit_and_supported_escapes() -> None:
    """Verify unescape prefix truncates by output length."""
    assert _unescape_prefix('\\"ab\\"cd', 3) == '"ab'
    assert _unescape_prefix('a ""quoted"" value', 5) == 'a "qu'


def test_unescape_prefix_handles_non_positive_limits() -> None:
    """Verify unescape prefix returns empty text for non-positive limits."""
    assert _unescape_prefix("anything", 0) == ""
    assert _unescape_prefix("anything", -3) == ""


def test_resolve_encoding_detects_utf8_bom() -> None:
    """Verify resolve encoding strips UTF-8 BOM length."""
    assert _resolve_encoding("utf-8", b"\xef\xbb\xbfabc") == ("utf-8", 3)


def test_resolve_encoding_detects_utf16_boms() -> None:
    """Verify resolve encoding identifies UTF-16 BOM variants."""
    assert _resolve_encoding("utf-16", b"\xff\xfeA\x00") == ("utf-16-le", 2)
    assert _resolve_encoding("utf-16", b"\xfe\xff\x00A") == ("utf-16-be", 2)


def test_resolve_encoding_handles_utf16_without_bom() -> None:
    """Verify resolve encoding falls back to UTF-16 heuristics."""
    assert _resolve_encoding("utf-16", b"") == ("utf-16-le", 0)
    assert _resolve_encoding("utf-16", b"A\x00B\x00") == ("utf-16-le", 0)
    assert _resolve_encoding("utf-16", b"\x00A\x00B") == ("utf-16-be", 0)
    assert _resolve_encoding("utf-16", b"\x00\x00") == ("utf-16-le", 0)


def test_resolve_encoding_preserves_non_utf16_encodings() -> None:
    """Verify resolve encoding returns requested non-UTF16 encoding."""
    assert _resolve_encoding("cp1251", b"raw bytes") == ("cp1251", 0)


def test_decode_text_strips_decoded_bom_character() -> None:
    """Verify decode text removes BOM code point from decoded text."""
    assert _decode_text(b"\xef\xbb\xbfhello", "utf-8") == "hello"
    assert _decode_text(b"plain", "utf-8") == "plain"


def test_hash_key_u64_is_stable_and_masked() -> None:
    """Verify hash key helper is deterministic and bounded to uint64."""
    first = _hash_key_u64("alpha")
    second = _hash_key_u64("alpha")
    third = _hash_key_u64("beta")

    assert first == second
    assert 0 <= first <= 0xFFFFFFFFFFFFFFFF
    assert 0 <= third <= 0xFFFFFFFFFFFFFFFF
    assert first != third
