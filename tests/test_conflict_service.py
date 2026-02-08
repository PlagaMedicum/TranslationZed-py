from __future__ import annotations

from translationzed_py.core.conflict_service import (
    ConflictResolution,
    ConflictWorkflowService,
    apply_entry_updates,
    build_merge_rows,
    drop_cache_plan,
    drop_original_plan,
    merge_plan,
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
    plan = drop_cache_plan(
        changed_keys={"A", "B", "C"},
        baseline_values={"A": "a0", "B": "b0", "C": "c0"},
        conflict_keys={"B"},
    )
    assert set(plan.changed_keys) == {"A", "C"}
    assert plan.original_values["B"] == "b0"
    assert not plan.force_original


def test_drop_original_plan_forces_conflict_keys() -> None:
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
