"""Test module for tmx io internals."""

import zipfile
from pathlib import Path

import pytest
from defusedxml import ElementTree as ET

from translationzed_py.core.tmx_io import (
    _first_xlsx_sheet_path,
    _locale_matches,
    _mo_source_text,
    _mo_target_text,
    _parse_po_quoted,
    _read_xlsx_shared_strings,
    _seg_text,
    _xlsx_cell_text,
    _xlsx_col_from_ref,
    _xml_lang_hint,
    _xml_source_target_children,
    iter_tm_pairs,
)


def test_tmx_io_helper_guards_cover_empty_values() -> None:
    """Verify helper guards return safe defaults for empty values."""
    assert _seg_text(None) == ""
    assert _locale_matches("", "en", "en") is False
    assert _xlsx_col_from_ref("") == -1
    assert _xlsx_col_from_ref("123") == -1
    assert _xlsx_col_from_ref("AA10") == 26


def test_read_xlsx_shared_strings_reads_only_si_nodes(tmp_path: Path) -> None:
    """Verify shared string parsing ignores non-si nodes."""
    path = tmp_path / "shared.xlsx"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "xl/sharedStrings.xml",
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                "<si><t>First</t></si><ignored/><si><r><t>Second</t></r></si>"
                "</sst>"
            ),
        )

    with zipfile.ZipFile(path) as archive:
        assert _read_xlsx_shared_strings(archive) == ["First", "Second"]


def test_first_xlsx_sheet_path_fallback_and_missing_sheet_error(tmp_path: Path) -> None:
    """Verify worksheet path resolution handles fallback and missing sheets."""
    path = tmp_path / "fallback.xlsx"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("xl/worksheets/sheet2.xml", "<worksheet/>")
        archive.writestr("xl/worksheets/sheet1.xml", "<worksheet/>")

    with zipfile.ZipFile(path) as archive:
        assert _first_xlsx_sheet_path(archive) == "xl/worksheets/sheet1.xml"

    empty = tmp_path / "empty.xlsx"
    with zipfile.ZipFile(empty, "w", compression=zipfile.ZIP_DEFLATED):
        pass

    with (
        zipfile.ZipFile(empty) as archive,
        pytest.raises(ValueError, match="no worksheet"),
    ):
        _first_xlsx_sheet_path(archive)


def test_first_xlsx_sheet_path_prefers_workbook_relationship_target(
    tmp_path: Path,
) -> None:
    """Verify workbook relationship mapping chooses the declared first sheet."""
    path = tmp_path / "rels.xlsx"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "xl/workbook.xml",
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                '<sheets><sheet name="S" sheetId="1" r:id="rId1"/></sheets>'
                "</workbook>"
            ),
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" '
                "Type="
                '"http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
                'Target="/worksheets/sheet2.xml"/>'
                "</Relationships>"
            ),
        )
        archive.writestr("xl/worksheets/sheet1.xml", "<worksheet/>")
        archive.writestr("xl/worksheets/sheet2.xml", "<worksheet/>")

    with zipfile.ZipFile(path) as archive:
        assert _first_xlsx_sheet_path(archive) == "xl/worksheets/sheet2.xml"


def test_xlsx_cell_text_handles_inline_shared_and_raw_variants() -> None:
    """Verify xlsx cell text conversion handles supported cell type variants."""
    inline = ET.fromstring('<c t="inlineStr"><is><t> Inline </t></is></c>')
    inline_missing = ET.fromstring('<c t="inlineStr"><v>1</v></c>')
    raw = ET.fromstring("<c><v> 42 </v></c>")
    as_is = ET.fromstring("<c><is><t>Literal</t></is></c>")
    shared_ok = ET.fromstring('<c t="s"><v>1</v></c>')
    shared_bad_value = ET.fromstring('<c t="s"><v>NaN</v></c>')
    shared_out_of_bounds = ET.fromstring('<c t="s"><v>9</v></c>')

    assert _xlsx_cell_text(inline, ["unused"]) == "Inline"
    assert _xlsx_cell_text(inline_missing, ["unused"]) == ""
    assert _xlsx_cell_text(raw, ["unused"]) == "42"
    assert _xlsx_cell_text(as_is, ["unused"]) == "Literal"
    assert _xlsx_cell_text(shared_ok, ["zero", "one"]) == "one"
    assert _xlsx_cell_text(shared_bad_value, ["zero"]) == ""
    assert _xlsx_cell_text(shared_out_of_bounds, ["zero"]) == ""


def test_xml_helpers_return_source_target_and_language_hints() -> None:
    """Verify xml helper functions resolve source and target elements and hints."""
    unit = ET.fromstring(
        "<unit source_lang='en' target_locale='be'>"
        "<source>Hello</source><translated>Прывітанне</translated></unit>"
    )
    source, target = _xml_source_target_children(unit)

    assert source is not None
    assert target is not None
    assert _seg_text(source) == "Hello"
    assert _seg_text(target) == "Прывітанне"
    assert _xml_lang_hint(unit, source=True) == "en"
    assert _xml_lang_hint(unit, source=False) == "be"
    assert _xml_lang_hint(ET.fromstring("<unit/>"), source=False) == ""


def test_mo_text_helpers_filter_invalid_tuple_values() -> None:
    """Verify mo text helper logic handles tuple and non-string inputs."""
    assert _mo_source_text(()) == ""
    assert _mo_source_text(("ctx\x04message\x00plural", "ignored")) == "message"
    assert _mo_source_text(123) == ""

    assert _mo_target_text(("", "   ", "Translation")) == "Translation"
    assert _mo_target_text(("", "   ")) == ""
    assert _mo_target_text(object()) == ""


def test_parse_po_quoted_handles_invalid_literals() -> None:
    """Verify po quoted parser handles syntax errors and non-string literals."""
    assert _parse_po_quoted("") == ""
    assert _parse_po_quoted('"value"') == "value"
    assert _parse_po_quoted('"\\xZZ"') == "\\xZZ"
    assert _parse_po_quoted('"unterminated') == '"unterminated'
    assert _parse_po_quoted("123") == "123"


def test_iter_tm_pairs_po_parses_plural_and_invalid_msgstr_indexes(
    tmp_path: Path,
) -> None:
    """Verify po parser handles plural rows and invalid plural indexes safely."""
    path = tmp_path / "plural.po"
    path.write_text(
        (
            "# translator comment\n"
            'msgid ""\n'
            'msgstr ""\n'
            '"Language: be\\n"\n'
            '"X-Source-Language: en\\n"\n'
            "\n"
            'msgid "Car"\n'
            'msgid_plural "Cars"\n'
            'msgstr[bad] "Аўто"\n'
            'msgstr[1] "Аўтамабілі"\n'
            "\n"
        ),
        encoding="utf-8",
    )

    assert list(iter_tm_pairs(path, "en", "be")) == [("CarCars", "Аўто")]


def test_iter_tm_pairs_xlsx_without_headers_uses_row_positions(tmp_path: Path) -> None:
    """Verify xlsx import supports no-header rows with implicit columns."""
    path = tmp_path / "no_header.xlsx"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                "<sheetData>"
                '<row r="1"><c t="inlineStr"><is><t>Hello</t></is></c>'
                '<c t="inlineStr"><is><t>Прывітанне</t></is></c></row>'
                '<row r="2"><c t="inlineStr"><is><t>Drop all</t></is></c>'
                '<c t="inlineStr"><is><t>Скінуць усё</t></is></c></row>'
                "</sheetData></worksheet>"
            ),
        )

    assert list(iter_tm_pairs(path, "en", "be")) == [
        ("Hello", "Прывітанне"),
        ("Drop all", "Скінуць усё"),
    ]
