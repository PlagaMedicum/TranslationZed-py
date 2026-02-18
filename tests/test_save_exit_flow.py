"""Test module for save exit flow."""

from __future__ import annotations

from pathlib import Path

from translationzed_py.core.save_exit_flow import (
    SaveBatchOutcome,
    SaveExitFlowService,
    apply_save_dialog_selection,
    apply_write_original_flow,
    build_save_batch_render_plan,
    build_save_dialog_labels,
    format_save_failures,
    run_save_batch_flow,
    should_accept_close,
)


def test_apply_write_original_flow_shows_nothing_to_write_when_empty() -> None:
    """Verify apply write original flow shows nothing to write when empty."""
    events: list[str] = []

    def _write_cache() -> bool:
        events.append("cache")
        return True

    def _drafts() -> list[Path]:
        events.append("drafts")
        return []

    def _choose(_files: list[Path]) -> str:
        events.append("choose")
        return "write"

    def _save(_files: list[Path]) -> None:
        events.append("save")

    def _notify() -> None:
        events.append("notify")

    apply_write_original_flow(
        write_cache=_write_cache,
        list_draft_files=_drafts,
        choose_action=_choose,
        save_all=_save,
        notify_nothing_to_write=_notify,
    )

    assert events == ["cache", "drafts", "notify"]


def test_apply_write_original_flow_write_calls_save_once() -> None:
    """Verify apply write original flow write calls save once."""
    events: list[str] = []
    files = [Path("BE/ui.txt")]

    def _write_cache() -> bool:
        events.append("cache")
        return True

    def _drafts() -> list[Path]:
        events.append("drafts")
        return files

    def _choose(_files: list[Path]) -> str:
        events.append("choose")
        return "write"

    def _save(_files: list[Path]) -> None:
        events.append("save")

    def _notify() -> None:
        events.append("notify")

    apply_write_original_flow(
        write_cache=_write_cache,
        list_draft_files=_drafts,
        choose_action=_choose,
        save_all=_save,
        notify_nothing_to_write=_notify,
    )

    assert events == ["cache", "drafts", "choose", "save"]


def test_should_accept_close_blocks_on_cancel() -> None:
    """Verify should accept close blocks on cancel."""
    events: list[str] = []
    files = [Path("BE/ui.txt")]

    def _write_cache() -> bool:
        events.append("cache")
        return True

    def _drafts() -> list[Path]:
        events.append("drafts")
        return files

    def _choose(_files: list[Path]) -> str:
        events.append("choose")
        return "cancel"

    def _save(_files: list[Path]) -> None:
        events.append("save")

    accepted = should_accept_close(
        prompt_write_on_exit=True,
        write_cache=_write_cache,
        list_draft_files=_drafts,
        choose_action=_choose,
        save_all=_save,
    )

    assert accepted is False
    assert events == ["cache", "drafts", "choose"]


def test_should_accept_close_with_write_runs_final_cache_check() -> None:
    """Verify should accept close with write runs final cache check."""
    events: list[str] = []
    files = [Path("BE/ui.txt")]

    def _write_cache() -> bool:
        events.append("cache")
        return True

    def _drafts() -> list[Path]:
        events.append("drafts")
        return files

    def _choose(_files: list[Path]) -> str:
        events.append("choose")
        return "write"

    def _save(_files: list[Path]) -> None:
        events.append("save")

    accepted = should_accept_close(
        prompt_write_on_exit=True,
        write_cache=_write_cache,
        list_draft_files=_drafts,
        choose_action=_choose,
        save_all=_save,
    )

    assert accepted is True
    assert events == ["cache", "drafts", "choose", "save", "cache"]


def test_should_accept_close_returns_false_on_final_cache_failure() -> None:
    """Verify should accept close returns false on final cache failure."""
    calls = {"cache": 0}

    def _write_cache() -> bool:
        calls["cache"] += 1
        return calls["cache"] == 1

    accepted = should_accept_close(
        prompt_write_on_exit=False,
        write_cache=_write_cache,
        list_draft_files=lambda: [],
        choose_action=lambda _files: "cache",
        save_all=lambda _files: None,
    )

    assert accepted is False
    assert calls["cache"] == 2


def test_run_save_batch_flow_empty_files() -> None:
    """Verify run save batch flow empty files."""
    outcome = run_save_batch_flow(
        files=[],
        current_file=None,
        save_current=lambda: True,
        save_from_cache=lambda _path: True,
    )
    assert outcome.aborted is False
    assert outcome.failures == ()
    assert outcome.saved_any is False


def test_run_save_batch_flow_aborts_when_current_save_fails() -> None:
    """Verify run save batch flow aborts when current save fails."""
    calls: list[str] = []
    files = [Path("BE/current.txt"), Path("BE/other.txt")]

    def _save_current() -> bool:
        calls.append("current")
        return False

    outcome = run_save_batch_flow(
        files=files,
        current_file=Path("BE/current.txt"),
        save_current=_save_current,
        save_from_cache=lambda _path: calls.append("cache") is None or True,
    )
    assert outcome.aborted is True
    assert outcome.failures == ()
    assert outcome.saved_any is False
    assert calls == ["current"]


def test_run_save_batch_flow_collects_failures() -> None:
    """Verify run save batch flow collects failures."""
    calls: list[str] = []
    files = [Path("BE/current.txt"), Path("BE/a.txt"), Path("BE/b.txt")]

    def _save_cache(path: Path) -> bool:
        calls.append(path.name)
        return path.name != "b.txt"

    outcome = run_save_batch_flow(
        files=files,
        current_file=Path("BE/current.txt"),
        save_current=lambda: True,
        save_from_cache=_save_cache,
    )
    assert outcome.aborted is False
    assert outcome.saved_any is True
    assert outcome.failures == (Path("BE/b.txt"),)
    assert calls == ["a.txt", "b.txt"]


def test_build_save_dialog_labels_prefers_root_relative_paths() -> None:
    """Verify build save dialog labels prefers root relative paths."""
    root = Path("/tmp/proj")
    files = [root / "BE" / "ui.txt", Path("/outside/menu.txt")]

    labels = build_save_dialog_labels(files, root=root)

    assert labels == ("BE/ui.txt", "/outside/menu.txt")


def test_apply_save_dialog_selection_uses_selected_labels() -> None:
    """Verify apply save dialog selection uses selected labels."""
    files = [Path("BE/a.txt"), Path("BE/b.txt")]
    labels = ("BE/a.txt", "BE/b.txt")

    selected = apply_save_dialog_selection(
        files=files,
        labels=labels,
        selected_labels=["BE/b.txt"],
    )
    all_files = apply_save_dialog_selection(
        files=files,
        labels=labels,
        selected_labels=None,
    )

    assert selected == (Path("BE/b.txt"),)
    assert all_files == tuple(files)


def test_format_save_failures_renders_root_relative_lines() -> None:
    """Verify format save failures renders root relative lines."""
    root = Path("/tmp/proj")
    message = format_save_failures(
        failures=[root / "BE" / "ui.txt", Path("/outside/menu.txt")],
        root=root,
    )

    assert message == "BE/ui.txt\n/outside/menu.txt"


def test_build_save_batch_render_plan_for_aborted_outcome() -> None:
    """Verify build save batch render plan for aborted outcome."""
    plan = build_save_batch_render_plan(
        outcome=SaveBatchOutcome(aborted=True, failures=(), saved_any=False),
        root=Path("/tmp/proj"),
    )
    assert plan.aborted is True
    assert plan.warning_message is None
    assert plan.set_saved_status is False


def test_build_save_batch_render_plan_for_failures() -> None:
    """Verify build save batch render plan for failures."""
    root = Path("/tmp/proj")
    plan = build_save_batch_render_plan(
        outcome=SaveBatchOutcome(
            aborted=False,
            failures=(root / "BE" / "ui.txt",),
            saved_any=True,
        ),
        root=root,
    )
    assert plan.aborted is False
    assert plan.warning_message == "BE/ui.txt"
    assert plan.set_saved_status is False


def test_build_save_batch_render_plan_for_clean_success() -> None:
    """Verify build save batch render plan for clean success."""
    plan = build_save_batch_render_plan(
        outcome=SaveBatchOutcome(aborted=False, failures=(), saved_any=True),
        root=Path("/tmp/proj"),
    )
    assert plan.aborted is False
    assert plan.warning_message is None
    assert plan.set_saved_status is True


def test_save_exit_flow_service_wraps_helper_calls() -> None:
    """Verify save exit flow service wraps helper calls."""
    service = SaveExitFlowService()
    root = Path("/tmp/proj")
    files = [root / "BE" / "a.txt"]
    labels = service.build_save_dialog_labels(files, root=root)
    selected = service.apply_save_dialog_selection(
        files=files,
        labels=labels,
        selected_labels=["BE/a.txt"],
    )
    outcome = service.run_save_batch_flow(
        files=selected,
        current_file=None,
        save_current=lambda: True,
        save_from_cache=lambda _path: True,
    )
    render = service.build_save_batch_render_plan(outcome=outcome, root=root)
    assert labels == ("BE/a.txt",)
    assert selected == (root / "BE" / "a.txt",)
    assert outcome.saved_any is True
    assert render.set_saved_status is True
