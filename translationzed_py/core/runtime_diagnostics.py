"""Bounded runtime logging and privacy-aware issue-report formatting."""

from __future__ import annotations

import contextlib
import logging
import logging.handlers
import platform
import sys
import tempfile
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from types import TracebackType

LOGGER_NAME = "translationzed_py"
LOG_FILENAME = "translationzed-py.log"
LOG_MAX_BYTES = 1_000_000
LOG_BACKUP_COUNT = 3
REPORT_LOG_TAIL_BYTES = 32 * 1024
REPORT_TRACEBACK_CHARS = 16 * 1024

_ACTIVE_LOG_PATH: Path | None = None
_HANDLER_MARKER = "_translationzed_py_owned"


def default_log_path() -> Path:
    """Return the process log path without creating it."""
    return Path(tempfile.gettempdir()) / "translationzed-py" / LOG_FILENAME


def get_logger() -> logging.Logger:
    """Return the application logger."""
    return logging.getLogger(LOGGER_NAME)


def current_log_path() -> Path | None:
    """Return the active rotating-log path, if file logging initialized."""
    return _ACTIVE_LOG_PATH


def configure_logging(*, log_path: Path | None = None) -> Path | None:
    """Configure console and rotating-file logging without blocking startup on failure."""
    global _ACTIVE_LOG_PATH

    logger = get_logger()
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    _remove_owned_handlers(logger)

    formatter = logging.Formatter(
        "%(asctime)sZ %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    formatter.converter = time.gmtime

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(formatter)
    setattr(console, _HANDLER_MARKER, True)
    logger.addHandler(console)

    requested = Path(log_path) if log_path is not None else default_log_path()
    try:
        requested.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            requested,
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        setattr(file_handler, _HANDLER_MARKER, True)
        logger.addHandler(file_handler)
    except Exception as exc:
        _ACTIVE_LOG_PATH = None
        logger.warning("Rotating file logging is unavailable: %s", exc)
        return None

    _ACTIVE_LOG_PATH = requested
    logger.info("Runtime logging initialized: %s", requested)
    return requested


def build_issue_report(
    *,
    app_version: str,
    qt_version: str,
    binding_version: str,
    project_root: Path | None = None,
    log_path: Path | None = None,
    exc_info: (
        tuple[type[BaseException], BaseException, TracebackType | None] | None
    ) = None,
) -> str:
    """Build a bounded Markdown report suitable for pasting into a GitHub issue."""
    active_log = log_path if log_path is not None else current_log_path()
    replacements = _private_path_replacements(project_root)
    exception_summary = "No exception was captured; describe the visible problem above."
    traceback_text = "No traceback captured."
    if exc_info is not None:
        exc_type, exc, tb = exc_info
        exception_summary = f"{exc_type.__name__}: {_bound_text(str(exc), 2_000)}"
        traceback_text = _bound_text(
            "".join(traceback.format_exception(exc_type, exc, tb)),
            REPORT_TRACEBACK_CHARS,
        )

    log_tail = (
        _read_log_tail(active_log, limit=REPORT_LOG_TAIL_BYTES)
        if active_log is not None
        else "File logging was unavailable for this run."
    )
    log_location = str(active_log) if active_log is not None else "Unavailable"
    fields = {
        "exception_summary": exception_summary,
        "traceback": traceback_text,
        "log_tail": log_tail,
        "log_location": log_location,
    }
    for key, value in tuple(fields.items()):
        fields[key] = _sanitize_paths(value, replacements)

    return "\n".join(
        (
            "# TranslationZed-Py issue report",
            "",
            "<!-- Review this report before posting. Project/home paths are redacted and "
            "environment variables are not collected. Error snippets may contain file text. -->",
            "",
            "## What I was doing",
            "",
            "<!-- List the actions immediately before the problem. -->",
            "",
            "## What happened",
            "",
            fields["exception_summary"],
            "",
            "## What I expected",
            "",
            "<!-- Describe the expected result. -->",
            "",
            "## Recovery and data safety",
            "",
            "- Did restarting restore the draft cache? <!-- Yes / No / Not tried -->",
            "- Were any original locale files changed unexpectedly? <!-- Yes / No -->",
            "- Accepted edits are normally cached immediately; describe any missing edit here.",
            "",
            "## Environment",
            "",
            f"- App version: {app_version}",
            f"- OS: {platform.platform()}",
            f"- Python: {' '.join(sys.version.split())}",
            f"- Qt: {qt_version}",
            f"- PySide: {binding_version}",
            f"- Project root: {'<PROJECT_ROOT>' if project_root is not None else 'Unavailable'}",
            f"- UTC time: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
            f"- Local log: {fields['log_location']}",
            "",
            "## Traceback",
            "",
            _markdown_code_block(fields["traceback"]),
            "",
            "## Recent log tail",
            "",
            _markdown_code_block(fields["log_tail"]),
            "",
            "Post at: https://github.com/PlagaMedicum/TranslationZed-py/issues/new",
        )
    )


def _remove_owned_handlers(logger: logging.Logger) -> None:
    for handler in tuple(logger.handlers):
        if not bool(getattr(handler, _HANDLER_MARKER, False)):
            continue
        logger.removeHandler(handler)
        with contextlib.suppress(Exception):
            handler.close()


def _read_log_tail(path: Path, *, limit: int) -> str:
    try:
        with path.open("rb") as handle:
            handle.seek(0, 2)
            size = handle.tell()
            start = max(0, size - max(1, int(limit)))
            handle.seek(start)
            payload = handle.read(max(1, int(limit)))
    except OSError as exc:
        return f"Log unavailable: {exc}"
    text = payload.decode("utf-8", errors="replace")
    if start:
        text = "[earlier log content omitted]\n" + text
    return text.rstrip() or "Log is empty."


def _private_path_replacements(
    project_root: Path | None,
) -> tuple[tuple[str, str], ...]:
    replacements: list[tuple[str, str]] = []
    if project_root is not None:
        raw = str(project_root)
        values = {raw}
        with contextlib.suppress(OSError, RuntimeError):
            values.add(str(project_root.resolve(strict=False)))
        replacements.extend((value, "<PROJECT_ROOT>") for value in values)
    try:
        home = str(Path.home())
    except Exception:
        home = ""
    if home:
        replacements.append((home, "~"))
    return tuple(sorted(replacements, key=lambda item: len(item[0]), reverse=True))


def _sanitize_paths(text: str, replacements: tuple[tuple[str, str], ...]) -> str:
    sanitized = str(text)
    for private, replacement in replacements:
        if private:
            sanitized = sanitized.replace(private, replacement)
    return sanitized


def _bound_text(text: str, limit: int) -> str:
    value = str(text)
    if len(value) <= limit:
        return value
    half = max(1, (limit - 40) // 2)
    return value[:half] + "\n[... bounded diagnostic omitted ...]\n" + value[-half:]


def _markdown_code_block(text: str) -> str:
    return "```text\n" + str(text).replace("```", "` ` `") + "\n```"
