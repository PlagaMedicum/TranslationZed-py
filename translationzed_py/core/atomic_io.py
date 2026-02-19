"""Atomic filesystem write helpers for cache/config persistence."""

from __future__ import annotations

import contextlib
import os
from pathlib import Path


def write_bytes_atomic(path: Path, data: bytes) -> None:
    """Write bytes with atomic replace and best-effort fsync."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(tmp, "wb") as handle:
            handle.write(data)
            handle.flush()
            with contextlib.suppress(OSError):
                os.fsync(handle.fileno())
        os.replace(tmp, path)
        _fsync_dir(path.parent)
    except Exception:
        with contextlib.suppress(OSError):
            tmp.unlink()
        raise


def write_text_atomic(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    """Write text data atomically using the selected encoding."""
    write_bytes_atomic(path, text.encode(encoding))


def _fsync_dir(path: Path) -> None:
    try:
        flags = getattr(os, "O_DIRECTORY", 0)
        fd = os.open(path, flags)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)
