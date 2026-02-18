"""Tmx io module."""

from __future__ import annotations

import ast
import csv
import gettext
import zipfile
from collections.abc import Iterable, Iterator
from pathlib import Path
from xml.sax.saxutils import escape

from defusedxml import ElementTree as ET  # type: ignore[import-untyped]

_XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
_XML_REL_ID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
_SUPPORTED_TM_IMPORT_SUFFIXES = (
    ".tmx",
    ".xliff",
    ".xlf",
    ".po",
    ".pot",
    ".csv",
    ".mo",
    ".xml",
    ".xlsx",
)
_CSV_SOURCE_HEADERS = frozenset(
    {
        "source",
        "src",
        "original",
        "source_text",
        "source text",
        "en",
    }
)
_CSV_TARGET_HEADERS = frozenset(
    {
        "target",
        "trg",
        "translation",
        "translated",
        "target_text",
        "target text",
    }
)
_CSV_SOURCE_LOCALE_HEADERS = frozenset(
    {"source_locale", "source_lang", "src_locale", "src_lang"}
)
_CSV_TARGET_LOCALE_HEADERS = frozenset(
    {"target_locale", "target_lang", "trg_locale", "trg_lang"}
)


def _lang_value(elem: ET.Element) -> str:
    """Execute lang value."""
    return elem.attrib.get(_XML_LANG) or elem.attrib.get("xml:lang") or ""


def _local_name(tag: str) -> str:
    """Execute local name."""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _seg_text(elem: ET.Element | None) -> str:
    """Execute seg text."""
    if elem is None:
        return ""
    return "".join(elem.itertext())


def _normalize_locale_tag(value: str) -> str:
    """Normalize locale tag."""
    return value.strip().lower().replace("_", "-")


def _locale_base(value: str) -> str:
    """Execute locale base."""
    return value.split("-", 1)[0] if value else ""


def _locale_matches(raw: str, normalized: str, base: str) -> bool:
    """Execute locale matches."""
    value = _normalize_locale_tag(raw)
    if not value:
        return False
    return value == normalized or _locale_base(value) == base


def supported_tm_import_suffixes() -> tuple[str, ...]:
    """Execute supported tm import suffixes."""
    return _SUPPORTED_TM_IMPORT_SUFFIXES


def iter_tm_pairs(
    path: Path,
    source_locale: str,
    target_locale: str,
) -> Iterator[tuple[str, str]]:
    """Execute iter tm pairs."""
    suffix = path.suffix.lower()
    if suffix == ".tmx":
        yield from iter_tmx_pairs(path, source_locale, target_locale)
        return
    if suffix in {".xliff", ".xlf"}:
        yield from iter_xliff_pairs(path, source_locale, target_locale)
        return
    if suffix in {".po", ".pot"}:
        yield from iter_po_pairs(path, source_locale, target_locale)
        return
    if suffix == ".csv":
        yield from iter_csv_pairs(path, source_locale, target_locale)
        return
    if suffix == ".mo":
        yield from iter_mo_pairs(path, source_locale, target_locale)
        return
    if suffix == ".xml":
        yield from iter_xml_pairs(path, source_locale, target_locale)
        return
    if suffix == ".xlsx":
        yield from iter_xlsx_pairs(path, source_locale, target_locale)
        return
    raise ValueError(f"Unsupported TM import format: {path.suffix or '<none>'}")


def iter_tmx_pairs(
    path: Path, source_locale: str, target_locale: str
) -> Iterator[tuple[str, str]]:
    """Execute iter tmx pairs."""
    source_locale = _normalize_locale_tag(source_locale)
    target_locale = _normalize_locale_tag(target_locale)
    if not source_locale or not target_locale:
        return
    source_base = _locale_base(source_locale)
    target_base = _locale_base(target_locale)
    for _event, elem in ET.iterparse(path, events=("end",)):
        if _local_name(elem.tag) != "tu":
            continue
        source_text = ""
        target_text = ""
        for tuv in elem:
            if _local_name(tuv.tag) != "tuv":
                continue
            lang = _normalize_locale_tag(_lang_value(tuv))
            if not lang:
                continue
            lang_base = _locale_base(lang)
            seg = None
            for child in tuv:
                if _local_name(child.tag) == "seg":
                    seg = child
                    break
            text = _seg_text(seg)
            if lang == source_locale or lang_base == source_base:
                source_text = text
            elif lang == target_locale or lang_base == target_base:
                target_text = text
        if source_text and target_text:
            yield source_text, target_text
        elem.clear()


def write_tmx(
    path: Path,
    pairs: Iterable[tuple[str, str]],
    *,
    source_locale: str,
    target_locale: str,
) -> None:
    """Write tmx."""
    source_locale = source_locale.strip()
    target_locale = target_locale.strip()
    with path.open("w", encoding="utf-8") as handle:
        handle.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        handle.write('<tmx version="1.4">\n')
        handle.write(
            '  <header creationtool="TranslationZed-Py" '
            'creationtoolversion="0.2" datatype="PlainText" segtype="sentence" '
            f'srclang="{escape(source_locale)}" />\n'
        )
        handle.write("  <body>\n")
        for source_text, target_text in pairs:
            if not (source_text and target_text):
                continue
            handle.write("    <tu>\n")
            handle.write(
                f'      <tuv xml:lang="{escape(source_locale)}"><seg>'
                f"{escape(source_text)}</seg></tuv>\n"
            )
            handle.write(
                f'      <tuv xml:lang="{escape(target_locale)}"><seg>'
                f"{escape(target_text)}</seg></tuv>\n"
            )
            handle.write("    </tu>\n")
        handle.write("  </body>\n</tmx>\n")


def detect_tm_languages(path: Path, *, limit: int = 2000) -> set[str]:
    """Execute detect tm languages."""
    suffix = path.suffix.lower()
    if suffix == ".tmx":
        return detect_tmx_languages(path, limit=limit)
    if suffix in {".xliff", ".xlf"}:
        return detect_xliff_languages(path, limit=limit)
    if suffix in {".po", ".pot"}:
        return detect_po_languages(path)
    if suffix == ".csv":
        return detect_csv_languages(path, limit=limit)
    if suffix == ".mo":
        return detect_mo_languages(path)
    if suffix == ".xml":
        return detect_xml_languages(path, limit=limit)
    if suffix == ".xlsx":
        return detect_xlsx_languages(path, limit=limit)
    return set()


def detect_tmx_languages(path: Path, *, limit: int = 2000) -> set[str]:
    """Execute detect tmx languages."""
    langs: set[str] = set()
    count = 0
    for _event, elem in ET.iterparse(path, events=("end",)):
        if _local_name(elem.tag) != "tuv":
            continue
        lang = _lang_value(elem).strip()
        if lang:
            langs.add(lang)
            if len(langs) >= 32 or count >= limit:
                break
        count += 1
        elem.clear()
    return langs


def iter_xliff_pairs(
    path: Path,
    source_locale: str,
    target_locale: str,
) -> Iterator[tuple[str, str]]:
    """Execute iter xliff pairs."""
    source_locale_norm = _normalize_locale_tag(source_locale)
    target_locale_norm = _normalize_locale_tag(target_locale)
    source_base = _locale_base(source_locale_norm)
    target_base = _locale_base(target_locale_norm)
    if not source_locale_norm or not target_locale_norm:
        return
    root_source_lang = ""
    root_target_lang = ""
    file_source_lang = ""
    file_target_lang = ""
    for event, elem in ET.iterparse(path, events=("start", "end")):
        name = _local_name(elem.tag)
        if event == "start":
            if name == "xliff":
                root_source_lang = (
                    elem.attrib.get("srcLang")
                    or elem.attrib.get("source-language")
                    or root_source_lang
                )
                root_target_lang = (
                    elem.attrib.get("trgLang")
                    or elem.attrib.get("target-language")
                    or root_target_lang
                )
            elif name == "file":
                file_source_lang = (
                    elem.attrib.get("source-language")
                    or elem.attrib.get("srcLang")
                    or root_source_lang
                )
                file_target_lang = (
                    elem.attrib.get("target-language")
                    or elem.attrib.get("trgLang")
                    or root_target_lang
                )
            continue
        if name == "file":
            file_source_lang = root_source_lang
            file_target_lang = root_target_lang
            elem.clear()
            continue
        if name in {"source", "target"}:
            continue
        if name not in {"trans-unit", "segment"}:
            elem.clear()
            continue
        source_elem = None
        target_elem = None
        for child in elem:
            child_name = _local_name(child.tag)
            if child_name == "source" and source_elem is None:
                source_elem = child
            elif child_name == "target" and target_elem is None:
                target_elem = child
        source_text = _seg_text(source_elem)
        target_text = _seg_text(target_elem)
        if source_text and target_text:
            source_lang = _lang_value(source_elem) if source_elem is not None else ""
            target_lang = _lang_value(target_elem) if target_elem is not None else ""
            source_lang = source_lang or file_source_lang or root_source_lang
            target_lang = target_lang or file_target_lang or root_target_lang
            source_ok = (
                True
                if not source_lang
                else _locale_matches(source_lang, source_locale_norm, source_base)
            )
            target_ok = (
                True
                if not target_lang
                else _locale_matches(target_lang, target_locale_norm, target_base)
            )
            if source_ok and target_ok:
                yield source_text, target_text
        elem.clear()


def detect_xliff_languages(path: Path, *, limit: int = 2000) -> set[str]:
    """Execute detect xliff languages."""
    langs: set[str] = set()
    count = 0

    def _add(value: str) -> None:
        """Execute add."""
        if value.strip():
            langs.add(value.strip())

    for event, elem in ET.iterparse(path, events=("start", "end")):
        name = _local_name(elem.tag)
        if event == "start":
            if name == "xliff":
                _add(elem.attrib.get("srcLang", ""))
                _add(elem.attrib.get("trgLang", ""))
                _add(elem.attrib.get("source-language", ""))
                _add(elem.attrib.get("target-language", ""))
            elif name == "file":
                _add(elem.attrib.get("source-language", ""))
                _add(elem.attrib.get("target-language", ""))
                _add(elem.attrib.get("srcLang", ""))
                _add(elem.attrib.get("trgLang", ""))
        else:
            if name in {"source", "target"}:
                _add(_lang_value(elem))
            count += 1
            elem.clear()
        if len(langs) >= 32 or count >= limit:
            break
    return langs


def iter_po_pairs(
    path: Path,
    source_locale: str,
    target_locale: str,
) -> Iterator[tuple[str, str]]:
    # Locale pair is resolved by import workflow; PO units carry msgid/msgstr pairs.
    """Execute iter po pairs."""
    _ = source_locale, target_locale
    pairs, _langs = _parse_po(path)
    yield from pairs


def detect_po_languages(path: Path) -> set[str]:
    """Execute detect po languages."""
    _pairs, langs = _parse_po(path)
    return langs


def iter_mo_pairs(
    path: Path,
    source_locale: str,
    target_locale: str,
) -> Iterator[tuple[str, str]]:
    # Locale pair is resolved by import workflow; MO units are msgid/msgstr catalog rows.
    """Execute iter mo pairs."""
    _ = source_locale, target_locale
    pairs_by_source: dict[str, str] = {}
    for raw_key, raw_value in _read_mo_catalog(path).items():
        source_text = _mo_source_text(raw_key)
        target_text = _mo_target_text(raw_value)
        if not source_text or not target_text:
            continue
        pairs_by_source.setdefault(source_text, target_text)
    yield from pairs_by_source.items()


def detect_mo_languages(path: Path) -> set[str]:
    """Execute detect mo languages."""
    langs: set[str] = set()
    metadata = _mo_target_text(_read_mo_catalog(path).get("", ""))
    if not metadata:
        return langs
    for raw_line in metadata.splitlines():
        if ":" not in raw_line:
            continue
        key_raw, value_raw = raw_line.split(":", 1)
        key = key_raw.strip().lower()
        value = value_raw.strip()
        if not value:
            continue
        if key in {
            "language",
            "source-language",
            "x-source-language",
            "target-language",
            "x-target-language",
        }:
            langs.add(value)
    return langs


def iter_xml_pairs(
    path: Path,
    source_locale: str,
    target_locale: str,
) -> Iterator[tuple[str, str]]:
    """Execute iter xml pairs."""
    source_locale_norm = _normalize_locale_tag(source_locale)
    target_locale_norm = _normalize_locale_tag(target_locale)
    source_base = _locale_base(source_locale_norm)
    target_base = _locale_base(target_locale_norm)
    seen: set[tuple[str, str]] = set()
    for _event, elem in ET.iterparse(path, events=("end",)):
        name = _local_name(elem.tag)
        if name in {"source", "target", "translation", "translated"}:
            continue
        if name not in {"tu", "trans-unit", "segment", "unit", "entry"}:
            elem.clear()
            continue
        source_elem, target_elem = _xml_source_target_children(elem)
        source_text = _seg_text(source_elem)
        target_text = _seg_text(target_elem)
        if source_text and target_text:
            source_lang = (
                _lang_value(source_elem) if source_elem is not None else ""
            ) or _xml_lang_hint(elem, source=True)
            target_lang = (
                _lang_value(target_elem) if target_elem is not None else ""
            ) or _xml_lang_hint(elem, source=False)
            source_ok = (
                True
                if not source_lang
                else _locale_matches(source_lang, source_locale_norm, source_base)
            )
            target_ok = (
                True
                if not target_lang
                else _locale_matches(target_lang, target_locale_norm, target_base)
            )
            pair = (source_text, target_text)
            if source_ok and target_ok and pair not in seen:
                seen.add(pair)
                yield pair
        elem.clear()


def detect_xml_languages(path: Path, *, limit: int = 2000) -> set[str]:
    """Execute detect xml languages."""
    langs: set[str] = set()
    for count, (_event, elem) in enumerate(
        ET.iterparse(path, events=("start",)), start=1
    ):
        lang = _lang_value(elem).strip()
        if lang:
            langs.add(lang)
        for key in (
            "source-language",
            "target-language",
            "srcLang",
            "trgLang",
            "source_locale",
            "target_locale",
            "source_lang",
            "target_lang",
        ):
            value = elem.attrib.get(key, "").strip()
            if value:
                langs.add(value)
        if len(langs) >= 32 or count >= limit:
            break
    return langs


def iter_xlsx_pairs(
    path: Path,
    source_locale: str,
    target_locale: str,
) -> Iterator[tuple[str, str]]:
    # Locale pair is resolved by import workflow; XLSX rows are source/target columns.
    """Execute iter xlsx pairs."""
    _ = source_locale, target_locale
    with zipfile.ZipFile(path) as archive:
        rows = _iter_xlsx_rows(archive)
        first = next(rows, None)
        if first is None:
            return
        source_idx, target_idx, has_header = _resolve_csv_column_indexes(first)
        if not has_header:
            source_text = _csv_value(first, source_idx)
            target_text = _csv_value(first, target_idx)
            if source_text and target_text:
                yield source_text, target_text
        for row in rows:
            source_text = _csv_value(row, source_idx)
            target_text = _csv_value(row, target_idx)
            if source_text and target_text:
                yield source_text, target_text


def detect_xlsx_languages(path: Path, *, limit: int = 2000) -> set[str]:
    """Execute detect xlsx languages."""
    langs: set[str] = set()
    with zipfile.ZipFile(path) as archive:
        rows = _iter_xlsx_rows(archive)
        header = next(rows, None)
        if header is None:
            return langs
        normalized = [_normalize_csv_header(cell) for cell in header]
        source_idx = _find_csv_header_index(normalized, _CSV_SOURCE_LOCALE_HEADERS)
        target_idx = _find_csv_header_index(normalized, _CSV_TARGET_LOCALE_HEADERS)
        if source_idx is None and target_idx is None:
            return langs
        for count, row in enumerate(rows, start=1):
            if source_idx is not None:
                source_locale = _csv_value(row, source_idx)
                if source_locale:
                    langs.add(source_locale)
            if target_idx is not None:
                target_locale = _csv_value(row, target_idx)
                if target_locale:
                    langs.add(target_locale)
            if len(langs) >= 32 or count >= limit:
                break
    return langs


def iter_csv_pairs(
    path: Path,
    source_locale: str,
    target_locale: str,
) -> Iterator[tuple[str, str]]:
    # Locale pair is resolved by import workflow; CSV units are source/target columns.
    """Execute iter csv pairs."""
    _ = source_locale, target_locale
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        reader = csv.reader(handle)
        first = next(reader, None)
        if first is None:
            return
        source_idx, target_idx, has_header = _resolve_csv_column_indexes(first)
        if not has_header:
            source_text = _csv_value(first, source_idx)
            target_text = _csv_value(first, target_idx)
            if source_text and target_text:
                yield source_text, target_text
        for row in reader:
            source_text = _csv_value(row, source_idx)
            target_text = _csv_value(row, target_idx)
            if source_text and target_text:
                yield source_text, target_text


def detect_csv_languages(path: Path, *, limit: int = 2000) -> set[str]:
    """Execute detect csv languages."""
    langs: set[str] = set()
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        if not header:
            return langs
        normalized = [_normalize_csv_header(cell) for cell in header]
        source_idx = _find_csv_header_index(normalized, _CSV_SOURCE_LOCALE_HEADERS)
        target_idx = _find_csv_header_index(normalized, _CSV_TARGET_LOCALE_HEADERS)
        if source_idx is None and target_idx is None:
            return langs
        for count, row in enumerate(reader, start=1):
            if source_idx is not None:
                source_locale = _csv_value(row, source_idx)
                if source_locale:
                    langs.add(source_locale)
            if target_idx is not None:
                target_locale = _csv_value(row, target_idx)
                if target_locale:
                    langs.add(target_locale)
            if len(langs) >= 32 or count >= limit:
                break
    return langs


def _resolve_csv_column_indexes(row: list[str]) -> tuple[int, int, bool]:
    """Resolve csv column indexes."""
    if not row:
        return 0, 1, False
    normalized = [_normalize_csv_header(cell) for cell in row]
    source_idx = _find_csv_header_index(normalized, _CSV_SOURCE_HEADERS)
    target_idx = _find_csv_header_index(normalized, _CSV_TARGET_HEADERS)
    has_header = source_idx is not None or target_idx is not None
    if source_idx is None:
        source_idx = 0
    if target_idx is None:
        target_idx = 1 if source_idx == 0 else 0
    if target_idx == source_idx and len(row) > 1:
        target_idx = 1 if source_idx == 0 else 0
    return source_idx, target_idx, has_header


def _normalize_csv_header(value: str) -> str:
    """Normalize csv header."""
    return value.strip().lower().replace("-", "_")


def _find_csv_header_index(row: list[str], labels: frozenset[str]) -> int | None:
    """Find csv header index."""
    for idx, value in enumerate(row):
        if value in labels:
            return idx
    return None


def _csv_value(row: list[str], idx: int) -> str:
    """Execute csv value."""
    if idx < 0 or idx >= len(row):
        return ""
    return row[idx].strip()


def _iter_xlsx_rows(archive: zipfile.ZipFile) -> Iterator[list[str]]:
    """Execute iter xlsx rows."""
    shared_strings = _read_xlsx_shared_strings(archive)
    sheet_path = _first_xlsx_sheet_path(archive)
    with archive.open(sheet_path) as handle:
        for _event, elem in ET.iterparse(handle, events=("end",)):
            if _local_name(elem.tag) != "row":
                continue
            row_map: dict[int, str] = {}
            fallback_idx = 0
            for cell in elem:
                if _local_name(cell.tag) != "c":
                    continue
                col_idx = _xlsx_col_from_ref(cell.attrib.get("r", ""))
                if col_idx < 0:
                    col_idx = fallback_idx
                fallback_idx = max(fallback_idx, col_idx + 1)
                row_map[col_idx] = _xlsx_cell_text(cell, shared_strings)
            if row_map:
                max_idx = max(row_map)
                yield [row_map.get(idx, "") for idx in range(max_idx + 1)]
            elem.clear()


def _read_xlsx_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    """Read xlsx shared strings."""
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    values: list[str] = []
    with archive.open("xl/sharedStrings.xml") as handle:
        for _event, elem in ET.iterparse(handle, events=("end",)):
            if _local_name(elem.tag) != "si":
                continue
            values.append(_seg_text(elem))
            elem.clear()
    return values


def _first_xlsx_sheet_path(archive: zipfile.ZipFile) -> str:
    """Execute first xlsx sheet path."""
    fallback = sorted(
        name
        for name in archive.namelist()
        if name.startswith("xl/worksheets/") and name.endswith(".xml")
    )
    if not fallback:
        raise ValueError("XLSX has no worksheet XML files")
    rels_path = "xl/_rels/workbook.xml.rels"
    workbook_path = "xl/workbook.xml"
    if rels_path not in archive.namelist() or workbook_path not in archive.namelist():
        return fallback[0]
    with archive.open(rels_path) as handle:
        rels_root = ET.parse(handle).getroot()
    rel_targets = {
        rel.attrib.get("Id", ""): rel.attrib.get("Target", "")
        for rel in rels_root
        if _local_name(rel.tag) == "Relationship"
    }
    with archive.open(workbook_path) as handle:
        workbook_root = ET.parse(handle).getroot()
    first_rel_id = ""
    for sheet in workbook_root.iter():
        if _local_name(sheet.tag) != "sheet":
            continue
        first_rel_id = sheet.attrib.get(_XML_REL_ID, "") or sheet.attrib.get("r:id", "")
        if first_rel_id:
            break
    target = rel_targets.get(first_rel_id, "").strip()
    if not target:
        return fallback[0]
    normalized = target.lstrip("/")
    if normalized.startswith("worksheets/") or not normalized.startswith("xl/"):
        normalized = f"xl/{normalized}"
    return normalized if normalized in archive.namelist() else fallback[0]


def _xlsx_col_from_ref(cell_ref: str) -> int:
    """Execute xlsx col from ref."""
    letters = ""
    for char in cell_ref.strip():
        if char.isalpha():
            letters += char.upper()
            continue
        break
    if not letters:
        return -1
    value = 0
    for char in letters:
        value = value * 26 + (ord(char) - 64)
    return value - 1


def _xlsx_cell_text(cell: ET.Element, shared_strings: list[str]) -> str:
    """Execute xlsx cell text."""
    cell_type = cell.attrib.get("t", "")
    if cell_type == "inlineStr":
        for child in cell:
            if _local_name(child.tag) == "is":
                return _seg_text(child).strip()
        return ""
    raw_value = ""
    for child in cell:
        child_name = _local_name(child.tag)
        if child_name == "v":
            raw_value = _seg_text(child).strip()
            break
        if child_name == "is":
            return _seg_text(child).strip()
    if cell_type == "s":
        try:
            index = int(raw_value)
        except ValueError:
            return ""
        if 0 <= index < len(shared_strings):
            return shared_strings[index].strip()
        return ""
    return raw_value


def _xml_source_target_children(
    elem: ET.Element,
) -> tuple[ET.Element | None, ET.Element | None]:
    """Execute xml source target children."""
    source_elem: ET.Element | None = None
    target_elem: ET.Element | None = None
    for child in elem:
        name = _local_name(child.tag)
        if source_elem is None and name == "source":
            source_elem = child
            continue
        if target_elem is None and name in {"target", "translation", "translated"}:
            target_elem = child
    return source_elem, target_elem


def _xml_lang_hint(elem: ET.Element, *, source: bool) -> str:
    """Execute xml lang hint."""
    key_candidates = (
        ("source-language", "srcLang", "source_locale", "source_lang")
        if source
        else ("target-language", "trgLang", "target_locale", "target_lang")
    )
    for key in key_candidates:
        value = str(elem.attrib.get(key, "")).strip()
        if value:
            return value
    return ""


def _read_mo_catalog(path: Path) -> dict[object, object]:
    """Read mo catalog."""
    with path.open("rb") as handle:
        catalog = getattr(gettext.GNUTranslations(handle), "_catalog", {})
    return catalog if isinstance(catalog, dict) else {}


def _mo_source_text(value: object) -> str:
    """Execute mo source text."""
    if isinstance(value, tuple):
        if not value:
            return ""
        value = value[0]
    if not isinstance(value, str):
        return ""
    text = value.split("\x04", 1)[-1]
    text = text.split("\x00", 1)[0]
    return text.strip()


def _mo_target_text(value: object) -> str:
    """Execute mo target text."""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, tuple):
        for item in value:
            if isinstance(item, str) and item.strip():
                return item.strip()
    return ""


def _parse_po(path: Path) -> tuple[list[tuple[str, str]], set[str]]:
    """Parse po."""
    pairs: list[tuple[str, str]] = []
    langs: set[str] = set()
    entry_msgid: list[str] = []
    entry_msgstr: dict[int, list[str]] = {}
    current_field: tuple[str, int] | None = None

    def _append_to_current(fragment: str) -> None:
        """Execute append to current."""
        nonlocal entry_msgid, entry_msgstr, current_field
        if current_field is None:
            return
        field, index = current_field
        if field == "msgid":
            entry_msgid.append(fragment)
            return
        entry_msgstr.setdefault(index, []).append(fragment)

    def _parse_header_languages(text: str) -> None:
        """Parse header languages."""
        nonlocal langs
        for raw in text.splitlines():
            if ":" not in raw:
                continue
            key_raw, value_raw = raw.split(":", 1)
            key = key_raw.strip().lower()
            value = value_raw.strip()
            if not value:
                continue
            if key in {"language", "source-language", "x-source-language"}:
                langs.add(value)

    def _finalize_entry() -> None:
        """Execute finalize entry."""
        nonlocal entry_msgid, entry_msgstr, current_field, pairs
        msgid = "".join(entry_msgid)
        msgstr = "".join(entry_msgstr.get(0, []))
        if not msgstr:
            for idx in sorted(entry_msgstr):
                candidate = "".join(entry_msgstr[idx])
                if candidate:
                    msgstr = candidate
                    break
        if msgid:
            if msgstr:
                pairs.append((msgid, msgstr))
        elif msgstr:
            _parse_header_languages(msgstr)
        entry_msgid = []
        entry_msgstr = {}
        current_field = None

    with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
        for raw_line in handle:
            line = raw_line.rstrip("\r\n")
            stripped = line.strip()
            if not stripped:
                _finalize_entry()
                continue
            if stripped.startswith("#"):
                continue
            if stripped.startswith("msgid "):
                current_field = ("msgid", 0)
                entry_msgid = [_parse_po_quoted(stripped[len("msgid ") :])]
                continue
            if stripped.startswith("msgid_plural "):
                # Keep plural source as part of msgid fallback stream.
                current_field = ("msgid", 0)
                entry_msgid.append(_parse_po_quoted(stripped[len("msgid_plural ") :]))
                continue
            if stripped.startswith("msgstr["):
                right = stripped.find("]")
                if right > len("msgstr["):
                    idx_raw = stripped[len("msgstr[") : right]
                    with_index = stripped[right + 1 :].strip()
                    try:
                        index = int(idx_raw)
                    except ValueError:
                        index = 0
                    current_field = ("msgstr", index)
                    entry_msgstr.setdefault(index, []).append(
                        _parse_po_quoted(with_index)
                    )
                    continue
            if stripped.startswith("msgstr "):
                current_field = ("msgstr", 0)
                entry_msgstr.setdefault(0, []).append(
                    _parse_po_quoted(stripped[len("msgstr ") :])
                )
                continue
            if stripped.startswith('"'):
                _append_to_current(_parse_po_quoted(stripped))
                continue
        _finalize_entry()
    return pairs, langs


def _parse_po_quoted(value: str) -> str:
    """Parse po quoted."""
    raw = value.strip()
    if not raw:
        return ""
    try:
        parsed = ast.literal_eval(raw)
    except (SyntaxError, ValueError):
        if raw.startswith('"') and raw.endswith('"'):
            return raw[1:-1]
        return raw
    if isinstance(parsed, str):
        return parsed
    return str(parsed)
