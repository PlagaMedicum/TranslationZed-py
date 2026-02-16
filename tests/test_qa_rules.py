from __future__ import annotations

from translationzed_py.core.qa_rules import (
    extract_protected_tokens,
    has_missing_trailing_fragment,
    has_newline_mismatch,
    missing_protected_tokens,
    newline_count,
    same_as_source,
    trailing_fragment,
)


def test_extract_protected_tokens_detects_code_like_tokens_only() -> None:
    text = "[img=music] <LINE> <CENTRE> %1 %1$s \\n " "<gasps from the courtroom> plain"
    assert extract_protected_tokens(text) == (
        "[img=music]",
        "<LINE>",
        "<CENTRE>",
        "%1",
        "%1$s",
        "\\n",
    )


def test_missing_protected_tokens_handles_duplicates() -> None:
    source = "<LINE> %1 %1"
    target = "<LINE> %1"
    assert missing_protected_tokens(source, target) == ("%1",)


def test_trailing_fragment_and_missing_trailing_check() -> None:
    assert trailing_fragment("Hello!") == "!"
    assert has_missing_trailing_fragment("Hello!", "Hello") is True
    assert has_missing_trailing_fragment("Hello", "Hello!") is False
    assert has_missing_trailing_fragment("Wait...", "Wait..") is True
    assert has_missing_trailing_fragment("Wait...", "Wait...") is False


def test_newline_mismatch_normalizes_crlf() -> None:
    source = "A\r\nB\nC"
    assert newline_count(source) == 2
    assert has_newline_mismatch(source, "A\nB\nC") is False
    assert has_newline_mismatch(source, "A\nBC") is True
    assert newline_count(r"A\nB") == 1
    assert has_newline_mismatch(r"A\nB", "AB") is True


def test_same_as_source_requires_exact_match() -> None:
    assert same_as_source("Text", "Text") is True
    assert same_as_source("Text", "text") is False
