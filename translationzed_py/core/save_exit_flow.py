from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Literal


def apply_write_original_flow(
    *,
    write_cache: Callable[[], bool],
    list_draft_files: Callable[[], list[Path]],
    choose_action: Callable[[list[Path]], Literal["cancel", "write", "cache"]],
    save_all: Callable[[list[Path]], None],
    notify_nothing_to_write: Callable[[], None],
) -> None:
    """
    Run the write-original action flow.
    """
    write_cache()
    files = list_draft_files()
    if not files:
        notify_nothing_to_write()
        return
    decision = choose_action(files)
    if decision == "cancel":
        return
    if decision == "write":
        save_all(files)
        return
    write_cache()


def should_accept_close(
    *,
    prompt_write_on_exit: bool,
    write_cache: Callable[[], bool],
    list_draft_files: Callable[[], list[Path]],
    choose_action: Callable[[list[Path]], Literal["cancel", "write", "cache"]],
    save_all: Callable[[Sequence[Path]], None],
) -> bool:
    """
    Run close-decision flow and return whether the window should close.
    """
    write_cache()
    if prompt_write_on_exit:
        files = list_draft_files()
        if files:
            decision = choose_action(files)
            if decision == "cancel":
                return False
            if decision == "write":
                save_all(files)
    return write_cache()
