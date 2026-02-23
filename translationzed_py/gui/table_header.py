"""Table-header click dispatch for source-reference and status controls."""

from __future__ import annotations

from typing import Any

from .source_reference_header import handle_header_click as _source_header_click
from .status_header import handle_header_click as _status_header_click


def handle_header_click(win: Any, logical_index: int) -> None:
    """Dispatch header clicks to column-specific handlers."""
    _source_header_click(win, logical_index)
    _status_header_click(win, logical_index)
