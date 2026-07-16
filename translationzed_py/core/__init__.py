"""Backend-core public surface – re-export runtime API."""

from __future__ import annotations

from .model import Entry, ParsedFile, Status
from .parser import parse, parse_lazy
from .project_scanner import (
    LocaleMeta,
    list_translatable_files,
    scan_root,
    scan_root_with_errors,
)
from .search import Match, SearchField, SearchRow, search
from .translation_format import is_supported_translation

__all__ = [
    "scan_root",
    "scan_root_with_errors",
    "list_translatable_files",
    "parse",
    "parse_lazy",
    "LocaleMeta",
    "Entry",
    "Status",
    "ParsedFile",
    "SearchField",
    "SearchRow",
    "Match",
    "search",
    "is_supported_translation",
]
