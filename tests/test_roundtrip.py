from pathlib import Path

from translationzed_py.core import parse


def test_roundtrip(tmp_path: Path):
    f = tmp_path / "test.txt"
    f.write_text('UI_YES = "Yes"\n')
    pf = parse(f)
    assert pf.raw_bytes() == f.read_bytes()
    assert len(pf.entries) == 1
    assert pf.entries[0].key == "UI_YES"
