"""Test module for saver."""

from translationzed_py.core import parse
from translationzed_py.core.model import Status
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


def test_save_tzp_comment_writeback_inserts_and_keeps_spans_valid(tmp_path) -> None:
    """TZP write-back should insert comments and keep spans valid for follow-up saves."""
    path = tmp_path / "file.txt"
    path.write_text('A = "Hi"\nB = "Bye"\n', encoding="utf-8")

    pf = parse(path)
    save(
        pf,
        {"A": "Hola"},
        write_tzp_status_comments=True,
        status_by_key={"A": Status.TRANSLATED},
    )
    assert path.read_text(encoding="utf-8") == (
        'A = "Hola" -- TZP:TRANSLATED\nB = "Bye"\n'
    )

    # Re-save another key to prove spans remained authoritative after comment insertion.
    save(pf, {"B": "Ciao"})
    assert path.read_text(encoding="utf-8") == (
        'A = "Hola" -- TZP:TRANSLATED\nB = "Ciao"\n'
    )


def test_save_tzp_comment_writeback_updates_existing_tzp_comment(tmp_path) -> None:
    """Existing TZP comments should be updated to canonical target status."""
    path = tmp_path / "file.txt"
    path.write_text('A = "Hi" -- TZP:TRANSLATED\n', encoding="utf-8")

    pf = parse(path)
    save(
        pf,
        {"A": "Hey"},
        write_tzp_status_comments=True,
        status_by_key={"A": Status.PROOFREAD},
    )

    assert path.read_text(encoding="utf-8") == 'A = "Hey" -- TZP:PROOFREAD\n'


def test_save_tzp_comment_writeback_does_not_mutate_user_comments(tmp_path) -> None:
    """Write-back must not rewrite user-authored comments without TZP namespace."""
    path = tmp_path / "file.txt"
    path.write_text('A = "Hi" -- translator note\n', encoding="utf-8")

    pf = parse(path)
    save(
        pf,
        {"A": "Hey"},
        write_tzp_status_comments=True,
        status_by_key={"A": Status.TRANSLATED},
    )

    assert path.read_text(encoding="utf-8") == 'A = "Hey" -- translator note\n'


def test_save_tzp_comment_writeback_removes_tzp_for_untouched_override(
    tmp_path,
) -> None:
    """Explicit untouched override should remove existing TZP marker comments."""
    path = tmp_path / "file.txt"
    path.write_text('A = "Hi" -- TZP:FOR_REVIEW\nB = "Yo"\n', encoding="utf-8")

    pf = parse(path)
    save(
        pf,
        {"B": "Yep"},
        write_tzp_status_comments=True,
        status_by_key={"A": Status.UNTOUCHED},
    )

    assert path.read_text(encoding="utf-8") == 'A = "Hi" \nB = "Yep"\n'
