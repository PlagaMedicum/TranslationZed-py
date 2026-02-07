from translationzed_py.core import Status, parse, parse_lazy


def _tmp(txt: str, tmp_path):
    file = tmp_path / "f.txt"
    file.write_text(txt, encoding="utf-8")
    return parse(file)


def test_escaped_quotes(tmp_path):
    pf = _tmp('QUOTE = "He said \\"hi\\""\n', tmp_path)
    assert pf.entries[0].value == 'He said "hi"'


def test_concat(tmp_path):
    pf = _tmp('HELLO = "Hel"  ..  "lo"\n', tmp_path)
    assert pf.entries[0].value == "Hello"


def test_concat_multiline(tmp_path):
    pf = _tmp('HELLO = "Hel"  ..\n  "lo"\n', tmp_path)
    assert pf.entries[0].value == "Hello"


def test_concat_multiline_lazy(tmp_path):
    file = tmp_path / "f.txt"
    file.write_text('HELLO = "Hel"  ..\n  "lo"\n', encoding="utf-8")
    pf = parse_lazy(file)
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


def test_parse_utf16_no_bom_le(tmp_path):
    path = tmp_path / "utf16le.txt"
    path.write_bytes('UI_OK = "Test"\n'.encode("utf-16-le"))
    pf = parse(path, encoding="UTF-16")
    assert pf.entries[0].value == "Test"


def test_parse_utf16_no_bom_be(tmp_path):
    path = tmp_path / "utf16be.txt"
    path.write_bytes('UI_OK = "Test"\n'.encode("utf-16-be"))
    pf = parse(path, encoding="UTF-16")
    assert pf.entries[0].value == "Test"


def test_parse_lua_table_blocks(tmp_path):
    text = """
Challenge_BE = {
    Challenge_One_name = "One",
    Challenge_Two_desc = "Two",
}
"""
    pf = _tmp(text, tmp_path)
    keys = [e.key for e in pf.entries]
    assert "Challenge_One_name" in keys
    assert "Challenge_Two_desc" in keys


def test_parse_dotted_keys(tmp_path):
    pf = _tmp('EvolvedRecipeName_Base.CannedTomatoOpen = "Tomato"\n', tmp_path)
    assert pf.entries[0].key == "EvolvedRecipeName_Base.CannedTomatoOpen"


def test_parse_table_header_without_equals(tmp_path):
    text = """
DynamicRadio_BE {
    AEBS_Intro = "Hello",
}
"""
    pf = _tmp(text, tmp_path)
    keys = [e.key for e in pf.entries]
    assert "AEBS_Intro" in keys


def test_parse_unterminated_string_line(tmp_path):
    text = 'BAD = "Missing quote\nOK = "Fine"\n'
    pf = _tmp(text, tmp_path)
    assert pf.entries[0].key == "BAD"
    assert pf.entries[0].value == "Missing quote"
    assert pf.entries[1].key == "OK"
    assert pf.entries[1].value == "Fine"


def test_parse_block_comments(tmp_path):
    text = """
A = "1"
/* comment */
B = "2"
"""
    pf = _tmp(text, tmp_path)
    keys = [e.key for e in pf.entries]
    assert keys == ["A", "B"]


def test_parse_stray_quote_with_markup(tmp_path):
    text = """
X = " <CENTRE> "<SIZE:large> hello",
Y = "Ok"
"""
    pf = _tmp(text, tmp_path)
    assert pf.entries[0].key == "X"
    assert "<SIZE:large>" in pf.entries[0].value
    assert pf.entries[1].key == "Y"


def test_parse_inline_quotes_with_trailing_text(tmp_path):
    text = (
        'X = "Use /startrain "intensity", optional intensity is from 1 to 100",\n'
        'Y = "Ok"\n'
    )
    pf = _tmp(text, tmp_path)
    assert pf.entries[0].key == "X"
    assert "intensity" in pf.entries[0].value
    assert pf.entries[1].key == "Y"


def test_parse_double_slash_comment(tmp_path):
    text = """// Auto-generated file
X = "Hello"
"""
    pf = _tmp(text, tmp_path)
    assert pf.entries[0].key == "X"


def test_parse_inner_quotes_with_ellipsis(tmp_path):
    text = 'X = "...called "baldie", "egghead", "skinskull"..."\n'
    pf = _tmp(text, tmp_path)
    assert pf.entries[0].key == "X"
    assert "skinskull" in pf.entries[0].value


def test_parse_inner_quotes_with_ellipsis_lazy(tmp_path):
    text = 'X = "...called "baldie", "egghead", "skinskull"..."\n'
    file = tmp_path / "lazy.txt"
    file.write_text(text, encoding="utf-8")
    pf = parse_lazy(file)
    assert pf.entries[0].key == "X"
    assert "skinskull" in pf.entries[0].value


def test_parse_keys_with_spaces_and_symbols(tmp_path):
    pf = _tmp('UI_optionscreen_binding_Equip/Unequip Handweapon = "Ok"\n', tmp_path)
    assert pf.entries[0].key == "UI_optionscreen_binding_Equip/Unequip Handweapon"


def test_parse_plain_text_as_single_entry(tmp_path):
    file = tmp_path / "title.txt"
    file.write_text("Plain text", encoding="utf-8")
    pf = parse(file)
    assert len(pf.entries) == 1
    assert pf.entries[0].key == "title.txt"
    assert pf.entries[0].raw is True


def test_parse_news_as_raw(tmp_path):
    file = tmp_path / "News_BE.txt"
    file.write_text('Line with "=" and "quotes"\n', encoding="utf-8")
    pf = parse(file)
    assert len(pf.entries) == 1
    assert pf.entries[0].key == "News_BE.txt"
    assert pf.entries[0].raw is True
