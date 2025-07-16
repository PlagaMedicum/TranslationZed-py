"""TranslationZed – all public symbols are re-exported from .core."""

from importlib import metadata

from .core import (  # noqa: F401 – re-exports
    Entry,
    ParsedFile,
    Status,
    parse,
    scan_root,
)

try:
    __version__ = metadata.version(__name__)
except metadata.PackageNotFoundError:  # editable install before first build
    __version__ = "0.0.0"
