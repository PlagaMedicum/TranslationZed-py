from pathlib import Path

from translationzed_py.core.en_hash_cache import compute, read, write


def test_en_hash_roundtrip(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    en = root / "EN"
    en.mkdir(parents=True)
    file = en / "ui.txt"
    file.write_text("HELLO = \"Hi\"\n", encoding="utf-8")

    hashes = compute(root)
    assert hashes
    write(root, hashes)
    restored = read(root)
    assert restored == hashes
