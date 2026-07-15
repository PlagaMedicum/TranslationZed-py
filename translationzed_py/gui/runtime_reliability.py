"""Qt adapters for session locking, exception containment, and issue reports."""

from __future__ import annotations

import logging
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType

import PySide6
from PySide6.QtCore import QLockFile, qVersion
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from translationzed_py import __version__
from translationzed_py.core.runtime_diagnostics import (
    build_issue_report,
    current_log_path,
    get_logger,
)

SESSION_LOCK_FILENAME = "session.lock"


@dataclass(frozen=True, slots=True)
class ProjectSessionLockResult:
    """Describe acquisition of the one-writer project-session lock."""

    lock: QLockFile | None
    previous_session_unclean: bool = False
    error_title: str = ""
    error_message: str = ""

    @property
    def acquired(self) -> bool:
        """Return whether the project lock is owned by this process."""
        return self.lock is not None


def acquire_project_session_lock(
    *, root: Path, cache_dir: str
) -> ProjectSessionLockResult:
    """Acquire a long-lived project lock and detect a stale crash marker."""
    path = root / cache_dir / SESSION_LOCK_FILENAME
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        get_logger().error("Cannot create project session-lock directory: %s", exc)
        return ProjectSessionLockResult(
            lock=None,
            error_title="Project session unavailable",
            error_message=(
                "TranslationZed-Py could not create its project session lock. "
                "The project was not opened because concurrent draft writes could lose changes."
                f"\n\n{exc}"
            ),
        )

    marker_existed = path.exists()
    lock = QLockFile(str(path))
    # A project stays open for an arbitrary duration. PID/process-name checks still
    # remove locks left by crashed processes; age alone must not evict a live owner.
    lock.setStaleLockTime(0)
    try:
        acquired = lock.tryLock(0)
    except Exception as exc:
        get_logger().exception("Project session-lock acquisition raised")
        return ProjectSessionLockResult(
            lock=None,
            error_title="Project session unavailable",
            error_message=f"Could not acquire the project session lock.\n\n{exc}",
        )
    if acquired:
        get_logger().info(
            "Project session lock acquired%s",
            " after an unclean session" if marker_existed else "",
        )
        return ProjectSessionLockResult(
            lock=lock,
            previous_session_unclean=marker_existed,
        )

    owner = _lock_owner_text(lock)
    if lock.error() == QLockFile.LockError.LockFailedError:
        message = (
            "This project is already open in another TranslationZed-Py process. "
            "Close that process before reopening the project. This guard prevents "
            "two instances from overwriting the same draft cache."
        )
        if owner:
            message += f"\n\nLock owner: {owner}"
        title = "Project already open"
    else:
        title = "Project session unavailable"
        message = (
            "TranslationZed-Py could not create its project session lock. "
            "Check write permissions for the project cache directory, then retry."
        )
    get_logger().error("%s: %s", title, message.replace("\n", " "))
    return ProjectSessionLockResult(
        lock=None,
        error_title=title,
        error_message=message,
    )


def ensure_project_session_lock(win: QWidget) -> ProjectSessionLockResult:
    """Acquire once for a window and retain the lock for its full session."""
    existing = getattr(win, "_project_session_lock", None)
    if existing is not None and existing.isLocked():
        return ProjectSessionLockResult(
            lock=existing,
            previous_session_unclean=bool(
                getattr(win, "_previous_session_unclean", False)
            ),
        )
    result = acquire_project_session_lock(
        root=Path(win._root),
        cache_dir=str(win._app_config.cache_dir),
    )
    if result.acquired:
        win._project_session_lock = result.lock
        win._previous_session_unclean = result.previous_session_unclean
    return result


def start_project_session(win: QWidget) -> bool:
    """Acquire the one-writer lock before any project cache mutation can occur."""
    result = ensure_project_session_lock(win)
    if result.acquired:
        return True
    show_session_lock_error(win, result)
    return False


def abort_project_startup(win: QWidget) -> None:
    """Mark startup aborted and release any project lock already acquired."""
    win._startup_aborted = True
    release_project_session_lock(win)


def show_session_lock_error(parent: QWidget, result: ProjectSessionLockResult) -> None:
    """Show an actionable failure for a project lock that could not be acquired."""
    QMessageBox.critical(parent, result.error_title, result.error_message)


def release_project_session_lock(win: QWidget) -> None:
    """Release the lock only after a close has passed all cancellation guards."""
    lock = getattr(win, "_project_session_lock", None)
    if lock is None:
        return
    try:
        lock.unlock()
        get_logger().info("Project session lock released")
    except Exception:
        get_logger().exception("Project session lock release failed")
    finally:
        win._project_session_lock = None


def log_user_message(*, critical: bool, title: str, text: str) -> None:
    """Record a bounded user-visible warning/error."""
    level = logging.ERROR if critical else logging.WARNING
    message = str(text).replace("\n", " ")
    if len(message) > 2_000:
        message = message[:2_000] + " [message bounded]"
    get_logger().log(level, "%s: %s", title, message)


def log_exception(context: str, exc: BaseException) -> None:
    """Record an already-caught exception with its original traceback."""
    get_logger().error(
        "%s: %s",
        context,
        exc,
        exc_info=(type(exc), exc, exc.__traceback__),
    )


def cache_error(exc: BaseException) -> str:
    """Explain the safe recovery path after a draft-cache write failure."""
    return (
        "The draft cache could not be written. Your edit remains in this window, and file "
        "switching or closing will be blocked until caching succeeds. Check free disk space "
        f"and project-cache permissions, then retry.\n\n{exc}"
    )


def add_issue_report_action(win: QWidget) -> None:
    """Add the standard copyable-report action to an existing Help menu."""
    action = win.menu_help.addAction("Copyable &Issue Report…")
    action.triggered.connect(lambda: show_issue_report(win))


def build_runtime_issue_report(
    parent: QWidget | None,
    *,
    exc_info: (
        tuple[type[BaseException], BaseException, TracebackType | None] | None
    ) = None,
    log_path: Path | None = None,
) -> str:
    """Build the current runtime's privacy-aware GitHub issue template."""
    root_value = getattr(parent, "_root", None) if parent is not None else None
    root = Path(root_value) if root_value is not None else None
    return build_issue_report(
        app_version=__version__,
        qt_version=qVersion(),
        binding_version=PySide6.__version__,
        project_root=root,
        log_path=log_path if log_path is not None else current_log_path(),
        exc_info=exc_info,
    )


def show_issue_report(
    parent: QWidget | None,
    *,
    exc_info: (
        tuple[type[BaseException], BaseException, TracebackType | None] | None
    ) = None,
    log_path: Path | None = None,
) -> None:
    """Show a selectable, one-click-copy issue report."""
    report = build_runtime_issue_report(
        parent,
        exc_info=exc_info,
        log_path=log_path,
    )
    dialog = QDialog(parent)
    dialog.setWindowTitle(
        "Unexpected error" if exc_info is not None else "TranslationZed-Py issue report"
    )
    dialog.resize(780, 560)
    layout = QVBoxLayout(dialog)
    label = QLabel(
        (
            "An unexpected error was contained. Copy this report, restart if the window "
            "no longer behaves normally, and verify that draft recovery restores your edits."
            if exc_info is not None
            else (
                "Copy this report, fill in the placeholders, review it, and paste it "
                "into a GitHub issue."
            )
        ),
        dialog,
    )
    label.setWordWrap(True)
    layout.addWidget(label)
    editor = QPlainTextEdit(dialog)
    editor.setReadOnly(True)
    editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
    editor.setPlainText(report)
    layout.addWidget(editor, 1)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, dialog)
    copy_button = buttons.addButton(
        "Copy report", QDialogButtonBox.ButtonRole.ActionRole
    )
    copy_button.clicked.connect(
        lambda: QGuiApplication.clipboard().setText(editor.toPlainText())
    )
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    dialog.exec()


class GuiExceptionBoundary:
    """Contain uncaught Python GUI exceptions and render copyable diagnostics."""

    def __init__(self, *, log_path: Path | None) -> None:
        """Initialize an inactive boundary for one GUI event-loop lifetime."""
        self._log_path = log_path
        self._parent: QWidget | None = None
        self._previous_hook = sys.excepthook
        self._handling = False

    def install(self) -> None:
        """Install this boundary as the process exception hook."""
        self._previous_hook = sys.excepthook
        sys.excepthook = self.handle

    def restore(self) -> None:
        """Restore the hook that was active before this boundary."""
        if sys.excepthook == self.handle:
            sys.excepthook = self._previous_hook

    def set_parent(self, parent: QWidget) -> None:
        """Set the current window used to parent diagnostics dialogs."""
        self._parent = parent

    def handle(
        self,
        exc_type: type[BaseException],
        exc: BaseException,
        tb: TracebackType | None,
    ) -> None:
        """Log and contain one uncaught Python exception."""
        if issubclass(exc_type, (KeyboardInterrupt, SystemExit)) or self._handling:
            self._previous_hook(exc_type, exc, tb)
            return
        self._handling = True
        try:
            get_logger().critical(
                "Unhandled GUI exception",
                exc_info=(exc_type, exc, tb),
            )
            if QApplication.instance() is None:
                self._previous_hook(exc_type, exc, tb)
                return
            show_issue_report(
                QApplication.activeWindow() or self._parent,
                exc_info=(exc_type, exc, tb),
                log_path=self._log_path,
            )
        except Exception:
            get_logger().exception("Failed to render unexpected-error diagnostics")
            self._previous_hook(exc_type, exc, tb)
        finally:
            self._handling = False


@contextmanager
def gui_exception_boundary(*, log_path: Path | None) -> Iterator[GuiExceptionBoundary]:
    """Install a GUI exception boundary for startup and the Qt event loop."""
    boundary = GuiExceptionBoundary(log_path=log_path)
    boundary.install()
    try:
        yield boundary
    except Exception:
        exc_type, exc, tb = sys.exc_info()
        if exc_type is not None and exc is not None:
            boundary.handle(exc_type, exc, tb)
    finally:
        boundary.restore()


def _lock_owner_text(lock: QLockFile) -> str:
    try:
        pid, hostname, appname = lock.getLockInfo()
    except Exception:
        return ""
    parts = [f"PID {pid}"]
    if appname:
        parts.append(str(appname))
    if hostname:
        parts.append(f"host {hostname}")
    return ", ".join(parts)
