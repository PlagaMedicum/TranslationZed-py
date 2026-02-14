from __future__ import annotations

import ast
from collections.abc import Iterable, Iterator
from pathlib import Path
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

_XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
_SUPPORTED_TM_IMPORT_SUFFIXES = (".tmx", ".xliff", ".xlf", ".po", ".pot")


def _lang_value(elem: ET.Element) -> str:
    return elem.attrib.get(_XML_LANG) or elem.attrib.get("xml:lang") or ""


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _seg_text(elem: ET.Element | None) -> str:
    if elem is None:
        return ""
    return "".join(elem.itertext())


def _normalize_locale_tag(value: str) -> str:
    return value.strip().lower().replace("_", "-")


def _locale_base(value: str) -> str:
    return value.split("-", 1)[0] if value else ""


def _locale_matches(raw: str, normalized: str, base: str) -> bool:
    value = _normalize_locale_tag(raw)
    if not value:
        return False
    return value == normalized or _locale_base(value) == base


def supported_tm_import_suffixes() -> tuple[str, ...]:
    return _SUPPORTED_TM_IMPORT_SUFFIXES


def iter_tm_pairs(
    path: Path,
    source_locale: str,
    target_locale: str,
) -> Iterator[tuple[str, str]]:
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
    raise ValueError(f"Unsupported TM import format: {path.suffix or '<none>'}")


def iter_tmx_pairs(
    path: Path, source_locale: str, target_locale: str
) -> Iterator[tuple[str, str]]:
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
    suffix = path.suffix.lower()
    if suffix == ".tmx":
        return detect_tmx_languages(path, limit=limit)
    if suffix in {".xliff", ".xlf"}:
        return detect_xliff_languages(path, limit=limit)
    if suffix in {".po", ".pot"}:
        return detect_po_languages(path)
    return set()


def detect_tmx_languages(path: Path, *, limit: int = 2000) -> set[str]:
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
    langs: set[str] = set()
    count = 0

    def _add(value: str) -> None:
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
    _ = source_locale, target_locale
    pairs, _langs = _parse_po(path)
    yield from pairs


def detect_po_languages(path: Path) -> set[str]:
    _pairs, langs = _parse_po(path)
    return langs


def _parse_po(path: Path) -> tuple[list[tuple[str, str]], set[str]]:
    pairs: list[tuple[str, str]] = []
    langs: set[str] = set()
    entry_msgid: list[str] = []
    entry_msgstr: dict[int, list[str]] = {}
    current_field: tuple[str, int] | None = None

    def _append_to_current(fragment: str) -> None:
        nonlocal entry_msgid, entry_msgstr, current_field
        if current_field is None:
            return
        field, index = current_field
        if field == "msgid":
            entry_msgid.append(fragment)
            return
        entry_msgstr.setdefault(index, []).append(fragment)

    def _parse_header_languages(text: str) -> None:
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
