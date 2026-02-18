from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from translationzed_py.core.search_replace_service import (
    build_replace_request,
    replace_text,
)


@given(
    text=st.text(
        alphabet=st.characters(min_codepoint=32, max_codepoint=126),
        min_size=0,
        max_size=120,
    ),
    query=st.text(
        alphabet=st.characters(min_codepoint=33, max_codepoint=126),
        min_size=1,
        max_size=8,
    ),
    replacement=st.text(
        alphabet=st.characters(min_codepoint=32, max_codepoint=126),
        min_size=0,
        max_size=8,
    ),
)
@settings(max_examples=60, deadline=None)
def test_property_literal_replace_all_matches_python(
    text: str,
    query: str,
    replacement: str,
) -> None:
    """Literal replace-all behavior remains equivalent to Python str.replace."""
    req = build_replace_request(
        query=query,
        replacement=replacement,
        use_regex=False,
        case_sensitive=True,
    )
    assert req is not None

    changed, out = replace_text(
        text,
        pattern=req.pattern,
        replacement=req.replacement,
        use_regex=req.use_regex,
        matches_empty=req.matches_empty,
        has_group_ref=req.has_group_ref,
        mode="all",
    )

    expected = text.replace(query, replacement)
    assert out == expected
    assert changed is (out != text)
