"""Backend-core public surface – re-export runtime API."""

from __future__ import annotations

from .model import Entry, ParsedFile, Status
from .parser import parse
from .project_scanner import (
    LocaleMeta,
    list_translatable_files,
    scan_root,
    scan_root_with_errors,
)
from .search import Match, SearchField, SearchRow, search

__all__ = [
    "scan_root",
    "scan_root_with_errors",
    "list_translatable_files",
    "parse",
    "LocaleMeta",
    "Entry",
    "Status",
    "ParsedFile",
    "SearchField",
    "SearchRow",
    "Match",
    "search",
]
