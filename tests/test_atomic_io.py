"""Test module for atomic io."""

from __future__ import annotations

from pathlib import Path

import pytest

from translationzed_py.core.atomic_io import (
    _fsync_dir,
    write_bytes_atomic,
    write_text_atomic,
)


def test_atomic_io_write_bytes_and_text_round_trip(tmp_path: Path) -> None:
    """Verify atomic write helpers persist bytes and text payloads."""
    bytes_path = tmp_path / "bytes.bin"
    text_path = tmp_path / "text.txt"

    write_bytes_atomic(bytes_path, b"\x00\x01payload")
    write_text_atomic(text_path, "hello")

    assert bytes_path.read_bytes() == b"\x00\x01payload"
    assert text_path.read_text(encoding="utf-8") == "hello"


def test_fsync_dir_returns_when_open_fails(tmp_path: Path, monkeypatch) -> None:
    """Verify fsync dir exits cleanly when directory open raises OSError."""
    monkeypatch.setattr(
        "translationzed_py.core.atomic_io.os.open",
        lambda *_a, **_k: (_ for _ in ()).throw(OSError("no open")),
    )
    _fsync_dir(tmp_path)


def test_fsync_dir_swallows_fsync_errors_and_closes_fd(
    tmp_path: Path, monkeypatch
) -> None:
    """Verify fsync dir suppresses fsync errors while still closing descriptors."""
    closed: list[int] = []

    monkeypatch.setattr(
        "translationzed_py.core.atomic_io.os.open", lambda *_a, **_k: 123
    )
    monkeypatch.setattr(
        "translationzed_py.core.atomic_io.os.fsync",
        lambda _fd: (_ for _ in ()).throw(OSError("no fsync")),
    )
    monkeypatch.setattr(
        "translationzed_py.core.atomic_io.os.close",
        lambda fd: closed.append(fd),
    )

    _fsync_dir(tmp_path)

    assert closed == [123]


def test_write_bytes_atomic_tolerates_fsync_failures(
    tmp_path: Path, monkeypatch
) -> None:
    """Verify atomic writer still persists data when fsync raises OSError."""
    target = tmp_path / "fsync.bin"
    monkeypatch.setattr(
        "translationzed_py.core.atomic_io.os.fsync",
        lambda _fd: (_ for _ in ()).throw(OSError("no fsync")),
    )

    write_bytes_atomic(target, b"payload")

    assert target.read_bytes() == b"payload"


def test_write_bytes_atomic_cleans_temp_file_on_replace_failure(
    tmp_path: Path, monkeypatch
) -> None:
    """Verify replace failure removes temporary file before re-raising error."""
    target = tmp_path / "replace-fail.bin"
    tmp = target.with_name(target.name + ".tmp")
    monkeypatch.setattr(
        "translationzed_py.core.atomic_io.os.replace",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("replace failed")),
    )

    with pytest.raises(OSError, match="replace failed"):
        write_bytes_atomic(target, b"payload")

    assert tmp.exists() is False
    assert target.exists() is False
