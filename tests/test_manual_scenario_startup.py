"""Tests for manual scenario startup helper wiring."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt

from translationzed_py.gui import main_window_panel_helpers as helpers
from translationzed_py.gui.manual_scenario_runtime import (
    SCENARIO_ENV_FILE,
    ManualScenario,
    ManualScenarioRuntime,
)


def _runtime_payload(tmp_path: Path) -> Path:
    payload = {
        "version": 1,
        "project_root": str((tmp_path / "project").resolve()),
        "scenario": {
            "id": "demo",
            "title": "Demo",
            "fixture_root": "conflict_manual",
            "selected_locales": ["BE"],
            "steps": ["one"],
            "expected_checks": ["ok"],
            "prefs_extras": {"TZP_STATUS_COMMENT_WRITEBACK": "true"},
            "env_overrides": {},
            "automation_pytest_selectors": ["tests/test_gui_smoke.py"],
        },
    }
    path = tmp_path / "runtime.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def test_prepare_manual_scenario_applies_runtime_locales_and_extras(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Prepare helper should apply selected locales and prefs extras from runtime."""
    runtime_path = _runtime_payload(tmp_path)
    monkeypatch.setenv(SCENARIO_ENV_FILE, str(runtime_path))
    win = SimpleNamespace(_prefs_extras={})
    selected = helpers._prepare_manual_scenario(win, None)
    assert selected == ["BE"]
    assert win._prefs_extras["TZP_STATUS_COMMENT_WRITEBACK"] == "true"
    assert win._manual_scenario_dialog_shown is False
    assert win._manual_scenario_dialog is None
    assert win._manual_scenario_runtime.scenario.id == "demo"


def test_schedule_post_startup_hooks_schedules_dialog_only_for_runtime(
    monkeypatch,
) -> None:
    """Startup hooks should schedule checklist popup only in scenario mode."""
    calls: list[str] = []
    scheduled: list[int] = []

    def _single_shot(ms: int, cb) -> None:  # type: ignore[no-untyped-def]
        scheduled.append(ms)
        cb()

    monkeypatch.setattr(helpers.QTimer, "singleShot", staticmethod(_single_shot))

    win_plain = SimpleNamespace(
        _schedule_post_locale_tasks=lambda: calls.append("plain")
    )
    helpers._schedule_post_startup_hooks(win_plain)
    assert calls == ["plain"]
    assert scheduled == []

    runtime = ManualScenarioRuntime(
        version=1,
        project_root="/tmp/project",
        scenario=ManualScenario(
            id="demo",
            title="Demo",
            fixture_root="conflict_manual",
            selected_locales=("BE",),
            steps=("one",),
            expected_checks=("ok",),
            env_overrides={},
            prefs_extras={},
            automation_pytest_selectors=("tests/test_gui_smoke.py",),
        ),
    )
    win_scenario = SimpleNamespace(
        _schedule_post_locale_tasks=lambda: calls.append("scenario"),
        _manual_scenario_runtime=runtime,
        _manual_scenario_dialog_shown=False,
        statusBar=lambda: SimpleNamespace(showMessage=lambda *_args, **_kwargs: None),
    )
    # Avoid constructing real dialog in this helper test.
    monkeypatch.setattr(helpers, "_show_manual_scenario_dialog", lambda _win: None)
    helpers._schedule_post_startup_hooks(win_scenario)
    assert calls[-1] == "scenario"
    assert scheduled == [0]


def test_show_manual_scenario_dialog_is_modeless_and_reports_result(
    monkeypatch, tmp_path: Path
) -> None:
    """Manual scenario checklist should open modeless and report pass/fail on close."""

    class _Signal:
        def __init__(self) -> None:
            self._callbacks: list = []

        def connect(self, cb):  # type: ignore[no-untyped-def]
            self._callbacks.append(cb)

        def emit(self, value: int) -> None:
            for cb in list(self._callbacks):
                cb(value)

    class _FakeDialog:
        instances: list["_FakeDialog"] = []

        def __init__(self, runtime, *, results_dir: Path, parent) -> None:
            self.runtime = runtime
            self.results_dir = results_dir
            self.parent = parent
            self.final_result: str | None = None
            self.finished = _Signal()
            self.modal: bool | None = None
            self.modality = None
            self.attributes: list[tuple[Qt.WidgetAttribute, bool]] = []
            self.shown = False
            self.raised = False
            self.activated = False
            _FakeDialog.instances.append(self)

        def setModal(self, value: bool) -> None:
            self.modal = value

        def setWindowModality(self, value) -> None:
            self.modality = value

        def setAttribute(self, attr: Qt.WidgetAttribute, on: bool = True) -> None:
            self.attributes.append((attr, on))

        def show(self) -> None:
            self.shown = True

        def raise_(self) -> None:
            self.raised = True

        def activateWindow(self) -> None:
            self.activated = True

        def isVisible(self) -> bool:
            return self.shown

    status_messages: list[tuple[str, int]] = []
    runtime = ManualScenarioRuntime(
        version=1,
        project_root=str((tmp_path / "project").resolve()),
        scenario=ManualScenario(
            id="demo",
            title="Demo",
            fixture_root="conflict_manual",
            selected_locales=("BE",),
            steps=("one",),
            expected_checks=("ok",),
            env_overrides={},
            prefs_extras={},
            automation_pytest_selectors=("tests/test_gui_smoke.py",),
        ),
    )
    win = SimpleNamespace(
        _manual_scenario_runtime=runtime,
        _manual_scenario_dialog_shown=False,
        _manual_scenario_dialog=None,
        statusBar=lambda: SimpleNamespace(
            showMessage=lambda text, timeout: status_messages.append((text, timeout))
        ),
    )
    monkeypatch.setattr(helpers, "ManualScenarioChecklistDialog", _FakeDialog)
    monkeypatch.setattr(
        helpers, "_manual_scenario_results_dir", lambda: tmp_path / "results"
    )

    helpers._show_manual_scenario_dialog(win)

    assert win._manual_scenario_dialog_shown is True
    assert len(_FakeDialog.instances) == 1
    dialog = _FakeDialog.instances[0]
    assert win._manual_scenario_dialog is dialog
    assert dialog.modal is False
    assert dialog.modality == Qt.WindowModality.NonModal
    assert (Qt.WidgetAttribute.WA_DeleteOnClose, True) in dialog.attributes
    assert dialog.shown is True
    assert dialog.raised is True
    assert dialog.activated is True
    assert status_messages == []

    # While visible, repeated calls should focus existing dialog rather than create another.
    helpers._show_manual_scenario_dialog(win)
    assert len(_FakeDialog.instances) == 1

    dialog.final_result = "passed"
    dialog.finished.emit(0)
    assert win._manual_scenario_dialog is None
    assert status_messages == [("Manual scenario 'demo' marked passed.", 8000)]
