"""Local-Git synchronization preview and GUI orchestration contracts."""

from __future__ import annotations

import json
import subprocess
import threading
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog

from translationzed_py.core.git_sync import read_state, resolve_commit, write_state
from translationzed_py.core.git_sync_service import (
    GitSyncMergePlan,
    GitSyncPlanItem,
    resolve_merge_plan,
)
from translationzed_py.core.model import Status
from translationzed_py.gui import MainWindow, git_sync_ui


def _git(root: Path, *args: str) -> str:
    """Run one test-repository Git command."""
    result = subprocess.run(
        ("git", "-C", str(root), *args),
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _project(root: Path, *, initialize_git: bool = False) -> None:
    """Create the smallest two-locale project accepted by MainWindow."""
    for code in ("EN", "BE"):
        locale = root / code
        locale.mkdir(parents=True)
        (locale / "language.txt").write_text(
            f"text = {code},\ncharset = UTF-8,\n",
            encoding="utf-8",
        )
        (locale / "UI.txt").write_text(
            f'A = "{code} old"\n',
            encoding="utf-8",
        )
    if initialize_git:
        _git(root, "init")
        _git(root, "config", "user.email", "tests@example.invalid")
        _git(root, "config", "user.name", "Tests")
        _git(root, "add", ".")
        _git(root, "commit", "-m", "baseline")


def _preview_plan() -> GitSyncMergePlan:
    """Build one comment conflict and one unappliable file conflict."""
    return GitSyncMergePlan(
        baseline="a" * 40,
        head="b" * 40,
        items=(
            GitSyncPlanItem(
                item_id="BE:modified",
                locale="BE",
                source_path="EN/UI.txt",
                target_path="BE/UI.txt",
                key="A",
                kinds=("modified", "comments"),
                base_source="Old",
                head_source="New",
                target_value="Пераклад",
                target_file_value="Пераклад",
                target_status=Status.TRANSLATED,
                base_comments=("-- old",),
                head_comments=("-- new",),
                target_comments=("-- local",),
                default_decision="conflict",
                comment_decision="choose",
                propose_for_review=True,
                conflict_reason="Choose the locale or EN comments.",
            ),
            GitSyncPlanItem(
                item_id="BE:missing",
                locale="BE",
                source_path="EN/New.txt",
                target_path="BE/New.txt",
                key="",
                kinds=("file_missing",),
                base_source=None,
                head_source=None,
                target_value=None,
                target_file_value=None,
                target_status=None,
                default_decision="conflict",
                can_apply=False,
                conflict_reason="No target file exists.",
            ),
        ),
        dirty_paths=("EN/dirty.txt",),
    )


def test_preview_model_requires_explicit_conflict_choices(qtbot) -> None:
    """Enable application only after comments and missing files are resolved."""
    model = git_sync_ui.GitSyncPreviewModel(_preview_plan())

    assert model.unresolved_count() == 2
    assert model.setData(model.index(0, model.COMMENT_COLUMN), "use_en", Qt.EditRole)
    assert model.data(model.index(0, model.DECISION_COLUMN), Qt.EditRole) == "apply"
    assert model.unresolved_count() == 1
    assert model.setData(model.index(1, model.DECISION_COLUMN), "ignore", Qt.EditRole)
    assert model.unresolved_count() == 0

    resolved = git_sync_ui.resolve_merge_plan(model.plan, model.choices())
    assert resolved.advance_baseline is True
    assert [choice.decision for choice in resolved.choices] == ["apply", "ignore"]


def test_preview_dialog_keeps_apply_disabled_until_resolved(qtbot) -> None:
    """Render warnings/details while guarding the cache-only Apply button."""
    dialog = git_sync_ui.GitSyncPreviewDialog(_preview_plan())
    qtbot.addWidget(dialog)

    assert dialog._apply_button.isEnabled() is False
    assert "Previous EN" in dialog.details.toPlainText()
    dialog.model.setData(
        dialog.model.index(0, dialog.model.COMMENT_COLUMN),
        "keep_locale",
        Qt.EditRole,
    )
    dialog.model.setData(
        dialog.model.index(1, dialog.model.DECISION_COLUMN),
        "ignore",
        Qt.EditRole,
    )
    assert dialog._apply_button.isEnabled() is True


def test_prepare_git_sync_reads_saved_baseline_to_local_head(tmp_path: Path) -> None:
    """Build the GUI preview from local commits without inspecting a remote."""
    root = tmp_path / "project"
    _project(root, initialize_git=True)
    baseline = resolve_commit(root)
    write_state(root, baseline=baseline)
    _git(root, "remote", "add", "origin", str(tmp_path / "unused-remote"))
    (root / "EN" / "UI.txt").write_text('A = "EN new"\n', encoding="utf-8")
    _git(root, "commit", "-am", "change EN")

    detection = git_sync_ui.detect_local_head(root)
    locales = {
        code: git_sync_ui.LocaleMeta(code, root / code, code, "utf-8")
        for code in ("EN", "BE")
    }
    prepared = git_sync_ui.prepare_git_sync(
        root,
        locales=locales,
        selected_locales=("BE",),
        en_encoding="utf-8",
        comment_prefix="--",
    )

    assert detection.changed is True
    assert prepared.problem is None
    assert prepared.plan is not None
    assert prepared.plan.baseline == baseline
    assert prepared.plan.head == resolve_commit(root)
    assert [(item.locale, item.key, item.kinds) for item in prepared.plan.items] == [
        ("BE", "A", ("modified",))
    ]


def test_unreachable_saved_commit_offers_recovery_state(tmp_path: Path) -> None:
    """Classify an unavailable local baseline instead of mutating it."""
    root = tmp_path / "project"
    _project(root, initialize_git=True)
    state_path = root / ".tzp" / "cache" / "git_sync_state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        json.dumps({"baseline": "f" * 40, "version": 1}),
        encoding="utf-8",
    )

    detection = git_sync_ui.detect_local_head(root)

    assert detection.problem == "unreachable"
    assert detection.head == resolve_commit(root)
    assert json.loads(state_path.read_text(encoding="utf-8"))["baseline"] == "f" * 40


def test_main_window_installs_general_git_action_without_startup_work(
    qtbot, tmp_path: Path
) -> None:
    """Place the explicit action in General and suppress background work in tests."""
    root = tmp_path / "project"
    _project(root)
    window = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(window)

    controller = window._git_sync_controller
    assert controller.action.objectName() == "git_sync_action"
    assert controller.action in window.menu_general.actions()
    assert controller._future is None


def test_detection_job_runs_outside_qt_thread(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    """Keep even the lightweight local-HEAD check off the GUI thread."""
    root = tmp_path / "project"
    _project(root)
    window = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(window)
    worker_threads: list[int] = []

    def _detect(_root: Path) -> git_sync_ui.GitSyncDetection:
        worker_threads.append(threading.get_ident())
        return git_sync_ui.GitSyncDetection(problem="missing")

    monkeypatch.setattr(git_sync_ui, "detect_local_head", _detect)
    window._git_sync_controller.detect()
    qtbot.waitUntil(lambda: window._git_sync_controller._future is None, timeout=2000)

    assert worker_threads
    assert worker_threads[0] != threading.get_ident()


def test_preview_cancel_does_not_start_application(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    """Leave synchronization effects untouched when the preview is cancelled."""
    root = tmp_path / "project"
    _project(root)
    window = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(window)
    applied: list[bool] = []

    class _CancelledDialog:
        def __init__(self, _plan, _parent) -> None:
            pass

        def exec(self) -> int:
            return int(QDialog.Rejected)

    monkeypatch.setattr(git_sync_ui, "GitSyncPreviewDialog", _CancelledDialog)
    monkeypatch.setattr(
        git_sync_ui,
        "apply_resolved_plan",
        lambda *_args, **_kwargs: applied.append(True),
    )

    window._git_sync_controller._show_preparation(
        git_sync_ui.GitSyncPreparation(plan=_preview_plan())
    )

    assert applied == []
    assert window._git_sync_controller._future is None


def test_async_apply_refreshes_open_file_without_writing_original(
    qtbot, tmp_path: Path
) -> None:
    """Apply review status off-thread and reload the affected open table safely."""
    root = tmp_path / "project"
    _project(root, initialize_git=True)
    baseline = resolve_commit(root)
    write_state(root, baseline=baseline)
    (root / "EN" / "UI.txt").write_text('A = "EN new"\n', encoding="utf-8")
    _git(root, "commit", "-am", "change EN")
    original = (root / "BE" / "UI.txt").read_bytes()
    window = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(window)
    target_index = window.fs_model.index_for_path(root / "BE" / "UI.txt")
    window._file_chosen(target_index)
    prepared = git_sync_ui.prepare_git_sync(
        root,
        locales=dict(window._locales),
        selected_locales=("BE",),
        en_encoding=window._locales["EN"].charset,
        comment_prefix=window._app_config.comment_prefix,
    )
    assert prepared.plan is not None

    window._git_sync_controller._start_apply(resolve_merge_plan(prepared.plan))
    qtbot.waitUntil(lambda: window._git_sync_controller._future is None, timeout=3000)

    state = read_state(root)
    assert state is not None
    assert state.baseline == resolve_commit(root)
    assert window._current_model.status_for_row(0) is Status.FOR_REVIEW
    assert (root / "BE" / "UI.txt").read_bytes() == original
