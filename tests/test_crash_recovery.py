from pathlib import Path

import tempfile

from translationzed_py.core import crash_recovery


def test_crash_recovery_write_read_clear(tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))
    root = tmp_path / "proj"
    root.mkdir()
    file_path = root / "BE" / "ui.txt"
    file_path.parent.mkdir()
    file_path.write_text('A = "Hi"\n', encoding="utf-8")

    crash_recovery.write(root, [file_path])
    data = crash_recovery.read()
    assert data is not None
    assert data["root"] == str(root.resolve())
    assert data["files"] == ["BE/ui.txt"]

    crash_recovery.clear()
    assert crash_recovery.read() is None


def test_crash_recovery_discard_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))
    root = tmp_path / "proj"
    root.mkdir()
    rel_file = Path("BE") / "ui.txt"
    cache_path = root / ".tzp-cache" / "BE" / "ui.bin"
    cache_path.parent.mkdir(parents=True)
    cache_path.write_bytes(b"dummy")

    crash_recovery.discard_cache(root, [rel_file.as_posix()])
    assert not cache_path.exists()
