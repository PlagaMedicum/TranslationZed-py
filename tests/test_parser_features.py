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


def test_parse_cp1251(prod_like_root):
    path = prod_like_root / "RU" / "IG_UI_RU.txt"
    pf = parse(path, encoding="Cp1251")
    assert pf.entries[0].key == "UI_OK"
    assert pf.entries[0].value == "Тест"


def test_parse_utf16(prod_like_root):
    path = prod_like_root / "KO" / "IG_UI_KO.txt"
    pf = parse(path, encoding="UTF-16")
    assert pf.entries[0].key == "UI_OK"
