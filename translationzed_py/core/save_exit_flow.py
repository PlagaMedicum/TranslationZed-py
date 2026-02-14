from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True, slots=True)
class SaveBatchOutcome:
    aborted: bool
    failures: tuple[Path, ...]
    saved_any: bool


@dataclass(frozen=True, slots=True)
class SaveBatchRenderPlan:
    aborted: bool
    warning_message: str | None
    set_saved_status: bool


@dataclass(frozen=True, slots=True)
class SaveExitFlowService:
    def build_save_dialog_labels(
        self, files: Sequence[Path], *, root: Path
    ) -> tuple[str, ...]:
        return build_save_dialog_labels(files, root=root)

    def apply_save_dialog_selection(
        self,
        *,
        files: Sequence[Path],
        labels: Sequence[str],
        selected_labels: Sequence[str] | None,
    ) -> tuple[Path, ...]:
        return apply_save_dialog_selection(
            files=files,
            labels=labels,
            selected_labels=selected_labels,
        )

    def build_save_batch_render_plan(
        self, *, outcome: SaveBatchOutcome, root: Path
    ) -> SaveBatchRenderPlan:
        return build_save_batch_render_plan(outcome=outcome, root=root)

    def apply_write_original_flow(
        self,
        *,
        write_cache: Callable[[], bool],
        list_draft_files: Callable[[], list[Path]],
        choose_action: Callable[[list[Path]], Literal["cancel", "write", "cache"]],
        save_all: Callable[[list[Path]], None],
        notify_nothing_to_write: Callable[[], None],
    ) -> None:
        apply_write_original_flow(
            write_cache=write_cache,
            list_draft_files=list_draft_files,
            choose_action=choose_action,
            save_all=save_all,
            notify_nothing_to_write=notify_nothing_to_write,
        )

    def should_accept_close(
        self,
        *,
        prompt_write_on_exit: bool,
        write_cache: Callable[[], bool],
        list_draft_files: Callable[[], list[Path]],
        choose_action: Callable[[list[Path]], Literal["cancel", "write", "cache"]],
        save_all: Callable[[Sequence[Path]], None],
    ) -> bool:
        return should_accept_close(
            prompt_write_on_exit=prompt_write_on_exit,
            write_cache=write_cache,
            list_draft_files=list_draft_files,
            choose_action=choose_action,
            save_all=save_all,
        )

    def run_save_batch_flow(
        self,
        *,
        files: Sequence[Path],
        current_file: Path | None,
        save_current: Callable[[], bool],
        save_from_cache: Callable[[Path], bool],
    ) -> SaveBatchOutcome:
        return run_save_batch_flow(
            files=files,
            current_file=current_file,
            save_current=save_current,
            save_from_cache=save_from_cache,
        )


def build_save_dialog_labels(files: Sequence[Path], *, root: Path) -> tuple[str, ...]:
    labels: list[str] = []
    for path in files:
        try:
            labels.append(path.relative_to(root).as_posix())
        except ValueError:
            labels.append(path.as_posix())
    return tuple(labels)


def apply_save_dialog_selection(
    *,
    files: Sequence[Path],
    labels: Sequence[str],
    selected_labels: Sequence[str] | None,
) -> tuple[Path, ...]:
    if selected_labels is None:
        return tuple(files)
    selected = set(selected_labels)
    return tuple(
        path for path, label in zip(files, labels, strict=False) if label in selected
    )


def format_save_failures(*, failures: Sequence[Path], root: Path) -> str:
    lines: list[str] = []
    for path in failures:
        try:
            lines.append(path.relative_to(root).as_posix())
        except ValueError:
            lines.append(path.as_posix())
    return "\n".join(lines)


def build_save_batch_render_plan(
    *, outcome: SaveBatchOutcome, root: Path
) -> SaveBatchRenderPlan:
    if outcome.aborted:
        return SaveBatchRenderPlan(
            aborted=True,
            warning_message=None,
            set_saved_status=False,
        )
    if outcome.failures:
        return SaveBatchRenderPlan(
            aborted=False,
            warning_message=format_save_failures(failures=outcome.failures, root=root),
            set_saved_status=False,
        )
    return SaveBatchRenderPlan(
        aborted=False,
        warning_message=None,
        set_saved_status=outcome.saved_any,
    )


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


def run_save_batch_flow(
    *,
    files: Sequence[Path],
    current_file: Path | None,
    save_current: Callable[[], bool],
    save_from_cache: Callable[[Path], bool],
) -> SaveBatchOutcome:
    if not files:
        return SaveBatchOutcome(aborted=False, failures=(), saved_any=False)

    remaining = list(files)
    saved_any = False
    if current_file and current_file in remaining:
        if not save_current():
            return SaveBatchOutcome(aborted=True, failures=(), saved_any=False)
        saved_any = True
        remaining.remove(current_file)

    failures: list[Path] = []
    for path in remaining:
        if save_from_cache(path):
            saved_any = True
        else:
            failures.append(path)
    return SaveBatchOutcome(
        aborted=False,
        failures=tuple(failures),
        saved_any=saved_any,
    )
