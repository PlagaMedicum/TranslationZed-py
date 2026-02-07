from __future__ import annotations

from pathlib import Path

from translationzed_py.core.save_exit_flow import (
    apply_write_original_flow,
    should_accept_close,
)


def test_apply_write_original_flow_shows_nothing_to_write_when_empty() -> None:
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
