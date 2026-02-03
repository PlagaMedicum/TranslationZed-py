from __future__ import annotations

import codecs


def _unescape(raw: str) -> str:
    """Unescape only escaped quotes/backslashes; keep other escapes literal."""
    if "\\" not in raw and '""' not in raw:
        return raw
    out: list[str] = []
    i = 0
    while i < len(raw):
        ch = raw[i]
        if ch == "\\" and i + 1 < len(raw):
            nxt = raw[i + 1]
            if nxt in {'"', "\\"}:
                out.append(nxt)
                i += 2
                continue
        if ch == '"' and i + 1 < len(raw) and raw[i + 1] == '"':
            out.append('"')
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _resolve_encoding(encoding: str, raw: bytes) -> tuple[str, int]:
    enc = encoding.lower().replace("_", "-")
    if enc in {"utf-8", "utf8"} and raw.startswith(codecs.BOM_UTF8):
        return "utf-8", 3
    if enc in {"utf-16", "utf16"} and raw.startswith(b"\xff\xfe"):
        return "utf-16-le", 2
    if enc in {"utf-16", "utf16"} and raw.startswith(b"\xfe\xff"):
        return "utf-16-be", 2
    if enc in {"utf-16", "utf16"}:
        if not raw:
            return "utf-16-le", 0
        even_zeros = sum(1 for i in range(0, len(raw), 2) if raw[i] == 0)
        odd_zeros = sum(1 for i in range(1, len(raw), 2) if raw[i] == 0)
        if odd_zeros > even_zeros:
            return "utf-16-le", 0
        if even_zeros > odd_zeros:
            return "utf-16-be", 0
        return "utf-16-le", 0
    return encoding, 0


def _decode_text(data: bytes, encoding: str) -> str:
    text = data.decode(encoding, errors="replace")
    if text.startswith("\ufeff"):
        return text[1:]
    return text
