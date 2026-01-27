import tempfile
from pathlib import Path

from translationzed_py.core import parse
from translationzed_py.core.model import Status
from translationzed_py.core.status_cache import read, write


def test_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "root"
        loc = root / "EN"
        loc.mkdir(parents=True)
        path = loc / "dummy.txt"
        path.write_text('GREETING = "Hi"\n', encoding="utf-8")

        pf = parse(path)  # proper ParsedFile
        # mutate frozen dataclass safely
        object.__setattr__(pf.entries[0], "status", Status.TRANSLATED)

        write(root, path, pf.entries)
        assert list(read(root, path).values()) == [Status.TRANSLATED]
