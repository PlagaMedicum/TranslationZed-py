"""Test module for conflict service."""

from __future__ import annotations

from translationzed_py.core.conflict_service import (
    ConflictPersistCallbacks,
    ConflictPromptPlan,
    ConflictResolution,
    ConflictWorkflowService,
    apply_entry_updates,
    build_merge_rows,
    build_persist_plan,
    build_prompt_plan,
    build_resolution_run_plan,
    drop_cache_plan,
    drop_original_plan,
    execute_choice,
    execute_merge_resolution,
    execute_persist_resolution,
    merge_plan,
    normalize_choice,
)
from translationzed_py.core.model import Entry, Status


def _entry(key: str, value: str, status: Status = Status.UNTOUCHED) -> Entry:
    return Entry(
        key=key,
        value=value,
        status=status,
        span=(0, 0),
        segments=(),
        gaps=(),
        raw=False,
        key_hash=123,
    )


def test_build_merge_rows_sorts_keys_and_extracts_cache_values() -> None:
    """Verify build merge rows sorts keys and extracts cache values."""
    rows, cache_values = build_merge_rows(
        entries=[_entry("B", "cache-b"), _entry("A", "cache-a"), _entry("C", "c")],
        conflict_originals={"B": "orig-b", "A": "orig-a"},
        sources={"A": "src-a"},
    )

    assert [row.key for row in rows] == ["A", "B"]
    assert rows[0].source_value == "src-a"
    assert rows[1].source_value == ""
    assert cache_values == {"A": "cache-a", "B": "cache-b"}


def test_drop_cache_plan_removes_conflict_keys_from_drafts() -> None:
    """Verify drop cache plan removes conflict keys from drafts."""
    plan = drop_cache_plan(
        changed_keys={"A", "B", "C"},
        baseline_values={"A": "a0", "B": "b0", "C": "c0"},
        conflict_keys={"B"},
    )
    assert set(plan.changed_keys) == {"A", "C"}
    assert plan.original_values["B"] == "b0"
    assert not plan.force_original


def test_drop_original_plan_forces_conflict_keys() -> None:
    """Verify drop original plan forces conflict keys."""
    plan = drop_original_plan(
        changed_keys={"A"},
        baseline_values={"A": "a0"},
        conflict_originals={"B": "b-file"},
    )
    assert set(plan.changed_keys) == {"A"}
    assert plan.original_values["A"] == "a0"
    assert plan.original_values["B"] == "b-file"
    assert set(plan.force_original) == {"B"}


def test_merge_plan_applies_status_rule_for_original_choice() -> None:
    """Verify merge plan applies status rule for original choice."""
    plan = merge_plan(
        changed_keys={"A", "B"},
        baseline_values={"A": "a0", "B": "b0"},
        conflict_originals={"A": "a-file", "B": "b-file"},
        cache_values={"A": "a-cache", "B": "b-cache"},
        resolutions={
            "A": ("a-cache", "cache"),
            "B": ("b-file", "original"),
        },
    )

    assert set(plan.changed_keys) == {"A"}
    assert plan.original_values["A"] == "a-file"
    assert "B" not in plan.original_values or plan.original_values["B"] == "b0"
    assert set(plan.force_original) == {"A"}
    assert "A" not in plan.value_updates
    assert plan.value_updates["B"] == "b-file"
    assert plan.status_updates["B"] == Status.FOR_REVIEW


def test_apply_entry_updates_modifies_only_target_keys() -> None:
    """Verify apply entry updates modifies only target keys."""
    entries = [_entry("A", "a", Status.UNTOUCHED), _entry("B", "b", Status.TRANSLATED)]
    changed = apply_entry_updates(
        entries,
        value_updates={"A": "a2"},
        status_updates={"B": Status.FOR_REVIEW},
    )

    assert changed is True
    assert entries[0].value == "a2"
    assert entries[0].status == Status.UNTOUCHED
    assert entries[1].value == "b"
    assert entries[1].status == Status.FOR_REVIEW
    assert entries[0].key_hash == 123
    assert entries[1].key_hash == 123


def test_conflict_workflow_service_drop_cache_builds_resolution() -> None:
    """Verify conflict workflow service drop cache builds resolution."""
    service = ConflictWorkflowService()
    resolution = service.resolve_drop_cache(
        changed_keys={"A", "B"},
        baseline_values={"A": "a0", "B": "b0"},
        conflict_originals={"B": "b-file"},
    )
    assert isinstance(resolution, ConflictResolution)
    assert set(resolution.changed_keys) == {"A"}
    assert resolution.value_updates == {}
    assert resolution.status_updates == {}


def test_conflict_workflow_service_merge_builds_and_applies_resolution() -> None:
    """Verify conflict workflow service merge builds and applies resolution."""
    service = ConflictWorkflowService()
    resolution = service.resolve_merge(
        changed_keys={"A"},
        baseline_values={"A": "a0"},
        conflict_originals={"A": "a-file"},
        cache_values={"A": "a-cache"},
        resolutions={"A": ("a-file", "original")},
    )

    entries = [_entry("A", "a-cache", Status.TRANSLATED)]
    changed = service.apply_resolution(entries, resolution=resolution)

    assert changed is True
    assert entries[0].value == "a-file"
    assert entries[0].status == Status.FOR_REVIEW


def test_build_prompt_plan_cases() -> None:
    """Verify build prompt plan cases."""
    no_conflict = build_prompt_plan(
        has_conflicts=False,
        is_current_file=True,
        for_save=False,
    )
    assert no_conflict == ConflictPromptPlan(
        require_dialog=False,
        immediate_result=True,
    )

    non_current_open = build_prompt_plan(
        has_conflicts=True,
        is_current_file=False,
        for_save=False,
    )
    assert non_current_open == ConflictPromptPlan(
        require_dialog=False,
        immediate_result=True,
    )

    non_current_save = build_prompt_plan(
        has_conflicts=True,
        is_current_file=False,
        for_save=True,
    )
    assert non_current_save == ConflictPromptPlan(
        require_dialog=False,
        immediate_result=False,
    )

    current = build_prompt_plan(
        has_conflicts=True,
        is_current_file=True,
        for_save=True,
    )
    assert current == ConflictPromptPlan(
        require_dialog=True,
        immediate_result=None,
    )


def test_build_persist_plan_marks_clean_only_when_no_changed_keys() -> None:
    """Verify build persist plan marks clean only when no changed keys."""
    dirty = build_persist_plan(
        ConflictResolution(
            changed_keys=frozenset({"A"}),
            original_values={"A": "a0"},
            force_original=frozenset({"A"}),
            value_updates={},
            status_updates={},
        )
    )
    assert dirty.changed_keys == {"A"}
    assert dirty.mark_file_clean is False
    assert dirty.clear_conflicts is True
    assert dirty.reload_current_file is True

    clean = build_persist_plan(
        ConflictResolution(
            changed_keys=frozenset(),
            original_values={},
            force_original=frozenset(),
            value_updates={},
            status_updates={},
        )
    )
    assert clean.mark_file_clean is True


def test_execute_persist_resolution_executes_callbacks_for_dirty_plan() -> None:
    """Verify execute persist resolution executes callbacks for dirty plan."""
    resolution = ConflictResolution(
        changed_keys=frozenset({"A"}),
        original_values={"A": "a0"},
        force_original=frozenset({"A"}),
        value_updates={},
        status_updates={},
    )
    calls: list[str] = []
    ok = execute_persist_resolution(
        resolution=resolution,
        callbacks=ConflictPersistCallbacks(
            write_cache=lambda _plan: calls.append("write"),
            mark_file_clean=lambda: calls.append("clean"),
            clear_conflicts=lambda: calls.append("clear"),
            reload_current_file=lambda: calls.append("reload"),
        ),
    )
    assert ok is True
    assert calls == ["write", "clear", "reload"]


def test_execute_persist_resolution_executes_mark_clean_when_no_changed() -> None:
    """Verify execute persist resolution executes mark clean when no changed."""
    resolution = ConflictResolution(
        changed_keys=frozenset(),
        original_values={},
        force_original=frozenset(),
        value_updates={},
        status_updates={},
    )
    calls: list[str] = []
    ok = execute_persist_resolution(
        resolution=resolution,
        callbacks=ConflictPersistCallbacks(
            write_cache=lambda _plan: calls.append("write"),
            mark_file_clean=lambda: calls.append("clean"),
            clear_conflicts=lambda: calls.append("clear"),
            reload_current_file=lambda: calls.append("reload"),
        ),
    )
    assert ok is True
    assert calls == ["write", "clean", "clear", "reload"]


def test_normalize_choice_and_service_wrappers() -> None:
    """Verify normalize choice and service wrappers."""
    assert normalize_choice("drop_cache") == "drop_cache"
    assert normalize_choice("drop_original") == "drop_original"
    assert normalize_choice("merge") == "merge"
    assert normalize_choice(None) == "cancel"
    assert normalize_choice("unknown") == "cancel"

    service = ConflictWorkflowService()
    service_plan = service.build_prompt_plan(
        has_conflicts=True,
        is_current_file=True,
        for_save=False,
    )
    assert service_plan.require_dialog is True
    assert service.normalize_choice("merge") == "merge"
    assert (
        service.execute_choice(
            "drop_cache",
            on_drop_cache=lambda: True,
            on_drop_original=lambda: False,
            on_merge=lambda: False,
        )
        is True
    )
    persist = service.build_persist_plan(
        ConflictResolution(
            changed_keys=frozenset(),
            original_values={},
            force_original=frozenset(),
            value_updates={},
            status_updates={},
        )
    )
    assert persist.mark_file_clean is True
    assert (
        service.execute_persist_resolution(
            resolution=ConflictResolution(
                changed_keys=frozenset(),
                original_values={},
                force_original=frozenset(),
                value_updates={},
                status_updates={},
            ),
            callbacks=ConflictPersistCallbacks(
                write_cache=lambda _plan: None,
                mark_file_clean=lambda: None,
                clear_conflicts=lambda: None,
                reload_current_file=lambda: None,
            ),
        )
        is True
    )
    run_plan = service.build_resolution_run_plan(
        action="drop_cache",
        has_current_file=True,
        has_current_model=True,
        is_current_file=True,
        conflict_count=1,
    )
    assert run_plan.run_resolution is True
    merge_exec = service.execute_merge_resolution(
        entries=[_entry("A", "a-cache", Status.TRANSLATED)],
        changed_keys={"A"},
        baseline_values={"A": "a0"},
        conflict_originals={"A": "a-file"},
        sources={"A": "src"},
        request_resolutions=lambda _rows: {"A": ("a-file", "original")},
    )
    assert merge_exec.resolved is True


def test_execute_choice_dispatches_callbacks() -> None:
    """Verify execute choice dispatches callbacks."""
    called: list[str] = []

    assert (
        execute_choice(
            "drop_cache",
            on_drop_cache=lambda: called.append("cache") or True,
            on_drop_original=lambda: called.append("orig") or False,
            on_merge=lambda: called.append("merge") or False,
        )
        is True
    )
    assert called == ["cache"]

    called.clear()
    assert (
        execute_choice(
            "drop_original",
            on_drop_cache=lambda: called.append("cache") or False,
            on_drop_original=lambda: called.append("orig") or True,
            on_merge=lambda: called.append("merge") or False,
        )
        is True
    )
    assert called == ["orig"]

    called.clear()
    assert (
        execute_choice(
            "merge",
            on_drop_cache=lambda: called.append("cache") or False,
            on_drop_original=lambda: called.append("orig") or False,
            on_merge=lambda: called.append("merge") or True,
        )
        is True
    )
    assert called == ["merge"]

    called.clear()
    assert (
        execute_choice(
            None,
            on_drop_cache=lambda: called.append("cache") or True,
            on_drop_original=lambda: called.append("orig") or True,
            on_merge=lambda: called.append("merge") or True,
        )
        is False
    )
    assert called == []


def test_build_resolution_run_plan() -> None:
    """Verify build resolution run plan."""
    blocked = build_resolution_run_plan(
        action="drop_cache",
        has_current_file=False,
        has_current_model=True,
        is_current_file=True,
        conflict_count=1,
    )
    assert blocked.run_resolution is False
    assert blocked.immediate_result is False

    merge_no_conflicts = build_resolution_run_plan(
        action="merge",
        has_current_file=True,
        has_current_model=True,
        is_current_file=True,
        conflict_count=0,
    )
    assert merge_no_conflicts.run_resolution is False
    assert merge_no_conflicts.immediate_result is True

    runnable = build_resolution_run_plan(
        action="drop_original",
        has_current_file=True,
        has_current_model=True,
        is_current_file=True,
        conflict_count=3,
    )
    assert runnable.run_resolution is True
    assert runnable.immediate_result is None


def test_execute_merge_resolution_flow() -> None:
    """Verify execute merge resolution flow."""
    entries = [_entry("A", "a-cache", Status.TRANSLATED)]
    conflict_originals = {"A": "a-file"}
    sources = {"A": "a-src"}
    execution = execute_merge_resolution(
        entries=entries,
        changed_keys={"A"},
        baseline_values={"A": "a0"},
        conflict_originals=conflict_originals,
        sources=sources,
        request_resolutions=lambda _rows: {"A": ("a-file", "original")},
    )
    assert execution.resolved is True
    assert execution.immediate_result is None
    assert execution.resolution is not None
    assert entries[0].value == "a-file"
    assert entries[0].status == Status.FOR_REVIEW


def test_execute_merge_resolution_cancel_and_no_conflicts() -> None:
    """Verify execute merge resolution cancel and no conflicts."""
    entries = [_entry("A", "a-cache", Status.TRANSLATED)]
    canceled = execute_merge_resolution(
        entries=entries,
        changed_keys={"A"},
        baseline_values={"A": "a0"},
        conflict_originals={"A": "a-file"},
        sources={"A": "a-src"},
        request_resolutions=lambda _rows: None,
    )
    assert canceled.resolved is False
    assert canceled.immediate_result is False
    assert canceled.resolution is None

    no_conflict = execute_merge_resolution(
        entries=entries,
        changed_keys={"A"},
        baseline_values={"A": "a0"},
        conflict_originals={},
        sources={},
        request_resolutions=lambda _rows: {"A": ("a-file", "original")},
    )
    assert no_conflict.resolved is False
    assert no_conflict.immediate_result is True
    assert no_conflict.resolution is None
