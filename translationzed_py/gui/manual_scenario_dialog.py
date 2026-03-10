"""Checklist dialog for manual UI scenario runs."""

from __future__ import annotations

import json
import time
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from .manual_scenario_runtime import ManualScenarioRuntime


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

        summary = QLabel(
            (
                f"Scenario ID: {runtime.scenario.id}\n"
                f"Fixture: {runtime.scenario.fixture_root}\n"
                f"Project root: {runtime.project_root}"
            ),
            self,
        )
        summary.setTextFormat(Qt.TextFormat.PlainText)
        summary.setWordWrap(True)
        layout.addWidget(summary)

        steps_label = QLabel("Manual steps (tick as you complete):", self)
        layout.addWidget(steps_label)
        self._steps_list = QListWidget(self)
        for step in runtime.scenario.steps:
            item = QListWidgetItem(step, self._steps_list)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
        layout.addWidget(self._steps_list, 2)

        expected_label = QLabel("Expected outcomes:", self)
        layout.addWidget(expected_label)
        self._expected_list = QListWidget(self)
        self._expected_list.setSelectionMode(QListWidget.NoSelection)
        for check in runtime.scenario.expected_checks:
            item = QListWidgetItem(check, self._expected_list)
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
        layout.addWidget(self._expected_list, 2)

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
        self._close_btn = QPushButton("Close", self)
        buttons.addButton(self._pass_btn, QDialogButtonBox.AcceptRole)
        buttons.addButton(self._fail_btn, QDialogButtonBox.DestructiveRole)
        buttons.addButton(self._close_btn, QDialogButtonBox.RejectRole)
        self._pass_btn.clicked.connect(self._mark_passed)
        self._fail_btn.clicked.connect(self._mark_failed)
        self._close_btn.clicked.connect(self.reject)
        layout.addWidget(buttons)

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

    def _write_artifact(self, result: str) -> Path:
        self._results_dir.mkdir(parents=True, exist_ok=True)
        stamp_ms = int(time.time() * 1000)
        safe_id = self._runtime.scenario.id.replace("/", "_")
        out_path = self._results_dir / f"{safe_id}-{stamp_ms}.json"
        payload = {
            "version": self._runtime.version,
            "scenario_id": self._runtime.scenario.id,
            "title": self._runtime.scenario.title,
            "fixture_root": self._runtime.scenario.fixture_root,
            "project_root": self._runtime.project_root,
            "result": result,
            "checked_steps": self._checked_steps(),
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

    def _mark_passed(self) -> None:
        self._write_artifact("passed")
        self._final_result = "passed"
        self.accept()

    def _mark_failed(self) -> None:
        self._write_artifact("failed")
        self._final_result = "failed"
        self.accept()
