"""Test module for tmx io internals."""

import struct
import zipfile
from pathlib import Path

import pytest
from defusedxml import ElementTree as ET

from translationzed_py.core.tmx_io import (
    _csv_value,
    _first_xlsx_sheet_path,
    _locale_matches,
    _mo_source_text,
    _mo_target_text,
    _parse_po_quoted,
    _read_xlsx_shared_strings,
    _resolve_csv_column_indexes,
    _seg_text,
    _xlsx_cell_text,
    _xlsx_col_from_ref,
    _xml_lang_hint,
    _xml_source_target_children,
    detect_tm_languages,
    detect_tmx_languages,
    iter_tm_pairs,
    write_tmx,
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


def test_iter_tmx_pairs_handles_empty_locale_and_sparse_nodes(tmp_path: Path) -> None:
    """Verify TMX parsing tolerates missing locales, seg nodes, and non-tuv tags."""
    path = tmp_path / "sparse.tmx"
    path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<tmx version="1.4">
  <header creationtool="test" creationtoolversion="1"
          datatype="PlainText" segtype="sentence" srclang="EN" />
  <body>
    <tu>
      <note>ignore me</note>
      <tuv><seg>No locale</seg></tuv>
      <tuv xml:lang="EN"><note /></tuv>
      <tuv xml:lang="BE"><seg>Тэкст</seg></tuv>
    </tu>
  </body>
</tmx>
""",
        encoding="utf-8",
    )

    assert list(iter_tm_pairs(path, "", "BE")) == []
    assert list(iter_tm_pairs(path, "EN", "BE")) == []


def test_write_tmx_skips_pairs_with_missing_side(tmp_path: Path) -> None:
    """Verify TMX writer skips pairs when source or target text is blank."""
    path = tmp_path / "written.tmx"
    write_tmx(
        path,
        [("Keep", "Пакінуць"), ("", "Drop"), ("Drop", "")],
        source_locale="EN",
        target_locale="BE",
    )

    assert list(iter_tm_pairs(path, "EN", "BE")) == [("Keep", "Пакінуць")]
    assert path.read_text(encoding="utf-8").count("<tu>") == 1


def test_detect_tmx_languages_respects_limit(tmp_path: Path) -> None:
    """Verify TMX language detection stops once the scan limit is reached."""
    path = tmp_path / "langs.tmx"
    path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<tmx version="1.4">
  <body>
    <tu>
      <tuv xml:lang="EN"><seg>Hello</seg></tuv>
      <tuv xml:lang="BE"><seg>Прывітанне</seg></tuv>
    </tu>
  </body>
</tmx>
""",
        encoding="utf-8",
    )

    assert detect_tmx_languages(path, limit=0) == {"EN"}


def test_xliff_and_mo_language_detection_handle_edge_cases(tmp_path: Path) -> None:
    """Verify XLIFF and MO language detection handles limit and malformed headers."""
    xliff = tmp_path / "sample.xliff"
    xliff.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2">
  <file source-language="en-US" target-language="be-BY">
    <body>
      <trans-unit id="1">
        <source>Hello</source>
        <target>Прывітанне</target>
      </trans-unit>
    </body>
  </file>
</xliff>
""",
        encoding="utf-8",
    )
    assert list(iter_tm_pairs(xliff, "", "BE")) == []
    assert detect_tm_languages(xliff, limit=0) == set()
    assert "en-US" in detect_tm_languages(xliff, limit=10)

    mo = tmp_path / "malformed.mo"
    _write_mo(
        mo,
        {
            "": "NoColonLine\nLanguage:\nX-Source-Language:   \n",
            "A": "B",
        },
    )
    assert detect_tm_languages(mo) == set()


def test_xml_csv_and_xlsx_detection_cover_empty_and_limit_paths(tmp_path: Path) -> None:
    """Verify XML/CSV/XLSX detection handles empty, no-header, and limited scans."""
    xml_path = tmp_path / "sample.xml"
    xml_path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<root>
  <unit xml:lang="EN" />
  <unit source-language="BE" />
</root>
""",
        encoding="utf-8",
    )
    assert detect_tm_languages(xml_path, limit=2) == {"EN"}

    csv_empty = tmp_path / "empty.csv"
    csv_empty.write_text("", encoding="utf-8")
    assert list(iter_tm_pairs(csv_empty, "EN", "BE")) == []
    assert detect_tm_languages(csv_empty) == set()

    csv_no_locale = tmp_path / "no_locale.csv"
    csv_no_locale.write_text("source,target\nHello,Прывітанне\n", encoding="utf-8")
    assert detect_tm_languages(csv_no_locale) == set()

    csv_locale = tmp_path / "locale.csv"
    csv_locale.write_text(
        "source_locale,target_locale,source,target\n"
        "en,be,Hello,Прывітанне\n"
        "ru,be,Hi,Вітаю\n",
        encoding="utf-8",
    )
    assert detect_tm_languages(csv_locale, limit=1)

    xlsx_empty = tmp_path / "empty.xlsx"
    with zipfile.ZipFile(xlsx_empty, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("xl/worksheets/sheet1.xml", "<worksheet/>")
    assert list(iter_tm_pairs(xlsx_empty, "EN", "BE")) == []

    xlsx_no_locale = tmp_path / "no_locale.xlsx"
    with zipfile.ZipFile(
        xlsx_no_locale, "w", compression=zipfile.ZIP_DEFLATED
    ) as archive:
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                "<sheetData>"
                '<row r="1"><c t="inlineStr"><is><t>source</t></is></c>'
                '<c t="inlineStr"><is><t>target</t></is></c></row>'
                '<row r="2"><ignored/></row>'
                "</sheetData></worksheet>"
            ),
        )
    assert detect_tm_languages(xlsx_no_locale) == set()

    xlsx_locale = tmp_path / "locale.xlsx"
    with zipfile.ZipFile(xlsx_locale, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                "<sheetData>"
                '<row r="1"><c t="inlineStr"><is><t>source_locale</t></is></c>'
                '<c t="inlineStr"><is><t>target_locale</t></is></c></row>'
                '<row r="2"><c t="inlineStr"><is><t>en</t></is></c>'
                '<c t="inlineStr"><is><t>be</t></is></c></row>'
                '<row r="3"><c t="inlineStr"><is><t>ru</t></is></c>'
                '<c t="inlineStr"><is><t>be</t></is></c></row>'
                "</sheetData></worksheet>"
            ),
        )
    assert detect_tm_languages(xlsx_locale, limit=1)


def test_csv_helpers_cover_empty_duplicate_and_out_of_range_cases() -> None:
    """Verify CSV helper internals handle empty rows and invalid indexes."""
    assert _resolve_csv_column_indexes([]) == (0, 1, False)
    assert _resolve_csv_column_indexes(["source", "source"]) == (0, 1, True)
    assert _csv_value(["a"], 2) == ""


def test_parse_po_handles_orphan_quotes_and_plural_fallback(tmp_path: Path) -> None:
    """Verify PO parser tolerates orphan quoted lines and plural-only translations."""
    path = tmp_path / "po_edge.po"
    path.write_text(
        (
            '"orphan line"\n'
            'msgid ""\n'
            'msgstr ""\n'
            '"Language:\\n"\n'
            '"NoColonLine\\n"\n'
            "\n"
            'msgid "Boat"\n'
            '"man"\n'
            'msgstr[1] "Лодка"\n'
            "\n"
        ),
        encoding="utf-8",
    )

    assert list(iter_tm_pairs(path, "EN", "BE")) == [("Boatman", "Лодка")]


def _write_mo(path: Path, entries: dict[str, str]) -> None:
    items = sorted(entries.items(), key=lambda item: item[0])
    ids = b""
    strings = b""
    id_offsets: list[tuple[int, int]] = []
    str_offsets: list[tuple[int, int]] = []
    original_base = 28 + len(items) * 16
    for source, _target in items:
        raw = source.encode("utf-8")
        id_offsets.append((len(raw), original_base + len(ids)))
        ids += raw + b"\x00"
    translation_base = original_base + len(ids)
    for _source, target in items:
        raw = target.encode("utf-8")
        str_offsets.append((len(raw), translation_base + len(strings)))
        strings += raw + b"\x00"
    with path.open("wb") as handle:
        handle.write(
            struct.pack("<7I", 0x950412DE, 0, len(items), 28, 28 + len(items) * 8, 0, 0)
        )
        for length, offset in id_offsets:
            handle.write(struct.pack("<2I", length, offset))
        for length, offset in str_offsets:
            handle.write(struct.pack("<2I", length, offset))
        handle.write(ids)
        handle.write(strings)
