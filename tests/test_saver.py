"""Test module for saver."""

from translationzed_py.core import parse
from translationzed_py.core.saver import save


def test_save_updates_spans(tmp_path):
    """Verify save updates spans."""
    path = tmp_path / "file.txt"
    path.write_text('A = "Hi"\nB = "Hello"\n', encoding="utf-8")

    pf = parse(path)
    save(pf, {"A": "Longer", "B": "X"})
    assert path.read_text(encoding="utf-8") == 'A = "Longer"\nB = "X"\n'

    # second save uses adjusted spans after length changes
    save(pf, {"B": "YY"})
    assert path.read_text(encoding="utf-8") == 'A = "Longer"\nB = "YY"\n'
    assert pf.entries[0].value == "Longer"
    assert pf.entries[1].value == "YY"


def test_save_preserves_concat_structure(tmp_path):
    """Verify save preserves concat structure."""
    path = tmp_path / "file.txt"
    path.write_text('HELLO = "Hel"  ..  "lo" -- cmt\n', encoding="utf-8")

    pf = parse(path)
    save(pf, {"HELLO": "Hola"})

    # preserve concat + trivia; only literals updated
    assert path.read_text(encoding="utf-8") == 'HELLO = "Hol"  ..  "a" -- cmt\n'


def test_save_escapes_special_chars(tmp_path):
    """Verify save escapes special chars."""
    path = tmp_path / "file.txt"
    path.write_text('A = "Hi"\n', encoding="utf-8")

    pf = parse(path)
    save(pf, {"A": "Line1\nLine2\\Path"})

    assert path.read_text(encoding="utf-8") == 'A = "Line1\\nLine2\\\\Path"\n'
