"""Backend-core public surface – re-export runtime API."""

from __future__ import annotations

from .model import Entry, ParsedFile, Status
from .parser import parse
from .project_scanner import scan_root

__all__ = [
    "scan_root",
    "parse",
    "Entry",
    "Status",
    "ParsedFile",
]
