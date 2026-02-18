from __future__ import annotations

import string
import tempfile
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from translationzed_py.core.parser import parse
from translationzed_py.core.saver import save

_KEY = st.text(
    alphabet=string.ascii_uppercase + string.digits + "_",
    min_size=1,
    max_size=20,
).filter(lambda value: value[0].isalpha() or value[0] == "_")
_VALUE = st.text(
    alphabet=string.ascii_letters + string.digits + " _-.:,",
    min_size=0,
    max_size=60,
)


@given(
    st.lists(
        st.tuples(_KEY, _VALUE), min_size=1, max_size=25, unique_by=lambda pair: pair[0]
    )
)
@settings(max_examples=40, deadline=None)
def test_property_parser_saver_roundtrip_identity(
    pairs: list[tuple[str, str]],
) -> None:
    """Saving unchanged parsed values preserves file bytes."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "property.txt"
        content = "".join(f'{key} = "{value}"\n' for key, value in pairs)
        path.write_text(content, encoding="utf-8")

        parsed = parse(path, encoding="utf-8")
        values = {entry.key: entry.value for entry in parsed.entries}

        save(parsed, values, encoding="utf-8")

        assert path.read_bytes() == content.encode("utf-8")
