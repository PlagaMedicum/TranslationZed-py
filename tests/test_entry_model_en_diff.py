"""Coverage for EN diff metadata and status triage row mapping in TranslationModel."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt

from translationzed_py.core.model import Entry, ParsedFile, Status
from translationzed_py.gui.entry_model import (
    DIFF_MARKER_ROLE,
    TranslationModel,
    VirtualNewRow,
)


def _entry(key: str, value: str, *, status: Status) -> Entry:
    return Entry(
        key=key,
        value=value,
        status=status,
        span=(0, 0),
        segments=(),
        gaps=(),
        raw=False,
        key_hash=None,
    )


def _parsed(entries: list[Entry]) -> ParsedFile:
    return ParsedFile(Path("/tmp/project/BE/ui.txt"), entries, b"")


def test_virtual_new_rows_render_in_en_order_and_are_editable() -> None:
    """Verify virtual NEW rows keep EN order and allow editing in value column."""
    model = TranslationModel(
        _parsed([_entry("A", "va", status=Status.PROOFREAD)]),
        source_values={"A": "sa"},
        diff_marker_by_key={"A": "MODIFIED", "B": "NEW"},
        virtual_new_rows=[VirtualNewRow(key="B", source="sb", value="")],
        en_order_keys=("A", "B"),
    )

    assert model.rowCount() == 2
    assert model.data(model.index(0, 0), Qt.DisplayRole) == "A"
    assert model.data(model.index(1, 0), Qt.DisplayRole) == "B"
    assert model.data(model.index(0, 0), DIFF_MARKER_ROLE) == "MODIFIED"
    assert model.data(model.index(1, 0), DIFF_MARKER_ROLE) == "NEW"
    assert model.flags(model.index(1, 2)) & Qt.ItemIsEditable
    assert not (model.flags(model.index(1, 3)) & Qt.ItemIsEditable)

    assert model.setData(model.index(1, 2), "draft", Qt.EditRole) is True
    assert model.has_pending_virtual_new_values() is True
    assert model.edited_virtual_new_values() == {"B": "draft"}


def test_status_filter_and_sort_apply_to_row_mapping() -> None:
    """Verify status sort/filter remaps visible model rows deterministically."""
    model = TranslationModel(
        _parsed(
            [
                _entry("A", "a", status=Status.PROOFREAD),
                _entry("B", "b", status=Status.UNTOUCHED),
                _entry("C", "c", status=Status.FOR_REVIEW),
            ]
        ),
        source_values={"A": "sa", "B": "sb", "C": "sc"},
    )

    assert [
        model.data(model.index(i, 0), Qt.EditRole) for i in range(model.rowCount())
    ] == [
        "A",
        "B",
        "C",
    ]

    model.set_status_sort_enabled(True)
    assert [
        model.data(model.index(i, 0), Qt.EditRole) for i in range(model.rowCount())
    ] == [
        "B",
        "C",
        "A",
    ]

    model.set_status_filter({Status.UNTOUCHED, Status.FOR_REVIEW})
    assert model.rowCount() == 2
    assert [
        model.data(model.index(i, 0), Qt.EditRole) for i in range(model.rowCount())
    ] == [
        "B",
        "C",
    ]

    model.set_status_filter(None)
    assert model.rowCount() == 3


def test_diff_marker_tooltips_use_source_locale_neutral_text() -> None:
    """Verify diff marker tooltips are source-locale wording, not EN-specific."""
    model = TranslationModel(
        _parsed(
            [
                _entry("A", "va", status=Status.PROOFREAD),
                _entry("B", "vb", status=Status.UNTOUCHED),
                _entry("C", "vc", status=Status.TRANSLATED),
            ]
        ),
        source_values={"A": "sa", "B": "sb", "C": "sc"},
        diff_marker_by_key={"A": "NEW", "B": "REMOVED", "C": "MODIFIED"},
    )

    tooltip_new = str(model.data(model.index(0, 0), Qt.ToolTipRole))
    tooltip_removed = str(model.data(model.index(1, 0), Qt.ToolTipRole))
    tooltip_modified = str(model.data(model.index(2, 0), Qt.ToolTipRole))

    assert "source locale" in tooltip_new.lower()
    assert "source locale" in tooltip_removed.lower()
    assert "source locale" in tooltip_modified.lower()
    assert " in en " not in tooltip_new.lower()
    assert " in en " not in tooltip_removed.lower()
    assert "en source changed" not in tooltip_modified.lower()
