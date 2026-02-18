"""Preview highlighting helpers for translation memory suggestions."""

from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QPlainTextEdit, QTextEdit

_MAX_TERMS = 24
_MAX_TERM_LEN = 80
_MAX_HITS = 200
_MAX_TEXT_LEN = 160_000


def prepare_tm_preview_terms(terms: Iterable[str]) -> list[str]:
    """Normalize and limit highlight terms for TM preview rendering."""
    cleaned: list[str] = []
    for term in terms:
        value = str(term).strip()
        if len(value) < 2 or len(value) > _MAX_TERM_LEN:
            continue
        if value in cleaned:
            continue
        cleaned.append(value)
        if len(cleaned) >= _MAX_TERMS:
            break
    return cleaned


def apply_tm_preview_highlights(editor: QPlainTextEdit, terms: Iterable[str]) -> None:
    """Apply bounded highlight selections for TM preview terms."""
    cleaned = prepare_tm_preview_terms(terms)
    if not cleaned:
        editor.setExtraSelections([])
        return
    doc = editor.document()
    text = doc.toPlainText()
    if len(text) > _MAX_TEXT_LEN:
        editor.setExtraSelections([])
        return
    lower = text.lower()
    fmt = QTextCharFormat()
    fmt.setBackground(QColor(255, 235, 120, 170))
    fmt.setForeground(QColor(0, 0, 0))
    selections: list[QTextEdit.ExtraSelection] = []
    for term in cleaned:
        query = term.lower()
        pos = 0
        while True:
            start = lower.find(query, pos)
            if start < 0:
                break
            end = start + len(query)
            cursor = QTextCursor(doc)
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.KeepAnchor)
            sel = QTextEdit.ExtraSelection()
            sel.cursor = cursor
            sel.format = fmt
            selections.append(sel)
            if len(selections) >= _MAX_HITS:
                editor.setExtraSelections(selections)
                return
            pos = end if end > pos else pos + 1
    editor.setExtraSelections(selections)
