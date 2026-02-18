"""Test module for property encoding invariants."""

from __future__ import annotations

import tempfile
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from translationzed_py.core.parser import parse
from translationzed_py.core.saver import save


@given(
    encoding=st.sampled_from(["utf-8", "cp1251", "utf-16"]),
    initial=st.text(
        alphabet=st.characters(min_codepoint=32, max_codepoint=126),
        min_size=0,
        max_size=40,
    ),
    updated=st.text(
        alphabet=st.characters(min_codepoint=32, max_codepoint=126),
        min_size=0,
        max_size=40,
    ),
)
@settings(max_examples=45, deadline=None)
def test_property_save_respects_declared_encoding(
    encoding: str,
    initial: str,
    updated: str,
) -> None:
    """Save path keeps the declared file encoding stable."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "enc.txt"
        path.write_text(f'KEY = "{initial}"\n', encoding=encoding)

        parsed = parse(path, encoding=encoding)
        save(parsed, {"KEY": updated}, encoding=encoding)

        data = path.read_bytes()
        reparsed = parse(path, encoding=encoding)
        assert len(reparsed.entries) == 1
        assert reparsed.entries[0].value == updated

        if encoding == "utf-16":
            assert data[:2] in {b"\xff\xfe", b"\xfe\xff"}
        else:
            assert data[:2] not in {b"\xff\xfe", b"\xfe\xff"}
