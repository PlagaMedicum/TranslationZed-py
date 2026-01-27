import tempfile
from pathlib import Path

from translationzed_py.core import parse
from translationzed_py.core.model import Status
from translationzed_py.core.status_cache import CacheEntry, read, write


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
        assert list(read(root, path).values()) == [CacheEntry(Status.TRANSLATED, None)]


def test_roundtrip_with_value_override():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "root"
        loc = root / "EN"
        loc.mkdir(parents=True)
        path = loc / "dummy.txt"
        path.write_text('GREETING = "Hi"\n', encoding="utf-8")

        pf = parse(path)
        object.__setattr__(pf.entries[0], "status", Status.TRANSLATED)
        object.__setattr__(pf.entries[0], "value", "Hello!")

        write(root, path, pf.entries, changed_keys={"GREETING"})
        entry = list(read(root, path).values())[0]
        assert entry.status == Status.TRANSLATED
        assert entry.value == "Hello!"


def test_write_skips_empty_cache():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "root"
        loc = root / "EN"
        loc.mkdir(parents=True)
        path = loc / "dummy.txt"
        path.write_text('GREETING = "Hi"\n', encoding="utf-8")

        pf = parse(path)
        write(root, path, pf.entries, changed_keys=set())
        cache_path = root / ".tzp-cache" / "EN" / "dummy.bin"
        assert not cache_path.exists()
        assert not (root / ".tzp-cache").exists()
