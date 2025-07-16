import tempfile
from pathlib import Path

from translationzed_py.core import parse
from translationzed_py.core.model import Status
from translationzed_py.core.status_cache import read, write


def test_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        loc = Path(tmp)
        (loc / "dummy.txt").write_text('GREETING = "Hi"\n', encoding="utf-8")

        pf = parse(loc / "dummy.txt")  # proper ParsedFile
        # mutate frozen dataclass safely
        object.__setattr__(pf.entries[0], "status", Status.TRANSLATED)

        write(loc, [pf])
        assert list(read(loc).values()) == [Status.TRANSLATED]
