from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

_XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"


def _lang_value(elem: ET.Element) -> str:
    return elem.attrib.get(_XML_LANG) or elem.attrib.get("xml:lang") or ""


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _seg_text(elem: ET.Element | None) -> str:
    if elem is None:
        return ""
    return "".join(elem.itertext())


def iter_tmx_pairs(
    path: Path, source_locale: str, target_locale: str
) -> Iterator[tuple[str, str]]:
    source_locale = source_locale.strip().lower()
    target_locale = target_locale.strip().lower()
    if not source_locale or not target_locale:
        return
    for _event, elem in ET.iterparse(path, events=("end",)):
        if _local_name(elem.tag) != "tu":
            continue
        source_text = ""
        target_text = ""
        for tuv in elem:
            if _local_name(tuv.tag) != "tuv":
                continue
            lang = _lang_value(tuv).lower()
            if not lang:
                continue
            seg = None
            for child in tuv:
                if _local_name(child.tag) == "seg":
                    seg = child
                    break
            text = _seg_text(seg)
            if lang == source_locale:
                source_text = text
            elif lang == target_locale:
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
