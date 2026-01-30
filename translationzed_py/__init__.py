"""TranslationZed – all public symbols are re-exported from .core."""

from importlib import metadata

from .core import (  # noqa: F401 – re-exports
    Entry,
    ParsedFile,
    Status,
    parse,
    scan_root,
)
from .version import __version__ as _fallback_version

try:
    __version__ = metadata.version(__name__)
except metadata.PackageNotFoundError:
    # Bundled apps (and editable installs) may not ship dist-info metadata.
    __version__ = _fallback_version
