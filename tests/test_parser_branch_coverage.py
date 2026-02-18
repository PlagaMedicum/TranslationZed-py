"""Test module for parser branch coverage."""

from __future__ import annotations

from pathlib import Path

import pytest

from translationzed_py.core import parse, parse_lazy
from translationzed_py.core import parser as parser_module
from translationzed_py.core.parser import (
    Kind,
    _read_string_token,
    _segment_text,
    _tokenise,
)


def test_read_string_token_handles_doubled_quotes_before_closing() -> None:
    """Verify read string token scans through doubled quotes."""
    text = '"a""b"'
    assert _read_string_token(text, 0) == len(text)


def test_read_string_token_returns_end_for_unclosed_literal() -> None:
    """Verify read string token stops at end when quote is not closed."""
    text = '"unterminated'
    assert _read_string_token(text, 0) == len(text)


def test_tokenise_raises_on_encoding_length_mismatch() -> None:
    """Verify tokenise rejects invalid byte sequences under strict offsets."""
    data = b'KEY = "\x80"\n'
    with pytest.raises(ValueError, match="Encoding length mismatch"):
        list(_tokenise(data, encoding="utf-8"))


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (b"KEY = .bare value\n", ".bare value"),
        (b'KEY = .bare, NEXT = "x"\n', ".bare"),
        (b"KEY = .bare -- note\n", ".bare"),
        (b"KEY = .bare // note\n", ".bare"),
        (b"KEY = .bare /* note */\n", ".bare"),
    ],
)
def test_tokenise_salvages_unquoted_values_until_boundary(
    data: bytes, expected: str
) -> None:
    """Verify tokenise salvages malformed bare values to known boundaries."""
    string_tokens = [tok for tok in _tokenise(data) if tok.kind is Kind.STRING]
    assert string_tokens
    assert string_tokens[0].text.strip() == expected


def test_tokenise_reports_location_for_unknown_sequence() -> None:
    """Verify tokenise reports location details for unknown content."""
    with pytest.raises(SyntaxError, match="Unknown sequence at 0"):
        list(_tokenise(b"@\n"))


def test_segment_text_rstrips_unquoted_segments() -> None:
    """Verify segment text trims trailing spaces for unquoted values."""
    assert _segment_text("value   ") == "value"


def test_parse_ignores_equal_without_preceding_key(tmp_path: Path) -> None:
    """Verify parse ignores equals that are not attached to a key token."""
    path = tmp_path / "invalid_then_valid.txt"
    path.write_text('= "drop"\nGOOD = "ok"\n', encoding="utf-8")
    pf = parse(path)
    assert [entry.key for entry in pf.entries] == ["GOOD"]


def test_parse_raises_when_equal_exists_but_no_entries(tmp_path: Path) -> None:
    """Verify parse rejects files with assignment markers but no values."""
    path = tmp_path / "broken.txt"
    path.write_text("ONLY = \n", encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported file format"):
        parse(path)


def test_parse_falls_back_to_raw_when_equal_is_inside_literal(tmp_path: Path) -> None:
    """Verify parse treats files as raw when no assignment token is present."""
    path = tmp_path / "literal_equals.txt"
    path.write_text('"="\n', encoding="utf-8")
    pf = parse(path)
    assert len(pf.entries) == 1
    assert pf.entries[0].raw is True
    assert pf.entries[0].key == "literal_equals.txt"


def test_parse_lazy_news_file_sets_status_map_and_returns_raw(tmp_path: Path) -> None:
    """Verify parse lazy handles News files as raw and initializes status map."""
    path = tmp_path / "News_BE.txt"
    path.write_text('Line with "=" token\n', encoding="utf-8")
    parser_module._STATUS_MAP = {}

    pf = parse_lazy(path)

    assert len(pf.entries) == 1
    assert pf.entries[0].raw is True
    assert pf.entries[0].key == "News_BE.txt"
    assert "TRANSLATED" in parser_module._STATUS_MAP


def test_parse_lazy_raises_when_equal_exists_but_no_entries(tmp_path: Path) -> None:
    """Verify parse lazy rejects malformed assignments without values."""
    path = tmp_path / "broken_lazy.txt"
    path.write_text("ONLY = \n", encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported file format"):
        parse_lazy(path)


def test_parse_lazy_falls_back_without_detected_assignment_tokens(
    tmp_path: Path,
) -> None:
    """Verify parse lazy falls back to raw entry when saw_equal is false."""
    path = tmp_path / "lazy_literal_equals.txt"
    path.write_text('"="\n', encoding="utf-8")
    pf = parse_lazy(path)
    assert len(pf.entries) == 1
    assert pf.entries[0].raw is True
    assert pf.entries[0].key == "lazy_literal_equals.txt"
