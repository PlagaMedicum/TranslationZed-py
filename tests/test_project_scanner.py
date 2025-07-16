from pathlib import Path

from translationzed_py.core import scan_root


def test_scan_root_discovers_locales(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    for loc in ("EN", "BE"):
        (root / loc).mkdir()
        (root / loc / "ui.txt").write_text("dummy")
    result = scan_root(root)
    assert set(result) == {"EN", "BE"}
