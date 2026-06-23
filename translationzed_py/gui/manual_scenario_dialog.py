"""Checklist dialog for manual UI scenario runs."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .manual_scenario_runtime import SCENARIO_ENV_RUN_TOKEN, ManualScenarioRuntime

WORKFLOW_LABELS = {
    "open_save": "Open / Save",
    "conflict_resolution": "Conflict Resolution",
    "qa_checklist": "QA Checklist",
    "encoding_charsets": "Encoding / Charsets",
    "tm_apply": "TM Apply",
    "source_reference": "Source Reference",
    "tzp_writeback": "TZP Write-back",
    "status_triage": "Status Triage",
    "search_replace": "Search / Replace",
}
MANUAL_DEPTH_LABELS = {
    "full_workflow": "Full workflow",
    "branch_check": "Branch check",
    "same_file_diagnostic": "Same-file diagnostic",
    "multi_file_roundtrip": "Multi-file roundtrip",
}


class ManualScenarioChecklistDialog(QDialog):
    """Display scenario steps/expectations and capture pass/fail notes."""

    def __init__(
        self,
        runtime: ManualScenarioRuntime,
        *,
        results_dir: Path,
        parent=None,
    ) -> None:
        """Initialize the checklist dialog for one manual scenario run."""
        super().__init__(parent)
        self._runtime = runtime
        self._results_dir = results_dir
        self._final_result: str | None = None
        self.setWindowTitle(f"Manual Scenario: {runtime.scenario.title}")
        self.resize(760, 620)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self._details_scroll = QScrollArea(self)
        self._details_scroll.setObjectName("scenario_details_scroll")
        self._details_scroll.setWidgetResizable(True)
        self._details_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._details_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._details_scroll.setMaximumHeight(190)
        details_container = QWidget(self._details_scroll)
        details_layout = QVBoxLayout(details_container)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(6)
        self._details_scroll.setWidget(details_container)
        layout.addWidget(self._details_scroll, 0)

        self._project_root = Path(runtime.project_root)

        summary = QLabel(
            f"Scenario ID: {runtime.scenario.id}\nFixture: {runtime.scenario.fixture_root}",
            self,
        )
        summary.setTextFormat(Qt.TextFormat.PlainText)
        summary.setWordWrap(True)
        summary.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        details_layout.addWidget(summary)

        self._add_copy_row(
            details_layout,
            "Project root",
            str(self._project_root),
            button_text="Copy project root",
            object_name="copy_project_root_button",
        )

        self._add_plain_section(details_layout, "Goal", runtime.scenario.goal)
        self._add_plain_section(
            details_layout,
            "Workflow family",
            WORKFLOW_LABELS.get(
                runtime.scenario.workflow_family, runtime.scenario.workflow_family
            ),
        )
        self._add_plain_section(
            details_layout, "Start context", runtime.scenario.start_context
        )
        self._add_copy_section(
            details_layout,
            "Focus files",
            runtime.scenario.focus_files,
            button_text="Copy focus paths",
            object_name="copy_focus_paths_button",
        )
        depth_label = MANUAL_DEPTH_LABELS.get(
            runtime.scenario.manual_depth, runtime.scenario.manual_depth
        )
        self._add_plain_section(
            details_layout,
            "Finish condition",
            f"{runtime.scenario.finish_condition}\nDepth: {depth_label}",
        )
        if runtime.scenario.operator_hints:
            self._add_plain_section(
                details_layout,
                "Operator hints",
                "\n".join(runtime.scenario.operator_hints),
            )
        if runtime.scenario.inspection_paths:
            self._add_copy_section(
                details_layout,
                "Inspection paths",
                runtime.scenario.inspection_paths,
                button_text="Copy inspection paths",
                object_name="copy_inspection_paths_button",
            )
        details_layout.addStretch(1)

        steps_label = QLabel("Manual steps (tick as you complete):", self)
        layout.addWidget(steps_label)
        self._steps_list = QListWidget(self)
        self._configure_checklist(self._steps_list)
        for step in runtime.scenario.steps:
            item = QListWidgetItem(step, self._steps_list)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            item.setToolTip(step)
        layout.addWidget(self._steps_list, 4)

        expected_label = QLabel("Expected outcomes:", self)
        layout.addWidget(expected_label)
        self._expected_list = QListWidget(self)
        self._configure_checklist(self._expected_list)
        for check in runtime.scenario.expected_checks:
            item = QListWidgetItem(check, self._expected_list)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            item.setToolTip(check)
        layout.addWidget(self._expected_list, 4)

        notes_label = QLabel("Notes:", self)
        layout.addWidget(notes_label)
        self._notes_edit = QPlainTextEdit(self)
        self._notes_edit.setPlaceholderText(
            "Record observations, blockers, and any repro details."
        )
        layout.addWidget(self._notes_edit, 2)

        buttons = QDialogButtonBox(self)
        self._pass_btn = QPushButton("Mark Passed", self)
        self._fail_btn = QPushButton("Mark Failed", self)
        self._close_btn = QPushButton("Cancel", self)
        buttons.addButton(self._pass_btn, QDialogButtonBox.AcceptRole)
        buttons.addButton(self._fail_btn, QDialogButtonBox.DestructiveRole)
        buttons.addButton(self._close_btn, QDialogButtonBox.RejectRole)
        self._pass_btn.setEnabled(False)
        self._pass_btn.clicked.connect(self._mark_passed)
        self._fail_btn.clicked.connect(self._mark_failed)
        self._close_btn.clicked.connect(self._mark_incomplete)
        self._steps_list.itemChanged.connect(lambda _item: self._sync_pass_enabled())
        self._expected_list.itemChanged.connect(lambda _item: self._sync_pass_enabled())
        layout.addWidget(buttons)
        self._sync_pass_enabled()

    def _configure_checklist(self, widget: QListWidget) -> None:
        """Keep long scenario rows readable while modal workflow prompts are open."""
        widget.setWordWrap(True)
        widget.setTextElideMode(Qt.TextElideMode.ElideNone)
        widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    def _add_plain_section(self, layout: QVBoxLayout, title: str, body: str) -> None:
        header = QLabel(f"{title}:", self)
        layout.addWidget(header)
        label = QLabel(body, self)
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.NoTextInteraction)
        layout.addWidget(label)

    def _absolute_fixture_paths(self, paths: tuple[str, ...]) -> tuple[str, ...]:
        absolute_paths: list[str] = []
        for rel_path in paths:
            absolute_paths.append(str((self._project_root / rel_path).resolve()))
        return tuple(absolute_paths)

    def _copy_text(self, text: str) -> None:
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)

    def _add_copy_row(
        self,
        layout: QVBoxLayout,
        title: str,
        body: str,
        *,
        button_text: str,
        object_name: str,
    ) -> None:
        header_row = QWidget(self)
        header_layout = QHBoxLayout(header_row)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)
        header_layout.addWidget(QLabel(f"{title}:", self))
        header_layout.addStretch(1)
        button = QPushButton(button_text, self)
        button.setObjectName(object_name)
        button.clicked.connect(lambda: self._copy_text(body))
        header_layout.addWidget(button)
        layout.addWidget(header_row)
        label = QLabel(body, self)
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.NoTextInteraction)
        layout.addWidget(label)

    def _add_copy_section(
        self,
        layout: QVBoxLayout,
        title: str,
        paths: tuple[str, ...],
        *,
        button_text: str,
        object_name: str,
    ) -> None:
        absolute_paths = self._absolute_fixture_paths(paths)
        body_lines: list[str] = []
        for rel_path, abs_path in zip(paths, absolute_paths, strict=False):
            body_lines.append(f"{rel_path}\n  -> {abs_path}")
        header_row = QWidget(self)
        header_layout = QHBoxLayout(header_row)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)
        header_layout.addWidget(QLabel(f"{title}:", self))
        header_layout.addStretch(1)
        button = QPushButton(button_text, self)
        button.setObjectName(object_name)
        button.clicked.connect(lambda: self._copy_text("\n".join(absolute_paths)))
        header_layout.addWidget(button)
        layout.addWidget(header_row)
        label = QLabel("\n".join(body_lines), self)
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.NoTextInteraction)
        layout.addWidget(label)

    @property
    def final_result(self) -> str | None:
        """Return the final result captured by pass/fail action, if any."""
        return self._final_result

    def _checked_steps(self) -> list[str]:
        checked: list[str] = []
        for idx in range(self._steps_list.count()):
            item = self._steps_list.item(idx)
            if item is None or item.checkState() != Qt.Checked:
                continue
            checked.append(item.text())
        return checked

    def _checked_expected_checks(self) -> list[str]:
        checked: list[str] = []
        for idx in range(self._expected_list.count()):
            item = self._expected_list.item(idx)
            if item is None or item.checkState() != Qt.Checked:
                continue
            checked.append(item.text())
        return checked

    def _all_items_checked(self, widget: QListWidget) -> bool:
        if widget.count() <= 0:
            return False
        for idx in range(widget.count()):
            item = widget.item(idx)
            if item is None or item.checkState() != Qt.Checked:
                return False
        return True

    def _sync_pass_enabled(self) -> None:
        self._pass_btn.setEnabled(
            self._all_items_checked(self._steps_list)
            and self._all_items_checked(self._expected_list)
        )

    def _write_artifact(self, result: str) -> Path:
        self._results_dir.mkdir(parents=True, exist_ok=True)
        stamp_ms = int(time.time() * 1000)
        safe_id = self._runtime.scenario.id.replace("/", "_")
        run_token = str(os.environ.get(SCENARIO_ENV_RUN_TOKEN, "")).strip()
        safe_token = "".join(
            ch if (ch.isalnum() or ch in {"-", "_", "."}) else "_" for ch in run_token
        ).strip("_")
        if safe_token:
            out_path = self._results_dir / f"{safe_id}-{safe_token}-{stamp_ms}.json"
        else:
            out_path = self._results_dir / f"{safe_id}-{stamp_ms}.json"
        payload = {
            "version": self._runtime.version,
            "scenario_id": self._runtime.scenario.id,
            "title": self._runtime.scenario.title,
            "fixture_root": self._runtime.scenario.fixture_root,
            "project_root": self._runtime.project_root,
            "run_token": run_token,
            "result": result,
            "checked_steps": self._checked_steps(),
            "checked_expected_checks": self._checked_expected_checks(),
            "all_steps": list(self._runtime.scenario.steps),
            "expected_checks": list(self._runtime.scenario.expected_checks),
            "notes": self._notes_edit.toPlainText().strip(),
            "completed_at_ms": stamp_ms,
        }
        out_path.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return out_path

    def _finalize(self, result: str) -> None:
        self._write_artifact(result)
        self._final_result = result
        self.accept()

    def _mark_passed(self) -> None:
        if not self._pass_btn.isEnabled():
            return
        self._finalize("passed")

    def _mark_failed(self) -> None:
        self._finalize("failed")

    def _mark_incomplete(self) -> None:
        self._finalize("incomplete")

    def reject(self) -> None:
        """Persist an explicit incomplete result when the dialog is dismissed."""
        if self._final_result is not None:
            super().reject()
            return
        self._mark_incomplete()
