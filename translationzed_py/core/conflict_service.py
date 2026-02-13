from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Literal

from .model import EntrySequence, Status


@dataclass(frozen=True, slots=True)
class ConflictMergeRow:
    key: str
    source_value: str
    original_value: str
    cache_value: str


@dataclass(frozen=True, slots=True)
class ConflictCachePlan:
    changed_keys: frozenset[str]
    original_values: dict[str, str]
    force_original: frozenset[str]


@dataclass(frozen=True, slots=True)
class ConflictMergePlan:
    changed_keys: frozenset[str]
    original_values: dict[str, str]
    force_original: frozenset[str]
    value_updates: dict[str, str]
    status_updates: dict[str, Status]


@dataclass(frozen=True, slots=True)
class ConflictResolution:
    changed_keys: frozenset[str]
    original_values: dict[str, str]
    force_original: frozenset[str]
    value_updates: dict[str, str]
    status_updates: dict[str, Status]


@dataclass(frozen=True, slots=True)
class ConflictPersistPlan:
    changed_keys: frozenset[str]
    original_values: dict[str, str]
    force_original: frozenset[str]
    mark_file_clean: bool
    clear_conflicts: bool
    reload_current_file: bool


@dataclass(frozen=True, slots=True)
class ConflictPersistCallbacks:
    write_cache: Callable[[ConflictPersistPlan], object]
    mark_file_clean: Callable[[], object]
    clear_conflicts: Callable[[], object]
    reload_current_file: Callable[[], object]


@dataclass(frozen=True, slots=True)
class ConflictMergeExecution:
    resolved: bool
    immediate_result: bool | None
    resolution: ConflictResolution | None


@dataclass(frozen=True, slots=True)
class ConflictResolutionRunPlan:
    run_resolution: bool
    immediate_result: bool | None


@dataclass(frozen=True, slots=True)
class ConflictPromptPlan:
    require_dialog: bool
    immediate_result: bool | None


@dataclass(frozen=True, slots=True)
class ConflictWorkflowService:
    def resolve_drop_cache(
        self,
        *,
        changed_keys: Iterable[str],
        baseline_values: Mapping[str, str],
        conflict_originals: Mapping[str, str],
    ) -> ConflictResolution:
        plan = drop_cache_plan(
            changed_keys=changed_keys,
            baseline_values=baseline_values,
            conflict_keys=conflict_originals,
        )
        return ConflictResolution(
            changed_keys=plan.changed_keys,
            original_values=plan.original_values,
            force_original=plan.force_original,
            value_updates={},
            status_updates={},
        )

    def resolve_drop_original(
        self,
        *,
        changed_keys: Iterable[str],
        baseline_values: Mapping[str, str],
        conflict_originals: Mapping[str, str],
    ) -> ConflictResolution:
        plan = drop_original_plan(
            changed_keys=changed_keys,
            baseline_values=baseline_values,
            conflict_originals=conflict_originals,
        )
        return ConflictResolution(
            changed_keys=plan.changed_keys,
            original_values=plan.original_values,
            force_original=plan.force_original,
            value_updates={},
            status_updates={},
        )

    def resolve_merge(
        self,
        *,
        changed_keys: Iterable[str],
        baseline_values: Mapping[str, str],
        conflict_originals: Mapping[str, str],
        cache_values: Mapping[str, str],
        resolutions: Mapping[str, tuple[str, Literal["original", "cache"]]],
    ) -> ConflictResolution:
        plan = merge_plan(
            changed_keys=changed_keys,
            baseline_values=baseline_values,
            conflict_originals=conflict_originals,
            cache_values=cache_values,
            resolutions=resolutions,
        )
        return ConflictResolution(
            changed_keys=plan.changed_keys,
            original_values=plan.original_values,
            force_original=plan.force_original,
            value_updates=plan.value_updates,
            status_updates=plan.status_updates,
        )

    def apply_resolution(
        self,
        entries: EntrySequence,
        *,
        resolution: ConflictResolution,
    ) -> bool:
        return apply_entry_updates(
            entries,
            value_updates=resolution.value_updates,
            status_updates=resolution.status_updates,
        )

    def build_prompt_plan(
        self,
        *,
        has_conflicts: bool,
        is_current_file: bool,
        for_save: bool,
    ) -> ConflictPromptPlan:
        return build_prompt_plan(
            has_conflicts=has_conflicts,
            is_current_file=is_current_file,
            for_save=for_save,
        )

    def normalize_choice(
        self, choice: str | None
    ) -> Literal["drop_cache", "drop_original", "merge", "cancel"]:
        return normalize_choice(choice)

    def execute_choice(
        self,
        choice: str | None,
        *,
        on_drop_cache: Callable[[], bool],
        on_drop_original: Callable[[], bool],
        on_merge: Callable[[], bool],
    ) -> bool:
        return execute_choice(
            choice,
            on_drop_cache=on_drop_cache,
            on_drop_original=on_drop_original,
            on_merge=on_merge,
        )

    def build_persist_plan(self, resolution: ConflictResolution) -> ConflictPersistPlan:
        return build_persist_plan(resolution)

    def execute_persist_resolution(
        self,
        *,
        resolution: ConflictResolution,
        callbacks: ConflictPersistCallbacks,
    ) -> bool:
        return execute_persist_resolution(
            resolution=resolution,
            callbacks=callbacks,
        )

    def execute_merge_resolution(
        self,
        *,
        entries: EntrySequence,
        changed_keys: Iterable[str],
        baseline_values: Mapping[str, str],
        conflict_originals: Mapping[str, str],
        sources: Mapping[str, str],
        request_resolutions: Callable[
            [list[ConflictMergeRow]],
            Mapping[str, tuple[str, Literal["original", "cache"]]] | None,
        ],
    ) -> ConflictMergeExecution:
        return execute_merge_resolution(
            entries=entries,
            changed_keys=changed_keys,
            baseline_values=baseline_values,
            conflict_originals=conflict_originals,
            sources=sources,
            request_resolutions=request_resolutions,
        )

    def build_resolution_run_plan(
        self,
        *,
        action: Literal["drop_cache", "drop_original", "merge"],
        has_current_file: bool,
        has_current_model: bool,
        is_current_file: bool,
        conflict_count: int,
    ) -> ConflictResolutionRunPlan:
        return build_resolution_run_plan(
            action=action,
            has_current_file=has_current_file,
            has_current_model=has_current_model,
            is_current_file=is_current_file,
            conflict_count=conflict_count,
        )


def build_merge_rows(
    entries: EntrySequence,
    conflict_originals: Mapping[str, str],
    sources: Mapping[str, str],
) -> tuple[list[ConflictMergeRow], dict[str, str]]:
    cache_values = {
        entry.key: entry.value for entry in entries if entry.key in conflict_originals
    }
    rows = [
        ConflictMergeRow(
            key=key,
            source_value=sources.get(key, ""),
            original_value=conflict_originals.get(key, ""),
            cache_value=cache_values.get(key, ""),
        )
        for key in sorted(conflict_originals)
    ]
    return rows, cache_values


def drop_cache_plan(
    *,
    changed_keys: Iterable[str],
    baseline_values: Mapping[str, str],
    conflict_keys: Iterable[str],
) -> ConflictCachePlan:
    remaining_changed = set(changed_keys) - set(conflict_keys)
    return ConflictCachePlan(
        changed_keys=frozenset(remaining_changed),
        original_values=dict(baseline_values),
        force_original=frozenset(),
    )


def drop_original_plan(
    *,
    changed_keys: Iterable[str],
    baseline_values: Mapping[str, str],
    conflict_originals: Mapping[str, str],
) -> ConflictCachePlan:
    originals = dict(baseline_values)
    originals.update(conflict_originals)
    return ConflictCachePlan(
        changed_keys=frozenset(changed_keys),
        original_values=originals,
        force_original=frozenset(conflict_originals),
    )


def merge_plan(
    *,
    changed_keys: Iterable[str],
    baseline_values: Mapping[str, str],
    conflict_originals: Mapping[str, str],
    cache_values: Mapping[str, str],
    resolutions: Mapping[str, tuple[str, Literal["original", "cache"]]],
) -> ConflictMergePlan:
    merged_changed = set(changed_keys)
    originals = dict(baseline_values)
    keep_conflict: set[str] = set()
    value_updates: dict[str, str] = {}
    status_updates: dict[str, Status] = {}
    for key, (chosen_value, choice) in resolutions.items():
        if key not in conflict_originals:
            continue
        original_value = conflict_originals.get(key, "")
        if chosen_value == original_value:
            merged_changed.discard(key)
        else:
            merged_changed.add(key)
            originals[key] = original_value
            keep_conflict.add(key)
        if chosen_value != cache_values.get(key, ""):
            value_updates[key] = chosen_value
        if choice == "original":
            status_updates[key] = Status.FOR_REVIEW
    return ConflictMergePlan(
        changed_keys=frozenset(merged_changed),
        original_values=originals,
        force_original=frozenset(keep_conflict),
        value_updates=value_updates,
        status_updates=status_updates,
    )


def apply_entry_updates(
    entries: EntrySequence,
    *,
    value_updates: Mapping[str, str],
    status_updates: Mapping[str, Status],
) -> bool:
    if not value_updates and not status_updates:
        return False
    updated = False
    for idx, entry in enumerate(entries):
        if entry.key not in value_updates and entry.key not in status_updates:
            continue
        new_value = value_updates.get(entry.key, entry.value)
        new_status = status_updates.get(entry.key, entry.status)
        if new_value == entry.value and new_status == entry.status:
            continue
        entries[idx] = type(entry)(
            entry.key,
            new_value,
            new_status,
            entry.span,
            entry.segments,
            entry.gaps,
            entry.raw,
            getattr(entry, "key_hash", None),
        )
        updated = True
    return updated


def build_prompt_plan(
    *,
    has_conflicts: bool,
    is_current_file: bool,
    for_save: bool,
) -> ConflictPromptPlan:
    if not has_conflicts:
        return ConflictPromptPlan(require_dialog=False, immediate_result=True)
    if not is_current_file:
        return ConflictPromptPlan(
            require_dialog=False,
            immediate_result=not for_save,
        )
    return ConflictPromptPlan(require_dialog=True, immediate_result=None)


def build_persist_plan(resolution: ConflictResolution) -> ConflictPersistPlan:
    return ConflictPersistPlan(
        changed_keys=resolution.changed_keys,
        original_values=resolution.original_values,
        force_original=resolution.force_original,
        mark_file_clean=not resolution.changed_keys,
        clear_conflicts=True,
        reload_current_file=True,
    )


def execute_persist_resolution(
    *,
    resolution: ConflictResolution,
    callbacks: ConflictPersistCallbacks,
) -> bool:
    plan = build_persist_plan(resolution)
    callbacks.write_cache(plan)
    if plan.mark_file_clean:
        callbacks.mark_file_clean()
    if plan.clear_conflicts:
        callbacks.clear_conflicts()
    if plan.reload_current_file:
        callbacks.reload_current_file()
    return True


def build_resolution_run_plan(
    *,
    action: Literal["drop_cache", "drop_original", "merge"],
    has_current_file: bool,
    has_current_model: bool,
    is_current_file: bool,
    conflict_count: int,
) -> ConflictResolutionRunPlan:
    if not has_current_file or not has_current_model or not is_current_file:
        return ConflictResolutionRunPlan(
            run_resolution=False,
            immediate_result=False,
        )
    if action == "merge" and conflict_count <= 0:
        return ConflictResolutionRunPlan(
            run_resolution=False,
            immediate_result=True,
        )
    return ConflictResolutionRunPlan(
        run_resolution=True,
        immediate_result=None,
    )


def execute_merge_resolution(
    *,
    entries: EntrySequence,
    changed_keys: Iterable[str],
    baseline_values: Mapping[str, str],
    conflict_originals: Mapping[str, str],
    sources: Mapping[str, str],
    request_resolutions: Callable[
        [list[ConflictMergeRow]],
        Mapping[str, tuple[str, Literal["original", "cache"]]] | None,
    ],
) -> ConflictMergeExecution:
    if not conflict_originals:
        return ConflictMergeExecution(
            resolved=False,
            immediate_result=True,
            resolution=None,
        )
    rows, cache_values = build_merge_rows(entries, conflict_originals, sources)
    resolutions = request_resolutions(rows)
    if not resolutions:
        return ConflictMergeExecution(
            resolved=False,
            immediate_result=False,
            resolution=None,
        )
    plan = merge_plan(
        changed_keys=changed_keys,
        baseline_values=baseline_values,
        conflict_originals=conflict_originals,
        cache_values=cache_values,
        resolutions=resolutions,
    )
    resolution = ConflictResolution(
        changed_keys=plan.changed_keys,
        original_values=plan.original_values,
        force_original=plan.force_original,
        value_updates=plan.value_updates,
        status_updates=plan.status_updates,
    )
    apply_entry_updates(
        entries,
        value_updates=resolution.value_updates,
        status_updates=resolution.status_updates,
    )
    return ConflictMergeExecution(
        resolved=True,
        immediate_result=None,
        resolution=resolution,
    )


def execute_choice(
    choice: str | None,
    *,
    on_drop_cache: Callable[[], bool],
    on_drop_original: Callable[[], bool],
    on_merge: Callable[[], bool],
) -> bool:
    action = normalize_choice(choice)
    if action == "drop_cache":
        return on_drop_cache()
    if action == "drop_original":
        return on_drop_original()
    if action == "merge":
        return on_merge()
    return False


def normalize_choice(
    choice: str | None,
) -> Literal["drop_cache", "drop_original", "merge", "cancel"]:
    if choice == "drop_cache":
        return "drop_cache"
    if choice == "drop_original":
        return "drop_original"
    if choice == "merge":
        return "merge"
    return "cancel"
