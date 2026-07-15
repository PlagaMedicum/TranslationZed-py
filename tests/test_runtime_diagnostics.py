"""Tests for bounded runtime logging and copyable issue-report content."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest

from translationzed_py.core import runtime_diagnostics as diagnostics


@pytest.fixture(autouse=True)
def _reset_runtime_logger():  # type: ignore[no-untyped-def]
    yield
    logger = diagnostics.get_logger()
    for handler in tuple(logger.handlers):
        if not bool(getattr(handler, "_translationzed_py_owned", False)):
            continue
        logger.removeHandler(handler)
        handler.close()
    diagnostics._ACTIVE_LOG_PATH = None


def test_configure_logging_writes_debug_file_and_is_idempotent(tmp_path: Path) -> None:
    """Keep verbose diagnostics in one bounded file without duplicate handlers."""
    path = tmp_path / "logs" / "runtime.log"

    assert diagnostics.configure_logging(log_path=path) == path
    diagnostics.get_logger().debug("debug-only diagnostic")
    for handler in diagnostics.get_logger().handlers:
        handler.flush()

    assert "debug-only diagnostic" in path.read_text(encoding="utf-8")
    assert diagnostics.configure_logging(log_path=path) == path
    owned = [
        handler
        for handler in diagnostics.get_logger().handlers
        if bool(getattr(handler, "_translationzed_py_owned", False))
    ]
    assert len(owned) == 2


def test_configure_logging_falls_back_to_console_when_file_setup_fails(
    tmp_path: Path, monkeypatch
) -> None:
    """A log-file permission/setup failure must not prevent application startup."""

    def _raise(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise OSError("read-only log directory")

    monkeypatch.setattr(diagnostics.logging.handlers, "RotatingFileHandler", _raise)

    assert diagnostics.configure_logging(log_path=tmp_path / "runtime.log") is None
    assert diagnostics.current_log_path() is None
    assert any(
        isinstance(handler, logging.StreamHandler)
        for handler in diagnostics.get_logger().handlers
    )


def test_issue_report_redacts_private_paths_and_bounds_log_tail(tmp_path: Path) -> None:
    """Reports remain pasteable and bounded while retaining actionable diagnostics."""
    root = tmp_path / "private-project"
    root.mkdir()
    log_path = tmp_path / "runtime.log"
    log_path.write_text(
        "old\n" + ("x" * diagnostics.REPORT_LOG_TAIL_BYTES) + f"\nfailed: {root}\n",
        encoding="utf-8",
    )
    try:
        raise RuntimeError(f"could not open {root / 'target.txt'}")
    except RuntimeError:
        exc_info = sys.exc_info()

    report = diagnostics.build_issue_report(
        app_version="1.0-test",
        qt_version="6.test",
        binding_version="6.test",
        project_root=root,
        log_path=log_path,
        exc_info=exc_info,
    )

    assert "RuntimeError" in report
    assert "<PROJECT_ROOT>/target.txt" in report
    assert str(root) not in report
    assert "[earlier log content omitted]" in report
    assert "App version: 1.0-test" in report
    assert "issues/new" in report
    assert len(report) < 60_000


def test_issue_report_survives_unresolvable_project_path(
    tmp_path: Path, monkeypatch
) -> None:
    """Diagnostics remain available when path canonicalization itself fails."""
    root = tmp_path / "looped-project"

    def _fail_resolve(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("loop")

    monkeypatch.setattr(Path, "resolve", _fail_resolve)

    report = diagnostics.build_issue_report(
        app_version="test",
        qt_version="test",
        binding_version="test",
        project_root=root,
    )

    assert str(root) not in report
    assert "Project root: <PROJECT_ROOT>" in report
