"""Tests for table-header click dispatch helper."""

from __future__ import annotations

from types import SimpleNamespace

from translationzed_py.gui.table_header import handle_header_click


def test_table_header_dispatches_source_and_status(monkeypatch) -> None:
    """Verify table-header dispatcher calls source and status handlers."""
    calls: list[tuple[str, int]] = []

    monkeypatch.setattr(
        "translationzed_py.gui.table_header._source_header_click",
        lambda _win, logical_index: calls.append(("source", logical_index)),
    )
    monkeypatch.setattr(
        "translationzed_py.gui.table_header._status_header_click",
        lambda _win, logical_index: calls.append(("status", logical_index)),
    )

    handle_header_click(SimpleNamespace(), 3)
    assert calls == [("source", 3), ("status", 3)]
