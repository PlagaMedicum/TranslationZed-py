"""Qt preview and background orchestration for local Git synchronization."""

from __future__ import annotations

import contextlib
from collections.abc import Callable, Mapping
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import (
    QAbstractTableModel,
    QEvent,
    QModelIndex,
    QObject,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QProgressDialog,
    QStyledItemDelegate,
    QTableView,
    QVBoxLayout,
)

from translationzed_py.core.git_sync import (
    GitSyncError,
    inspect,
    inspect_state,
    resolve_commit,
    write_state,
)
from translationzed_py.core.git_sync_apply import (
    GitSyncApplyResult,
    apply_resolved_plan,
)
from translationzed_py.core.git_sync_service import (
    GitSyncItemChoice,
    GitSyncMergePlan,
    GitSyncResolvedPlan,
    build_change_set,
    build_merge_plan,
    resolve_merge_plan,
)
from translationzed_py.core.project_scanner import LocaleMeta

from . import runtime_reliability

_DECISION_LABELS = {
    "apply": "Apply",
    "ignore": "Ignore",
    "conflict": "Resolve…",
}
_COMMENT_LABELS = {
    "none": "—",
    "use_en": "Use EN",
    "keep_locale": "Keep locale",
    "choose": "Choose…",
}
_DETAIL_LIMIT = 12_000


@dataclass(frozen=True, slots=True)
class GitSyncDetection:
    """Describe saved-baseline availability and local committed HEAD state."""

    baseline: str | None = None
    head: str | None = None
    problem: str | None = None

    @property
    def changed(self) -> bool:
        """Return whether local committed HEAD differs from the saved baseline."""
        return bool(self.baseline and self.head and self.baseline != self.head)


@dataclass(frozen=True, slots=True)
class GitSyncPreparation:
    """Return either a preview plan or a recoverable baseline problem."""

    plan: GitSyncMergePlan | None = None
    problem: str | None = None


@dataclass(slots=True)
class _RowChoice:
    decision: str
    comment_decision: str
    mark_for_review: bool


def detect_local_head(root: Path) -> GitSyncDetection:
    """Inspect only saved state and local commits for the startup indicator."""
    state = inspect_state(root)
    if state.state is None:
        return GitSyncDetection(problem=state.problem or "missing")
    head = resolve_commit(root, "HEAD")
    try:
        baseline = resolve_commit(root, state.state.baseline)
    except GitSyncError:
        return GitSyncDetection(head=head, problem="unreachable")
    return GitSyncDetection(baseline=baseline, head=head)


def prepare_git_sync(
    root: Path,
    *,
    locales: Mapping[str, LocaleMeta],
    selected_locales: tuple[str, ...],
    en_encoding: str,
    comment_prefix: str,
) -> GitSyncPreparation:
    """Build a cache-aware preview from the saved baseline through local HEAD."""
    state = inspect_state(root)
    if state.state is None:
        return GitSyncPreparation(problem=state.problem or "missing")
    resolve_commit(root, "HEAD")
    try:
        baseline = resolve_commit(root, state.state.baseline)
    except GitSyncError:
        return GitSyncPreparation(problem="unreachable")
    inspection = inspect(root, baseline=baseline)
    change_set = build_change_set(
        root,
        inspection,
        en_encoding=en_encoding,
        comment_prefixes=(comment_prefix,),
    )
    return GitSyncPreparation(
        plan=build_merge_plan(
            root,
            change_set,
            locales=locales,
            selected_locales=selected_locales,
            comment_prefixes=(comment_prefix,),
        )
    )


def _clip(value: str | None, limit: int = 120) -> str:
    text = "" if value is None else str(value)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)] + "…"


def _bounded_lines(paths: tuple[str, ...], *, limit: int = 12) -> str:
    shown = list(paths[:limit])
    if len(paths) > limit:
        shown.append(f"… and {len(paths) - limit} more")
    return ", ".join(shown)


class GitSyncPreviewModel(QAbstractTableModel):
    """Expose an immutable merge plan with transient editable choices."""

    resolution_changed = Signal()
    _HEADERS = (
        "Locale",
        "File",
        "Key",
        "Change",
        "Translation",
        "Decision",
        "Comments",
        "For review",
    )
    DECISION_COLUMN = 5
    COMMENT_COLUMN = 6
    REVIEW_COLUMN = 7

    def __init__(self, plan: GitSyncMergePlan, parent: QObject | None = None) -> None:
        """Initialize choices from the core plan defaults."""
        super().__init__(parent)
        self.plan = plan
        self._choices = [
            _RowChoice(
                decision=item.default_decision,
                comment_decision=item.comment_decision,
                mark_for_review=item.propose_for_review,
            )
            for item in plan.items
        ]

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        """Return the number of preview items."""
        return 0 if parent and parent.isValid() else len(self.plan.items)

    def columnCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        """Return the fixed preview column count."""
        return 0 if parent and parent.isValid() else len(self._HEADERS)

    def headerData(  # noqa: N802
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.DisplayRole,
    ) -> object:
        """Return compact horizontal labels."""
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self._HEADERS[section]
        return super().headerData(section, orientation, role)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> object:
        """Render one preview value or editable choice."""
        if not index.isValid() or not 0 <= index.row() < len(self.plan.items):
            return None
        item = self.plan.items[index.row()]
        choice = self._choices[index.row()]
        column = index.column()
        if role in {Qt.DisplayRole, Qt.EditRole}:
            values: tuple[object, ...] = (
                item.locale,
                item.target_path,
                item.key or "(file)",
                ", ".join(item.kinds),
                _clip(item.target_value) or "—",
                (
                    _DECISION_LABELS.get(choice.decision, choice.decision)
                    if role == Qt.DisplayRole
                    else choice.decision
                ),
                (
                    _COMMENT_LABELS.get(
                        choice.comment_decision, choice.comment_decision
                    )
                    if role == Qt.DisplayRole
                    else choice.comment_decision
                ),
                "" if item.propose_for_review else "—",
            )
            return values[column]
        if role == Qt.CheckStateRole and column == self.REVIEW_COLUMN:
            if item.propose_for_review:
                return Qt.Checked if choice.mark_for_review else Qt.Unchecked
            return None
        if role == Qt.ToolTipRole:
            if column == 4:
                return item.target_value or ""
            if column == self.DECISION_COLUMN:
                return item.conflict_reason or "Apply or explicitly ignore this item."
            if column == self.COMMENT_COLUMN and item.comment_decision == "choose":
                return (
                    "Choose whether to keep locale comments or use current EN comments."
                )
        if role == Qt.TextAlignmentRole and column in {0, 7}:
            return Qt.AlignCenter
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        """Enable only the three transient decision controls."""
        flags = super().flags(index)
        if not index.isValid():
            return flags
        item = self.plan.items[index.row()]
        if index.column() == self.DECISION_COLUMN:
            return flags | Qt.ItemIsEditable
        if index.column() == self.COMMENT_COLUMN and item.comment_decision == "choose":
            return flags | Qt.ItemIsEditable
        if index.column() == self.REVIEW_COLUMN and item.propose_for_review:
            return flags | Qt.ItemIsUserCheckable
        return flags

    def editor_options(self, index: QModelIndex) -> tuple[tuple[str, str], ...]:
        """Return raw/display choices for the combo delegate."""
        item = self.plan.items[index.row()]
        if index.column() == self.DECISION_COLUMN:
            values = (
                ("apply", "ignore", "conflict")
                if item.can_apply
                else (
                    "ignore",
                    "conflict",
                )
            )
            return tuple((value, _DECISION_LABELS[value]) for value in values)
        if index.column() == self.COMMENT_COLUMN and item.comment_decision == "choose":
            return tuple(
                (value, _COMMENT_LABELS[value])
                for value in ("choose", "use_en", "keep_locale")
            )
        return ()

    def setData(  # noqa: N802
        self, index: QModelIndex, value: object, role: int = Qt.EditRole
    ) -> bool:
        """Update a transient choice and notify the dialog's resolution guard."""
        if not index.isValid():
            return False
        item = self.plan.items[index.row()]
        choice = self._choices[index.row()]
        column = index.column()
        changed_columns = {column}
        changed = False
        if role == Qt.EditRole and column == self.DECISION_COLUMN:
            raw = str(value)
            allowed = {entry[0] for entry in self.editor_options(index)}
            if raw in allowed and choice.decision != raw:
                choice.decision = raw
                changed = True
        elif role == Qt.EditRole and column == self.COMMENT_COLUMN:
            raw = str(value)
            allowed = {entry[0] for entry in self.editor_options(index)}
            if raw in allowed and choice.comment_decision != raw:
                choice.comment_decision = raw
                changed = True
                if raw in {"use_en", "keep_locale"} and choice.decision == "conflict":
                    choice.decision = "apply"
                    changed_columns.add(self.DECISION_COLUMN)
        elif (
            role == Qt.CheckStateRole
            and column == self.REVIEW_COLUMN
            and item.propose_for_review
        ):
            checked = value == Qt.Checked or value == Qt.CheckState.Checked
            if choice.mark_for_review != checked:
                choice.mark_for_review = checked
                changed = True
        if not changed:
            return False
        left = self.index(index.row(), min(changed_columns))
        right = self.index(index.row(), max(changed_columns))
        self.dataChanged.emit(
            left,
            right,
            [Qt.DisplayRole, Qt.EditRole, Qt.CheckStateRole],
        )
        self.resolution_changed.emit()
        return True

    def unresolved_count(self) -> int:
        """Count choices that the core resolver would reject as incomplete."""
        count = 0
        for item, choice in zip(self.plan.items, self._choices, strict=True):
            if choice.decision == "conflict" or (
                choice.decision == "apply"
                and (
                    not item.can_apply
                    or (
                        item.comment_decision == "choose"
                        and choice.comment_decision not in {"use_en", "keep_locale"}
                    )
                )
            ):
                count += 1
        return count

    def choices(self) -> dict[str, GitSyncItemChoice]:
        """Build core choice DTOs without performing effects."""
        return {
            item.item_id: GitSyncItemChoice(
                item_id=item.item_id,
                decision=choice.decision,  # type: ignore[arg-type]
                comment_decision=choice.comment_decision,  # type: ignore[arg-type]
                mark_for_review=choice.mark_for_review,
            )
            for item, choice in zip(self.plan.items, self._choices, strict=True)
        }


class _ChoiceDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):  # noqa: N802
        model = index.model()
        if not isinstance(model, GitSyncPreviewModel):
            return super().createEditor(parent, option, index)
        options = model.editor_options(index)
        if not options:
            return None
        combo = QComboBox(parent)
        for value, label in options:
            combo.addItem(label, value)
        return combo

    def setEditorData(self, editor, index) -> None:  # noqa: N802
        if not isinstance(editor, QComboBox):
            return super().setEditorData(editor, index)
        current = index.data(Qt.EditRole)
        position = editor.findData(current)
        editor.setCurrentIndex(max(0, position))

    def setModelData(self, editor, model, index) -> None:  # noqa: N802
        if not isinstance(editor, QComboBox):
            return super().setModelData(editor, model, index)
        model.setData(index, editor.currentData(), Qt.EditRole)


class GitSyncPreviewDialog(QDialog):
    """Show a bounded, explicit preview before cache-only synchronization."""

    def __init__(self, plan: GitSyncMergePlan, parent=None) -> None:
        """Build the preview table, detail panel, warnings, and apply guard."""
        super().__init__(parent)
        self.setWindowTitle("Synchronize from local Git HEAD")
        self.setWindowModality(Qt.WindowModal)
        self.resize(1120, 720)
        layout = QVBoxLayout(self)
        summary = QLabel(
            f"Review {len(plan.items)} target-locale item(s). Apply writes drafts/status "
            "cache only; normal Save remains the only route to locale files.",
            self,
        )
        summary.setWordWrap(True)
        layout.addWidget(summary)
        warnings: list[str] = []
        if plan.dirty_paths:
            warnings.append(
                "Uncommitted EN paths are not included: "
                + _bounded_lines(plan.dirty_paths)
            )
        if plan.unsupported_paths:
            warnings.append(
                "Unsupported EN paths were skipped: "
                + _bounded_lines(plan.unsupported_paths)
            )
        if warnings:
            warning = QLabel("\n".join(warnings), self)
            warning.setWordWrap(True)
            layout.addWidget(warning)

        self.model = GitSyncPreviewModel(plan, self)
        self.table = QTableView(self)
        self.table.setModel(self.model)
        self.table.setItemDelegate(_ChoiceDelegate(self.table))
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(
            QAbstractItemView.DoubleClicked | QAbstractItemView.SelectedClicked
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        for column in (1, 2, 4):
            header.setSectionResizeMode(column, QHeaderView.Stretch)
        layout.addWidget(self.table, 2)

        self.details = QPlainTextEdit(self)
        self.details.setReadOnly(True)
        self.details.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.details.setMinimumHeight(170)
        layout.addWidget(self.details, 1)
        self._resolution_label = QLabel(self)
        layout.addWidget(self._resolution_label)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel, self)
        self._apply_button = buttons.addButton(
            "Apply to drafts", QDialogButtonBox.AcceptRole
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.model.resolution_changed.connect(self._refresh_resolution)
        self.table.selectionModel().currentRowChanged.connect(self._show_details)
        if plan.items:
            self.table.selectRow(0)
            self._show_details(self.model.index(0, 0), QModelIndex())
        else:
            self.details.setPlainText(
                "No target-locale items were produced. Applying records local HEAD as reviewed."
            )
        self._refresh_resolution()

    def _refresh_resolution(self) -> None:
        unresolved = self.model.unresolved_count()
        self._apply_button.setEnabled(unresolved == 0)
        self._resolution_label.setText(
            "All items are resolved."
            if unresolved == 0
            else f"Resolve or ignore {unresolved} item(s) before applying."
        )

    def _show_details(self, current: QModelIndex, _previous: QModelIndex) -> None:
        if not current.isValid():
            return
        item = self.model.plan.items[current.row()]
        parts = [
            f"Target: {item.target_path}",
            f"Key: {item.key or '(file-level change)'}",
            f"Change: {', '.join(item.kinds)}",
            "",
            "Previous EN:",
            _clip(item.base_source, _DETAIL_LIMIT) or "(missing)",
            "",
            "Current EN:",
            _clip(item.head_source, _DETAIL_LIMIT) or "(missing)",
            "",
            "Current translation/draft:",
            _clip(item.target_value, _DETAIL_LIMIT) or "(missing)",
        ]
        if item.base_comments or item.head_comments or item.target_comments:
            parts.extend(
                [
                    "",
                    "Previous EN comments:",
                    _clip("\n".join(item.base_comments), _DETAIL_LIMIT) or "(none)",
                    "",
                    "Current EN comments:",
                    _clip("\n".join(item.head_comments), _DETAIL_LIMIT) or "(none)",
                    "",
                    "Locale comments:",
                    _clip("\n".join(item.target_comments), _DETAIL_LIMIT) or "(none)",
                ]
            )
        if item.conflict_reason:
            parts.extend(["", "Needs attention:", item.conflict_reason])
        self.details.setPlainText("\n".join(parts))

    def resolved_plan(self) -> GitSyncResolvedPlan:
        """Run the authoritative core resolver over the dialog choices."""
        return resolve_merge_plan(self.model.plan, self.model.choices())


class GitSyncController(QObject):
    """Keep Git inspection and cache application outside the GUI thread."""

    def __init__(self, window) -> None:
        """Create one serialized worker and one General-menu action."""
        super().__init__(window)
        self._window = window
        self._root = Path(window._root)
        self._pool = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="tzp-git-sync"
        )
        self._future: Future[Any] | None = None
        self._success: Callable[[Any], None] | None = None
        self._show_errors = False
        self._phase = "idle"
        self._closed = False
        self._pending_resolved: GitSyncResolvedPlan | None = None
        self._progress: QProgressDialog | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._poll)
        self.action = QAction("Synchronize from &Git…", window)
        self.action.setObjectName("git_sync_action")
        self.action.setToolTip("Compare the saved baseline with local committed HEAD.")
        self.action.triggered.connect(self.run)
        window.addAction(self.action)
        window.installEventFilter(self)

    def schedule_detection(self) -> None:
        """Queue a startup check after the window finishes constructing."""
        if not self._window._test_mode:
            QTimer.singleShot(0, self.detect)

    def detect(self) -> None:
        """Check local committed HEAD without showing a startup modal."""
        self._submit(
            "detect",
            lambda: detect_local_head(self._root),
            self._apply_detection,
            show_errors=False,
        )

    def run(self) -> None:
        """Build and present an explicit synchronization preview."""
        if self._future is not None:
            self._window.statusBar().showMessage(
                "Git synchronization is already running.", 3000
            )
            return
        selected = tuple(
            code for code in self._window._selected_locales if code != "EN"
        )
        if not selected:
            QMessageBox.information(
                self._window,
                "No target locale",
                "Select at least one target locale before synchronization.",
            )
            return
        if not self._window._write_cache_current():
            return
        locales = dict(self._window._locales)
        en_meta = locales.get("EN")
        if en_meta is None:
            QMessageBox.warning(
                self._window,
                "English locale unavailable",
                "The project has no readable EN locale metadata.",
            )
            return
        comment_prefix = self._window._app_config.comment_prefix
        self._window.statusBar().showMessage("Preparing local Git synchronization…", 0)
        self._submit(
            "prepare",
            lambda: prepare_git_sync(
                self._root,
                locales=locales,
                selected_locales=selected,
                en_encoding=en_meta.charset,
                comment_prefix=comment_prefix,
            ),
            self._show_preparation,
            show_errors=True,
        )

    def _submit(
        self,
        phase: str,
        job: Callable[[], Any],
        success: Callable[[Any], None],
        *,
        show_errors: bool,
    ) -> None:
        if self._closed or self._future is not None:
            return
        self._phase = phase
        self._show_errors = show_errors
        self._success = success
        self.action.setEnabled(False)
        self._future = self._pool.submit(job)
        self._timer.start()

    def _poll(self) -> None:
        future = self._future
        if future is None or not future.done():
            return
        self._timer.stop()
        success = self._success
        show_errors = self._show_errors
        phase = self._phase
        self._future = None
        self._success = None
        self._show_errors = False
        self._phase = "idle"
        self.action.setEnabled(True)
        self._close_progress()
        try:
            result = future.result()
        except Exception as exc:
            if phase == "apply":
                self._pending_resolved = None
            runtime_reliability.log_exception(
                f"Git synchronization {phase} failed", exc
            )
            self.action.setToolTip(
                f"Git synchronization unavailable: {_clip(str(exc), 300)}"
            )
            if show_errors:
                QMessageBox.critical(
                    self._window,
                    "Git synchronization failed",
                    "No locale originals or Git history were changed. Retry after fixing the "
                    "reported problem. If cache effects completed before a final baseline error, "
                    "retry is safe.\n\n"
                    f"{exc}\n\nUse Help → Copyable Issue Report if this is unexpected.",
                )
            return
        if success is not None and not self._closed:
            success(result)

    def _apply_detection(self, detection: GitSyncDetection) -> None:
        if detection.problem:
            self.action.setText("Synchronize from &Git…")
            self.action.setToolTip(
                "Set up or repair the saved local-HEAD synchronization baseline."
            )
            return
        if detection.changed:
            self.action.setText("Synchronize from &Git… (changes available)")
            self.action.setToolTip(
                "Local committed HEAD has changed since synchronization."
            )
            self._window.statusBar().showMessage(
                "Committed English changes are available: General → Synchronize from Git…",
                8000,
            )
        else:
            self._set_synchronized(detection.head)

    def _show_preparation(self, preparation: GitSyncPreparation) -> None:
        if preparation.problem:
            self._offer_baseline_reset(preparation.problem)
            return
        plan = preparation.plan
        if plan is None:
            return
        if plan.baseline == plan.head:
            self._set_synchronized(plan.head)
            QMessageBox.information(
                self._window,
                "Already synchronized",
                "The saved baseline already matches local committed HEAD.",
            )
            return
        dialog = GitSyncPreviewDialog(plan, self._window)
        if dialog.exec() != QDialog.Accepted:
            self._window.statusBar().showMessage(
                "Git synchronization cancelled; the baseline was not changed.", 5000
            )
            return
        resolved = dialog.resolved_plan()
        if not resolved.advance_baseline:
            return
        self._start_apply(resolved)

    def _offer_baseline_reset(self, problem: str) -> None:
        descriptions = {
            "missing": "This project has no synchronization baseline.",
            "unreadable": "The saved synchronization baseline cannot be read.",
            "malformed": "The saved synchronization baseline is malformed.",
            "unsupported_version": "The saved synchronization baseline has an unsupported format.",
            "invalid_baseline": "The saved synchronization baseline is invalid.",
            "unreachable": "The saved synchronization commit is not available locally.",
        }
        answer = QMessageBox.question(
            self._window,
            "Set local Git baseline",
            descriptions.get(problem, "The synchronization baseline is unavailable.")
            + "\n\nSet current local committed HEAD as the starting point? "
            "This changes only TranslationZed-Py's project cache; it does not change Git or "
            "locale files.",
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if answer != QMessageBox.Yes:
            return
        self._window.statusBar().showMessage("Setting local Git baseline…", 0)
        self._submit(
            "initialize",
            lambda: write_state(self._root, baseline="HEAD"),
            lambda state: self._baseline_initialized(state.baseline),
            show_errors=True,
        )

    def _baseline_initialized(self, baseline: str) -> None:
        self._set_synchronized(baseline)
        QMessageBox.information(
            self._window,
            "Git synchronization ready",
            "Current local committed HEAD is now the baseline. Future committed English "
            "changes will appear in the synchronization preview.",
        )

    def _start_apply(self, resolved: GitSyncResolvedPlan) -> None:
        self._pending_resolved = resolved
        progress = QProgressDialog(
            "Applying synchronization choices to drafts…",
            "",
            0,
            0,
            self._window,
        )
        progress.setWindowTitle("Synchronize from Git")
        progress.setWindowModality(Qt.WindowModal)
        progress.setCancelButton(None)
        progress.setMinimumDuration(0)
        progress.show()
        self._progress = progress
        locales = dict(self._window._locales)
        comment_prefix = self._window._app_config.comment_prefix
        self._submit(
            "apply",
            lambda: apply_resolved_plan(
                self._root,
                resolved,
                locales=locales,
                comment_prefixes=(comment_prefix,),
            ),
            self._apply_finished,
            show_errors=True,
        )

    def _apply_finished(self, result: GitSyncApplyResult) -> None:
        resolved = self._pending_resolved
        self._pending_resolved = None
        if resolved is not None:
            affected = {
                (self._root / item.target_path).resolve()
                for item in resolved.plan.items
            }
            current = getattr(self._window, "_current_pf", None)
            if current is not None and current.path.resolve() in affected:
                self._window._reload_file(current.path)
        self._window._mark_cached_dirty()
        self._set_synchronized(result.baseline)
        self._window.statusBar().showMessage(
            "Git synchronization applied to drafts: "
            f"{result.reviewed_items} review mark(s), "
            f"{result.staged_comment_items} staged comment update(s).",
            8000,
        )

    def _set_synchronized(self, commit: str | None) -> None:
        self.action.setText("Synchronize from &Git…")
        suffix = f" ({commit[:12]})" if commit else ""
        self.action.setToolTip(
            "Saved baseline matches local committed HEAD" + suffix + "."
        )

    def _close_progress(self) -> None:
        progress = self._progress
        self._progress = None
        if progress is not None:
            progress.close()
            progress.deleteLater()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Block window close only during a cache/baseline write phase."""
        if (
            watched is self._window
            and event.type() == QEvent.Close
            and self._phase in {"apply", "initialize"}
        ):
            event.ignore()
            self._window.statusBar().showMessage(
                "Wait for Git synchronization to finish before closing.", 4000
            )
            return True
        return super().eventFilter(watched, event)

    def shutdown(self) -> None:
        """Stop polling and abandon queued read-only work during accepted close."""
        if self._closed:
            return
        self._closed = True
        self._timer.stop()
        if self._future is not None:
            with contextlib.suppress(Exception):
                self._future.cancel()
        self._future = None
        self._success = None
        self._close_progress()
        with contextlib.suppress(Exception):
            self._pool.shutdown(wait=False, cancel_futures=True)
        with contextlib.suppress(Exception):
            self._window.removeEventFilter(self)


def install(window) -> GitSyncController:
    """Add the local-Git action at the current General-menu insertion point."""
    controller = GitSyncController(window)
    window.menu_general.addAction(controller.action)
    controller.schedule_detection()
    return controller


__all__ = [
    "GitSyncController",
    "GitSyncDetection",
    "GitSyncPreparation",
    "GitSyncPreviewDialog",
    "GitSyncPreviewModel",
    "detect_local_head",
    "install",
    "prepare_git_sync",
]
