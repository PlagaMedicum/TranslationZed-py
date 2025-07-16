from translationzed_py.core import Status, parse


def _tmp(txt: str, tmp_path):
    file = tmp_path / "f.txt"
    file.write_text(txt)
    return parse(file)


def test_escaped_quotes(tmp_path):
    pf = _tmp('QUOTE = "He said \\"hi\\""\n', tmp_path)
    assert pf.entries[0].value == 'He said "hi"'


def test_concat(tmp_path):
    pf = _tmp('HELLO = "Hel"  ..  "lo"\n', tmp_path)
    assert pf.entries[0].value == "Hello"


def test_status_comment(tmp_path):
    pf = _tmp('UI_YES = "Так" -- PROOFREAD\n', tmp_path)
    assert pf.entries[0].status is Status.PROOFREAD
