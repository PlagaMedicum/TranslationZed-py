"""Test module for project session."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import translationzed_py.core.project_session as project_session_module
import translationzed_py.core.session_resume as session_resume_module
import translationzed_py.core.status_cache as status_cache
from translationzed_py.core.model import Entry, Status
from translationzed_py.core.project_session import (
    CacheMigrationBatchCallbacks,
    CacheMigrationBatchExecution,
    CacheMigrationBatchPlan,
    CacheMigrationScheduleCallbacks,
    CacheMigrationScheduleExecution,
    CacheMigrationSchedulePlan,
    CrashRecoveryAffectedFile,
    CrashRecoveryApplyExecution,
    CrashRecoveryApplyPlan,
    CrashRecoveryDetectionPlan,
    CrashRecoveryReport,
    LocaleResetPlan,
    LocaleSelectionPlan,
    LocaleSwitchPlan,
    OrphanCacheWarningPlan,
    PostLocaleStartupPlan,
    ProjectSessionService,
    SessionResumeSnapshot,
    TreeRebuildPlan,
    apply_locale_reset_plan,
    build_cache_migration_batch_plan,
    build_cache_migration_schedule_plan,
    build_crash_recovery_apply_plan,
    build_crash_recovery_detection_plan,
    build_crash_recovery_report,
    build_locale_reset_plan,
    build_locale_selection_plan,
    build_locale_switch_plan,
    build_orphan_cache_warning,
    build_post_locale_startup_plan,
    build_tree_rebuild_plan,
    collect_draft_files,
    collect_orphan_cache_paths,
    execute_cache_migration_batch,
    execute_cache_migration_schedule,
    execute_crash_recovery_apply_plan,
    find_last_opened_file,
    normalize_selected_locales,
    resolve_requested_locales,
    run_post_locale_startup_tasks,
    use_lazy_tree,
)


def _touch(path: Path, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _session_resume_payload(**updates: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "version": session_resume_module.SESSION_RESUME_VERSION,
        "generated_at_ms": 1,
        "selected_locales": ["BE"],
        "active_file_relpath": "BE/a.txt",
        "active_row": 0,
        "left_panel_index": 0,
        "detail_visible": True,
        "search_text": "",
        "replace_text": "",
        "search_case_sensitive": False,
        "tm_min_score": 50,
        "tm_grouping_mode": "none",
        "tm_origin_project": True,
        "tm_origin_import": True,
    }
    payload.update(updates)
    return payload


def _entry(key: str, value: str, status: Status) -> Entry:
    return Entry(
        key=key,
        value=value,
        status=status,
        span=(0, 0),
        segments=(),
        gaps=(),
    )


def _write_cache_fixture(
    root: Path,
    file_path: Path,
    *,
    draft_keys: tuple[str, ...],
    status_only_keys: tuple[str, ...],
) -> None:
    entries: list[Entry] = []
    for key in draft_keys:
        entries.append(_entry(key, f"{key}_draft", Status.FOR_REVIEW))
    for key in status_only_keys:
        entries.append(_entry(key, f"{key}_stable", Status.TRANSLATED))
    status_cache.write(
        root,
        file_path,
        entries,
        changed_keys=set(draft_keys),
        last_opened=1,
    )


def test_collect_draft_files_filters_by_opened_and_locale(tmp_path: Path) -> None:
    """Verify collect draft files filters by opened and locale."""
    root = tmp_path / "proj"
    _touch(root / "BE" / "a.txt")
    _touch(root / "BE" / "b.txt")
    _touch(root / "RU" / "c.txt")
    _touch(root / ".tzp" / "cache" / "BE" / "a.bin")
    _touch(root / ".tzp" / "cache" / "BE" / "b.bin")
    _touch(root / ".tzp" / "cache" / "RU" / "c.bin")

    drafts = {
        root / ".tzp" / "cache" / "BE" / "a.bin",
        root / ".tzp" / "cache" / "RU" / "c.bin",
    }

    files = collect_draft_files(
        root=root,
        cache_dir=".tzp/cache",
        cache_ext=".bin",
        translation_ext=".txt",
        has_drafts=lambda cache_path: cache_path in drafts,
        locales=["BE", "RU"],
        opened_files={root / "BE" / "a.txt", root / "RU" / "c.txt"},
    )
    assert files == [root / "BE" / "a.txt", root / "RU" / "c.txt"]


def test_json_cache_identity_survives_session_recovery_mapping(tmp_path: Path) -> None:
    """JSON draft and last-opened scans must resolve the original JSON file."""
    root = tmp_path / "proj"
    original = root / "BE" / "UI.json"
    cache = root / ".tzp" / "cache" / "BE" / "UI.json.bin"
    _touch(original, '{"A": "Адзін"}')
    _touch(cache)

    files = collect_draft_files(
        root=root,
        cache_dir=".tzp/cache",
        cache_ext=".bin",
        translation_ext=".txt",
        has_drafts=lambda path: path == cache,
        locales=["BE"],
    )
    latest, scanned = find_last_opened_file(
        root=root,
        cache_dir=".tzp/cache",
        cache_ext=".bin",
        translation_ext=".txt",
        selected_locales=["BE"],
        read_last_opened=lambda path: 42 if path == cache else 0,
    )
    orphans = collect_orphan_cache_paths(
        root=root,
        cache_dir=".tzp/cache",
        cache_ext=".bin",
        translation_ext=".txt",
        selected_locales=["BE"],
    )

    assert files == [original]
    assert (latest, scanned) == (original, 1)
    assert orphans == {}


def test_collect_draft_files_skips_missing_originals(tmp_path: Path) -> None:
    """Verify collect draft files skips missing originals."""
    root = tmp_path / "proj"
    _touch(root / ".tzp" / "cache" / "BE" / "ghost.bin")

    files = collect_draft_files(
        root=root,
        cache_dir=".tzp/cache",
        cache_ext=".bin",
        translation_ext=".txt",
        has_drafts=lambda _path: True,
    )
    assert files == []


def test_find_last_opened_file_selects_latest_timestamp(tmp_path: Path) -> None:
    """Verify find last opened file selects latest timestamp."""
    root = tmp_path / "proj"
    _touch(root / "BE" / "a.txt")
    _touch(root / "BE" / "b.txt")
    _touch(root / ".tzp" / "cache" / "BE" / "a.bin")
    _touch(root / ".tzp" / "cache" / "BE" / "b.bin")

    timestamps = {
        root / ".tzp" / "cache" / "BE" / "a.bin": 10,
        root / ".tzp" / "cache" / "BE" / "b.bin": 20,
    }
    best, scanned = find_last_opened_file(
        root=root,
        cache_dir=".tzp/cache",
        cache_ext=".bin",
        translation_ext=".txt",
        selected_locales=["BE"],
        read_last_opened=lambda cache_path: timestamps.get(cache_path, 0),
    )
    assert best == root / "BE" / "b.txt"
    assert scanned == 2


def test_find_last_opened_file_returns_none_without_selected_locales(
    tmp_path: Path,
) -> None:
    """Verify find last opened file returns none without selected locales."""
    root = tmp_path / "proj"
    _touch(root / ".tzp" / "cache" / "BE" / "a.bin")
    best, scanned = find_last_opened_file(
        root=root,
        cache_dir=".tzp/cache",
        cache_ext=".bin",
        translation_ext=".txt",
        selected_locales=[],
        read_last_opened=lambda _cache_path: 1,
    )
    assert best is None
    assert scanned == 0


def test_find_last_opened_file_skips_missing_original_even_with_timestamp(
    tmp_path: Path,
) -> None:
    """Verify find last opened skips cache rows when original source file is missing."""
    root = tmp_path / "proj"
    _touch(root / ".tzp" / "cache" / "BE" / "ghost.bin")
    best, scanned = find_last_opened_file(
        root=root,
        cache_dir=".tzp/cache",
        cache_ext=".bin",
        translation_ext=".txt",
        selected_locales=["BE"],
        read_last_opened=lambda _cache_path: 10,
    )
    assert best is None
    assert scanned == 1


def test_collect_draft_files_reads_legacy_cache_dir(tmp_path: Path) -> None:
    """Verify collect draft files reads legacy cache dir."""
    root = tmp_path / "proj"
    _touch(root / "BE" / "a.txt")
    legacy_cache = root / ".tzp-cache" / "BE" / "a.bin"
    _touch(legacy_cache)

    files = collect_draft_files(
        root=root,
        cache_dir=".tzp/cache",
        cache_ext=".bin",
        translation_ext=".txt",
        has_drafts=lambda cache_path: cache_path == legacy_cache,
        locales=["BE"],
    )

    assert files == [root / "BE" / "a.txt"]


def test_collect_draft_files_handles_legacy_primary_cache_root(tmp_path: Path) -> None:
    """Verify draft collection works when cache_dir is configured as legacy root."""
    root = tmp_path / "proj"
    _touch(root / "BE" / "a.txt")
    legacy_cache = root / ".tzp-cache" / "BE" / "a.bin"
    _touch(legacy_cache)

    files = collect_draft_files(
        root=root,
        cache_dir=".tzp-cache",
        cache_ext=".bin",
        translation_ext=".txt",
        has_drafts=lambda cache_path: cache_path == legacy_cache,
        locales=["BE"],
    )

    assert files == [root / "BE" / "a.txt"]


def test_collect_orphan_cache_paths_filters_warned_locales(tmp_path: Path) -> None:
    """Verify collect orphan cache paths filters warned locales."""
    root = tmp_path / "proj"
    _touch(root / ".tzp" / "cache" / "BE" / "orphan.bin")
    _touch(root / ".tzp-cache" / "RU" / "legacy_orphan.bin")
    _touch(root / "RU" / "ok.txt")
    _touch(root / ".tzp" / "cache" / "RU" / "ok.bin")

    out = collect_orphan_cache_paths(
        root=root,
        cache_dir=".tzp/cache",
        cache_ext=".bin",
        translation_ext=".txt",
        selected_locales=["BE", "RU"],
        warned_locales={"RU"},
    )

    assert set(out) == {"BE"}
    assert out["BE"] == [root / ".tzp" / "cache" / "BE" / "orphan.bin"]


def test_build_crash_recovery_report_collects_draft_and_status_counts(
    tmp_path: Path,
) -> None:
    """Verify crash recovery report collects deterministic per-file draft/status counts."""
    root = tmp_path / "proj"
    file_a = root / "BE" / "a.txt"
    file_b = root / "BE" / "b.txt"
    _touch(file_a, 'A = "one"\n')
    _touch(file_b, 'B = "two"\n')
    _write_cache_fixture(
        root,
        file_a,
        draft_keys=("A",),
        status_only_keys=("A_STATUS",),
    )
    _write_cache_fixture(
        root,
        file_b,
        draft_keys=("B",),
        status_only_keys=(),
    )

    report = build_crash_recovery_report(
        root=root,
        cache_dir=".tzp/cache",
        cache_ext=".bin",
        translation_ext=".txt",
        selected_locales=["BE", "BE"],
        has_drafts=status_cache.read_has_drafts_from_path,
        now_ms=lambda: 123456,
    )

    assert report == CrashRecoveryReport(
        project_root=str(root),
        generated_at_ms=123456,
        affected_files=(
            CrashRecoveryAffectedFile(
                file_path="BE/a.txt",
                locale="BE",
                draft_value_count=1,
                status_only_count=1,
                cache_mtime_ns=(root / ".tzp" / "cache" / "BE" / "a.bin")
                .stat()
                .st_mtime_ns,
                warning="",
            ),
            CrashRecoveryAffectedFile(
                file_path="BE/b.txt",
                locale="BE",
                draft_value_count=1,
                status_only_count=0,
                cache_mtime_ns=(root / ".tzp" / "cache" / "BE" / "b.bin")
                .stat()
                .st_mtime_ns,
                warning="",
            ),
        ),
        total_files=2,
        total_draft_values=2,
        total_status_only=1,
    )


def test_build_crash_recovery_report_returns_none_without_drafts(
    tmp_path: Path,
) -> None:
    """Verify crash recovery report returns none when cache has no draft values."""
    root = tmp_path / "proj"
    file_a = root / "BE" / "a.txt"
    _touch(file_a, 'A = "one"\n')
    _write_cache_fixture(
        root,
        file_a,
        draft_keys=(),
        status_only_keys=("A_STATUS",),
    )

    report = build_crash_recovery_report(
        root=root,
        cache_dir=".tzp/cache",
        cache_ext=".bin",
        translation_ext=".txt",
        selected_locales=["BE"],
        has_drafts=status_cache.read_has_drafts_from_path,
        now_ms=lambda: 1,
    )

    assert report is None


def test_build_crash_recovery_report_returns_none_when_selected_locales_empty(
    tmp_path: Path,
) -> None:
    """Verify crash recovery report returns none when selected locale list is empty."""
    root = tmp_path / "proj"
    _touch(root / "BE" / "a.txt")
    _touch(root / ".tzp" / "cache" / "BE" / "a.bin")

    report = build_crash_recovery_report(
        root=root,
        cache_dir=".tzp/cache",
        cache_ext=".bin",
        translation_ext=".txt",
        selected_locales=[],
        has_drafts=lambda _path: True,
        now_ms=lambda: 1,
    )

    assert report is None


def test_build_crash_recovery_report_handles_draft_flag_without_cache_rows(
    tmp_path: Path,
) -> None:
    """Verify crash recovery report tolerates draft-flag true with status-only rows."""
    root = tmp_path / "proj"
    file_a = root / "BE" / "a.txt"
    _touch(file_a, 'A = "one"\n')
    _write_cache_fixture(
        root,
        file_a,
        draft_keys=(),
        status_only_keys=("A_STATUS",),
    )

    report = build_crash_recovery_report(
        root=root,
        cache_dir=".tzp/cache",
        cache_ext=".bin",
        translation_ext=".txt",
        selected_locales=["BE"],
        has_drafts=lambda _path: True,
        now_ms=lambda: 7,
    )

    assert report is None


def test_build_crash_recovery_detection_plan_requires_interrupt_signal() -> None:
    """Verify crash recovery detection requires startup acceptance and interruption signal."""
    report = CrashRecoveryReport(
        project_root="/tmp/proj",
        generated_at_ms=1,
        affected_files=(
            CrashRecoveryAffectedFile(
                file_path="BE/a.txt",
                locale="BE",
                draft_value_count=1,
                status_only_count=0,
                cache_mtime_ns=1,
                warning="",
            ),
        ),
        total_files=1,
        total_draft_values=1,
        total_status_only=0,
    )
    blocked = build_crash_recovery_detection_plan(
        startup_accepted=True,
        report=report,
        previous_session_unclean=False,
        interrupted_draft_marker=False,
    )
    assert blocked == CrashRecoveryDetectionPlan(
        run_recovery_flow=False,
        report=None,
    )

    enabled = build_crash_recovery_detection_plan(
        startup_accepted=True,
        report=report,
        previous_session_unclean=True,
        interrupted_draft_marker=False,
    )
    assert enabled == CrashRecoveryDetectionPlan(
        run_recovery_flow=True,
        report=report,
    )


def test_build_crash_recovery_apply_plan_variants(tmp_path: Path) -> None:
    """Verify crash recovery apply-plan builder maps restore/discard/cancel deterministically."""
    root = tmp_path / "proj"
    report = CrashRecoveryReport(
        project_root=str(root),
        generated_at_ms=1,
        affected_files=(
            CrashRecoveryAffectedFile(
                file_path="BE/a.txt",
                locale="BE",
                draft_value_count=1,
                status_only_count=0,
                cache_mtime_ns=1,
                warning="",
            ),
            CrashRecoveryAffectedFile(
                file_path=str(root / "BE" / "b.txt"),
                locale="BE",
                draft_value_count=1,
                status_only_count=0,
                cache_mtime_ns=2,
                warning="",
            ),
            CrashRecoveryAffectedFile(
                file_path=str(tmp_path / "outside.txt"),
                locale="BE",
                draft_value_count=1,
                status_only_count=0,
                cache_mtime_ns=3,
                warning="",
            ),
        ),
        total_files=3,
        total_draft_values=3,
        total_status_only=0,
    )
    cancel_plan = build_crash_recovery_apply_plan(
        root=root,
        cache_dir=".tzp/cache",
        cache_ext=".bin",
        report=report,
        decision="cancel",
    )
    restore_plan = build_crash_recovery_apply_plan(
        root=root,
        cache_dir=".tzp/cache",
        cache_ext=".bin",
        report=report,
        decision="restore",
    )
    discard_plan = build_crash_recovery_apply_plan(
        root=root,
        cache_dir=".tzp/cache",
        cache_ext=".bin",
        report=report,
        decision="discard",
    )

    assert cancel_plan == CrashRecoveryApplyPlan(
        decision="cancel",
        continue_startup=False,
        discard_cache_paths=(),
    )
    assert restore_plan == CrashRecoveryApplyPlan(
        decision="restore",
        continue_startup=True,
        discard_cache_paths=(),
    )
    assert discard_plan == CrashRecoveryApplyPlan(
        decision="discard",
        continue_startup=True,
        discard_cache_paths=(
            root / ".tzp" / "cache" / "BE" / "a.bin",
            root / ".tzp" / "cache" / "BE" / "b.bin",
            root / ".tzp" / "cache" / "session.resume.json",
            root / ".tzp-cache" / "BE" / "a.bin",
            root / ".tzp-cache" / "BE" / "b.bin",
        ),
    )


def test_build_crash_recovery_apply_plan_rejects_unknown_decision(
    tmp_path: Path,
) -> None:
    """Verify crash recovery apply-plan builder rejects unknown decisions."""
    with pytest.raises(ValueError, match="Unsupported crash recovery decision"):
        build_crash_recovery_apply_plan(
            root=tmp_path / "proj",
            cache_dir=".tzp/cache",
            cache_ext=".bin",
            report=None,
            decision="bad",
        )


def test_build_crash_recovery_apply_plan_discard_without_report_keeps_snapshot_delete(
    tmp_path: Path,
) -> None:
    """Verify discard plan includes session snapshot delete even without report payload."""
    root = tmp_path / "proj"
    plan = build_crash_recovery_apply_plan(
        root=root,
        cache_dir=".tzp/cache",
        cache_ext=".bin",
        report=None,
        decision="discard",
    )
    assert plan == CrashRecoveryApplyPlan(
        decision="discard",
        continue_startup=True,
        discard_cache_paths=(root / ".tzp" / "cache" / "session.resume.json",),
    )


def test_execute_crash_recovery_apply_plan_variants(tmp_path: Path) -> None:
    """Verify crash recovery apply-plan executor handles noop/success/failure deterministically."""
    root = tmp_path / "proj"
    path_a = root / ".tzp" / "cache" / "BE" / "a.bin"
    path_b = root / ".tzp-cache" / "BE" / "a.bin"
    noop_execution = execute_crash_recovery_apply_plan(
        plan=CrashRecoveryApplyPlan(
            decision="cancel",
            continue_startup=False,
            discard_cache_paths=(),
        )
    )
    calls: list[Path] = []

    def _unlink(path: Path) -> None:
        calls.append(path)
        if path == path_b:
            raise OSError("unlink failed")

    execution = execute_crash_recovery_apply_plan(
        plan=CrashRecoveryApplyPlan(
            decision="discard",
            continue_startup=True,
            discard_cache_paths=(path_a, path_b),
        ),
        unlink_cache_path=_unlink,
    )

    assert noop_execution == CrashRecoveryApplyExecution(
        decision="cancel",
        continue_startup=False,
        discarded_cache_paths=(),
        failed_cache_paths=(),
        failure_message=None,
    )
    assert calls == [path_a, path_b]
    assert execution.decision == "discard"
    assert execution.continue_startup is True
    assert execution.discarded_cache_paths == (path_a,)
    assert execution.failed_cache_paths == (path_b,)
    assert execution.failure_message == path_b.as_posix()


def test_execute_crash_recovery_apply_plan_uses_default_unlink_for_missing_path(
    tmp_path: Path,
) -> None:
    """Verify crash recovery apply executor uses missing-ok unlink when callback is omitted."""
    missing_path = tmp_path / "proj" / ".tzp" / "cache" / "BE" / "missing.bin"
    execution = execute_crash_recovery_apply_plan(
        plan=CrashRecoveryApplyPlan(
            decision="discard",
            continue_startup=True,
            discard_cache_paths=(missing_path,),
        )
    )
    assert execution == CrashRecoveryApplyExecution(
        decision="discard",
        continue_startup=True,
        discarded_cache_paths=(missing_path,),
        failed_cache_paths=(),
        failure_message=None,
    )


def test_execute_crash_recovery_apply_plan_truncates_failure_message_preview(
    tmp_path: Path,
) -> None:
    """Verify crash recovery apply executor truncates failure preview after 20 paths."""
    failed_paths = tuple(
        tmp_path / "proj" / ".tzp" / "cache" / "BE" / f"{idx}.bin" for idx in range(21)
    )

    def _always_fail(_path: Path) -> None:
        raise OSError("boom")

    execution = execute_crash_recovery_apply_plan(
        plan=CrashRecoveryApplyPlan(
            decision="discard",
            continue_startup=True,
            discard_cache_paths=failed_paths,
        ),
        unlink_cache_path=_always_fail,
    )
    assert execution.failed_cache_paths == failed_paths
    assert execution.failure_message is not None
    assert "... (1 more)" in execution.failure_message


def test_project_session_private_path_helpers_cover_outside_and_missing_cases(
    tmp_path: Path,
) -> None:
    """Verify private path helpers handle outside-root and missing-file fallbacks."""
    root = tmp_path / "proj"
    cache_root = root / ".tzp" / "cache"
    outside_cache = tmp_path / "outside" / "a.bin"
    outside_file = tmp_path / "outside" / "a.txt"
    missing_stat = tmp_path / "outside" / "missing.bin"

    assert (
        project_session_module._original_path_from_cache(
            root=root,
            cache_root=cache_root,
            cache_path=outside_cache,
            cache_ext=".bin",
            translation_ext=".txt",
        )
        is None
    )
    assert (
        project_session_module._display_file_path(root=root, file_path=outside_file)
        == outside_file.as_posix()
    )
    assert project_session_module._safe_mtime_ns(missing_stat) == 0


def test_project_session_service_delegates_to_helpers(tmp_path: Path) -> None:
    """Verify project session service delegates to helpers."""
    root = tmp_path / "proj"
    _touch(root / "BE" / "a.txt")
    cache_path = root / ".tzp" / "cache" / "BE" / "a.bin"
    _touch(cache_path)

    svc = ProjectSessionService(
        cache_dir=".tzp/cache",
        cache_ext=".bin",
        translation_ext=".txt",
        has_drafts=lambda path: path == cache_path,
        read_last_opened=lambda path: 123 if path == cache_path else 0,
    )

    assert svc.collect_draft_files(root=root, locales=["BE"]) == [root / "BE" / "a.txt"]
    best, scanned = svc.find_last_opened_file(root=root, selected_locales=["BE"])
    assert best == root / "BE" / "a.txt"
    assert scanned == 1
    assert svc.normalize_selected_locales(
        requested_locales=["EN", "BE", "BE", "RU", "XX"],
        available_locales=["EN", "BE", "RU"],
    ) == ["BE", "RU"]
    assert svc.use_lazy_tree(["BE"]) is False
    assert svc.use_lazy_tree(["BE", "RU"]) is True
    plan = svc.build_locale_selection_plan(
        requested_locales=["RU", "BE", "BE"],
        available_locales=["EN", "BE", "RU"],
        current_locales=["BE"],
    )
    assert plan == LocaleSelectionPlan(
        selected_locales=("RU", "BE"),
        lazy_tree=True,
        changed=True,
    )
    switch_plan = svc.build_locale_switch_plan(
        requested_locales=["RU", "BE", "BE"],
        available_locales=["EN", "BE", "RU"],
        current_locales=["BE"],
    )
    assert switch_plan == LocaleSwitchPlan(
        selected_locales=("RU", "BE"),
        lazy_tree=True,
        should_apply=True,
        reset_session_state=True,
        schedule_post_locale_tasks=True,
        tm_bootstrap_pending=True,
    )
    reset_plan = svc.build_locale_reset_plan()
    assert reset_plan == LocaleResetPlan(
        clear_files_by_locale=True,
        clear_opened_files=True,
        clear_conflict_files=True,
        clear_conflict_sources=True,
        clear_conflict_notified=True,
        clear_current_file=True,
        clear_current_model=True,
        clear_table_model=True,
        clear_status_combo=True,
    )
    reset_calls: list[str] = []
    svc.apply_locale_reset_plan(
        plan=reset_plan,
        clear_files_by_locale=lambda: reset_calls.append("files"),
        clear_opened_files=lambda: reset_calls.append("opened"),
        clear_conflict_files=lambda: reset_calls.append("conflict_files"),
        clear_conflict_sources=lambda: reset_calls.append("conflict_sources"),
        clear_conflict_notified=lambda: reset_calls.append("conflict_notified"),
        clear_current_file=lambda: reset_calls.append("current_file"),
        clear_current_model=lambda: reset_calls.append("current_model"),
        clear_table_model=lambda: reset_calls.append("table"),
        clear_status_combo=lambda: reset_calls.append("status"),
    )
    assert reset_calls == [
        "files",
        "opened",
        "conflict_files",
        "conflict_sources",
        "conflict_notified",
        "current_file",
        "current_model",
        "table",
        "status",
    ]
    startup_plan = svc.build_post_locale_startup_plan(selected_locales=["BE"])
    assert startup_plan == PostLocaleStartupPlan(
        should_schedule=True,
        run_cache_scan=True,
        run_session_resume=True,
        run_auto_open=True,
        task_count=3,
    )
    calls: list[str] = []
    assert (
        svc.run_post_locale_startup_tasks(
            plan=startup_plan,
            run_cache_scan=lambda: calls.append("scan"),
            run_session_resume=lambda: (calls.append("resume"), False)[1],
            run_auto_open=lambda: calls.append("open"),
        )
        == 3
    )
    assert calls == ["scan", "resume", "open"]
    tree_plan = svc.build_tree_rebuild_plan(
        selected_locales=["BE"],
        resize_splitter=True,
    )
    assert tree_plan == TreeRebuildPlan(
        lazy_tree=False,
        expand_all=True,
        preload_single_root=False,
        resize_splitter=True,
    )
    warning_plan = svc.build_orphan_cache_warning(
        locale="BE",
        orphan_paths=[root / ".tzp" / "cache" / "BE" / "a.bin"],
        root=root,
    )
    assert warning_plan == OrphanCacheWarningPlan(
        window_title="Orphan cache files",
        text="Locale BE has cache files without source files.",
        informative_text="Purge deletes those cache files. Dismiss keeps them.",
        detailed_text=".tzp/cache/BE/a.bin",
        orphan_paths=(root / ".tzp" / "cache" / "BE" / "a.bin",),
    )
    apply_plan = svc.build_crash_recovery_apply_plan(
        root=root,
        report=None,
        decision="cancel",
    )
    assert apply_plan == CrashRecoveryApplyPlan(
        decision="cancel",
        continue_startup=False,
        discard_cache_paths=(),
    )
    discard_path = root / ".tzp" / "cache" / "BE" / "a.bin"
    unlinked: list[Path] = []
    execution = svc.execute_crash_recovery_apply_plan(
        plan=CrashRecoveryApplyPlan(
            decision="discard",
            continue_startup=True,
            discard_cache_paths=(discard_path,),
        ),
        unlink_cache_path=lambda path: unlinked.append(path),
    )
    assert execution == CrashRecoveryApplyExecution(
        decision="discard",
        continue_startup=True,
        discarded_cache_paths=(discard_path,),
        failed_cache_paths=(),
        failure_message=None,
    )
    assert unlinked == [discard_path]
    schedule_plan = svc.build_cache_migration_schedule_plan(
        legacy_paths=[root / ".tzp-cache" / "BE" / "a.bin"],
        batch_size=1,
    )
    assert schedule_plan == CacheMigrationSchedulePlan(
        run_immediate=True,
        pending_paths=(),
        reset_migration_count=False,
        start_timer=False,
    )
    batch_plan = svc.build_cache_migration_batch_plan(
        pending_paths=[root / ".tzp-cache" / "BE" / "a.bin"],
        batch_size=1,
        migrated_count=0,
    )
    assert batch_plan == CacheMigrationBatchPlan(
        batch_paths=(root / ".tzp-cache" / "BE" / "a.bin",),
        remaining_paths=(),
        stop_timer=False,
        completion_status_message=None,
    )


def test_project_session_service_builds_crash_recovery_detection_plan(
    tmp_path: Path,
) -> None:
    """Verify project session service builds crash recovery report and detection plan."""
    root = tmp_path / "proj"
    file_a = root / "BE" / "a.txt"
    _touch(file_a, 'A = "one"\n')
    _write_cache_fixture(
        root,
        file_a,
        draft_keys=("A",),
        status_only_keys=("A_STATUS",),
    )
    svc = ProjectSessionService(
        cache_dir=".tzp/cache",
        cache_ext=".bin",
        translation_ext=".txt",
        has_drafts=status_cache.read_has_drafts_from_path,
        read_last_opened=status_cache.read_last_opened_from_path,
    )

    report = svc.build_crash_recovery_report(
        root=root,
        selected_locales=["BE"],
        now_ms=lambda: 42,
    )
    assert report is not None
    assert report.total_draft_values == 1
    assert report.total_status_only == 1
    assert report.generated_at_ms == 42

    plan = svc.build_crash_recovery_detection_plan(
        root=root,
        selected_locales=["BE"],
        startup_accepted=True,
        previous_session_unclean=False,
        interrupted_draft_marker=True,
        now_ms=lambda: 42,
    )
    assert plan.run_recovery_flow is True
    assert plan.report is not None
    assert plan.report.total_files == 1


def test_project_session_service_session_resume_snapshot_roundtrip(
    tmp_path: Path,
) -> None:
    """Verify session-resume snapshot build/read/write/resolve contracts are deterministic."""
    root = tmp_path / "proj"
    _touch(root / "BE" / "a.txt", 'A = "one"\n')
    svc = ProjectSessionService(
        cache_dir=".tzp/cache",
        cache_ext=".bin",
        translation_ext=".txt",
        has_drafts=lambda _path: False,
        read_last_opened=lambda _path: 0,
    )
    snapshot = svc.build_session_resume_snapshot(
        generated_at_ms=123,
        selected_locales=["BE", "BE", "RU"],
        active_file_relpath="BE/a.txt",
        active_row=7,
        left_panel_index=2,
        detail_visible=True,
        search_text="foo",
        replace_text="bar",
        search_case_sensitive=True,
        tm_min_score=80,
        tm_grouping_mode="origin",
        tm_origin_project=True,
        tm_origin_import=False,
    )
    assert snapshot == SessionResumeSnapshot(
        version=1,
        generated_at_ms=123,
        selected_locales=("BE", "RU"),
        active_file_relpath="BE/a.txt",
        active_row=7,
        left_panel_index=0,
        detail_visible=True,
        search_text="foo",
        replace_text="bar",
        search_case_sensitive=True,
        tm_min_score=80,
        tm_grouping_mode="origin",
        tm_origin_project=True,
        tm_origin_import=False,
    )
    path = svc.write_session_resume_snapshot(root=root, snapshot=snapshot)
    assert path == root / ".tzp" / "cache" / "session.resume.json"
    loaded = svc.read_session_resume_snapshot(root=root)
    assert loaded == snapshot
    assert (
        svc.resolve_session_resume_active_path(
            root=root,
            active_file_relpath="BE/a.txt",
        )
        == (root / "BE" / "a.txt").resolve()
    )
    assert (
        svc.resolve_session_resume_active_path(
            root=root,
            active_file_relpath="../outside.txt",
        )
        is None
    )


def test_session_resume_parser_normalizes_legacy_sidebar_to_project() -> None:
    """Verify legacy snapshots cannot reactivate heavyweight side panels at startup."""
    snapshot = session_resume_module.parse_session_resume_snapshot(
        _session_resume_payload(left_panel_index=1)
    )

    assert snapshot is not None
    assert snapshot.left_panel_index == 0


def test_session_resume_default_writer_uses_atomic_replace(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Project session state must not expose a partial JSON file after interruption."""
    snapshot = session_resume_module.parse_session_resume_snapshot(
        _session_resume_payload()
    )
    assert snapshot is not None
    writes: list[tuple[Path, str, str]] = []
    monkeypatch.setattr(
        session_resume_module,
        "write_text_atomic",
        lambda path, text, *, encoding: writes.append((path, text, encoding)),
    )

    path = session_resume_module.write_session_resume_snapshot(
        root=tmp_path,
        cache_dir=".tzp/cache",
        snapshot=snapshot,
    )

    assert writes == [
        (
            path,
            json.dumps(snapshot.to_payload(), ensure_ascii=False, indent=2) + "\n",
            "utf-8",
        )
    ]


def test_project_session_service_session_resume_snapshot_reader_ignores_invalid_payloads(
    tmp_path: Path,
) -> None:
    """Verify invalid snapshot payloads are ignored without exception leakage."""
    root = tmp_path / "proj"
    svc = ProjectSessionService(
        cache_dir=".tzp/cache",
        cache_ext=".bin",
        translation_ext=".txt",
        has_drafts=lambda _path: False,
        read_last_opened=lambda _path: 0,
    )
    path = svc.session_resume_snapshot_path(root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not-json", encoding="utf-8")
    assert svc.read_session_resume_snapshot(root=root) is None

    payload = {
        "version": 999,
        "generated_at_ms": 1,
        "selected_locales": ["BE"],
        "active_file_relpath": None,
        "active_row": None,
        "left_panel_index": 0,
        "detail_visible": True,
        "search_text": "",
        "replace_text": "",
        "search_case_sensitive": False,
        "tm_min_score": 50,
        "tm_grouping_mode": "none",
        "tm_origin_project": True,
        "tm_origin_import": True,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert svc.read_session_resume_snapshot(root=root) is None


def test_session_resume_persistence_helpers_support_injected_io_and_fail_closed(
    tmp_path: Path,
) -> None:
    """Verify snapshot persistence callbacks and deletion failures stay deterministic."""
    root = tmp_path / "proj"
    snapshot = session_resume_module.build_session_resume_snapshot(
        generated_at_ms=123,
        selected_locales=["BE"],
        active_file_relpath="BE/a.txt",
        active_row=2,
        left_panel_index=1,
        detail_visible=True,
        search_text="źródło",
        replace_text="target",
        search_case_sensitive=False,
        tm_min_score=80,
        tm_grouping_mode="origin",
        tm_origin_project=True,
        tm_origin_import=False,
    )
    assert snapshot.left_panel_index == 0
    writes: list[tuple[Path, str]] = []
    path = session_resume_module.write_session_resume_snapshot(
        root=root,
        cache_dir=".tzp/cache",
        snapshot=snapshot,
        write_text=lambda target, text: writes.append((target, text)),
    )
    assert writes == [
        (path, json.dumps(snapshot.to_payload(), ensure_ascii=False, indent=2) + "\n")
    ]

    _touch(path)
    assert session_resume_module.delete_session_resume_snapshot(
        root=root,
        cache_dir=".tzp/cache",
    )
    assert not path.exists()

    deleted: list[Path] = []
    assert session_resume_module.delete_session_resume_snapshot(
        root=root,
        cache_dir=".tzp/cache",
        unlink_path=deleted.append,
    )
    assert deleted == [path]

    def _fail_delete(_path: Path) -> None:
        raise OSError("blocked")

    assert not session_resume_module.delete_session_resume_snapshot(
        root=root,
        cache_dir=".tzp/cache",
        unlink_path=_fail_delete,
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("generated_at_ms", True),
        ("generated_at_ms", -1),
        ("selected_locales", "BE"),
        ("left_panel_index", -1),
        ("detail_visible", 1),
        ("search_text", None),
        ("search_case_sensitive", 0),
        ("tm_min_score", 4),
        ("tm_grouping_mode", "invalid"),
        ("tm_origin_project", 1),
    ],
)
def test_session_resume_parser_rejects_invalid_required_fields(
    field: str,
    value: object,
) -> None:
    """Verify malformed required snapshot fields reject the whole resume record."""
    payload = _session_resume_payload()
    payload[field] = value
    assert session_resume_module.parse_session_resume_snapshot(payload) is None


@pytest.mark.parametrize(
    ("active_file_relpath", "active_row"),
    [
        (None, None),
        (123, True),
        ("", -1),
    ],
)
def test_session_resume_parser_normalizes_optional_fields(
    active_file_relpath: object,
    active_row: object,
) -> None:
    """Verify unusable optional location fields are normalized without losing the snapshot."""
    payload = _session_resume_payload(
        selected_locales=["BE", "", "BE"],
        active_file_relpath=active_file_relpath,
        active_row=active_row,
    )
    snapshot = session_resume_module.parse_session_resume_snapshot(payload)
    assert snapshot is not None
    assert snapshot.selected_locales == ("BE",)
    assert snapshot.active_file_relpath is None
    assert snapshot.active_row is None


def test_session_resume_parser_rejects_invalid_payload_shape_and_locale_rows() -> None:
    """Verify non-object snapshots and non-string locale rows are rejected."""
    assert session_resume_module.parse_session_resume_snapshot([]) is None
    payload = _session_resume_payload(selected_locales=["BE", 123])
    assert session_resume_module.parse_session_resume_snapshot(payload) is None
    assert (
        session_resume_module.resolve_session_resume_active_path(
            root=Path("/project"),
            active_file_relpath="",
        )
        is None
    )


def test_normalize_selected_locales_filters_source_unknown_and_duplicates() -> None:
    """Verify normalize selected locales filters source unknown and duplicates."""
    selected = normalize_selected_locales(
        requested_locales=["", "EN", "BE", "BE", "RU", "XX", "RU"],
        available_locales=["EN", "BE", "RU"],
        source_locale="EN",
    )
    assert selected == ["BE", "RU"]


def test_use_lazy_tree_requires_more_than_one_locale() -> None:
    """Verify use lazy tree requires more than one locale."""
    assert use_lazy_tree([]) is False
    assert use_lazy_tree(["BE"]) is False
    assert use_lazy_tree(["BE", ""]) is False
    assert use_lazy_tree(["BE", "RU"]) is True


def test_resolve_requested_locales_uses_explicit_request() -> None:
    """Verify resolve requested locales uses explicit request."""
    selected = resolve_requested_locales(
        requested_locales=["RU", "BE"],
        resume_locales=["BE"],
        last_locales=["BE"],
        available_locales=["EN", "BE", "RU"],
        smoke_mode=False,
        source_locale="EN",
    )
    assert selected == ["RU", "BE"]


def test_resolve_requested_locales_uses_valid_session_pool_without_smoke() -> None:
    """Verify a saved session pool bypasses interactive startup locale selection."""
    selected = resolve_requested_locales(
        requested_locales=None,
        resume_locales=["EN", "RU", "RU", "missing", "BE"],
        last_locales=[],
        available_locales=["EN", "BE", "RU"],
        smoke_mode=False,
        source_locale="EN",
    )

    assert selected == ["RU", "BE"]


def test_resolve_requested_locales_prefers_last_locales_in_smoke_mode() -> None:
    """Verify resolve requested locales prefers last locales in smoke mode."""
    selected = resolve_requested_locales(
        requested_locales=None,
        last_locales=["EN", "RU", "RU"],
        available_locales=["EN", "BE", "RU"],
        smoke_mode=True,
        source_locale="EN",
    )
    assert selected == ["RU"]


def test_resolve_requested_locales_uses_first_available_in_smoke_mode() -> None:
    """Verify resolve requested locales uses first available in smoke mode."""
    selected = resolve_requested_locales(
        requested_locales=None,
        last_locales=[],
        available_locales=["EN", "BE", "RU"],
        smoke_mode=True,
        source_locale="EN",
    )
    assert selected == ["BE"]


def test_resolve_requested_locales_returns_none_without_smoke_mode() -> None:
    """Verify resolve requested locales returns none without smoke mode."""
    selected = resolve_requested_locales(
        requested_locales=None,
        resume_locales=["missing"],
        last_locales=["BE"],
        available_locales=["EN", "BE", "RU"],
        smoke_mode=False,
        source_locale="EN",
    )
    assert selected is None


def test_build_locale_selection_plan_deduplicates_and_flags_change() -> None:
    """Verify build locale selection plan deduplicates and flags change."""
    plan = build_locale_selection_plan(
        requested_locales=["EN", "RU", "RU", "BE", "XX"],
        available_locales=["EN", "BE", "RU"],
        current_locales=["BE"],
        source_locale="EN",
    )
    assert plan == LocaleSelectionPlan(
        selected_locales=("RU", "BE"),
        lazy_tree=True,
        changed=True,
    )


def test_build_locale_selection_plan_marks_no_change() -> None:
    """Verify build locale selection plan marks no change."""
    plan = build_locale_selection_plan(
        requested_locales=["BE"],
        available_locales=["EN", "BE", "RU"],
        current_locales=["EN", "BE", "BE"],
        source_locale="EN",
    )
    assert plan == LocaleSelectionPlan(
        selected_locales=("BE",),
        lazy_tree=False,
        changed=False,
    )


def test_build_locale_selection_plan_returns_none_when_empty() -> None:
    """Verify build locale selection plan returns none when empty."""
    plan = build_locale_selection_plan(
        requested_locales=["EN", "", "XX"],
        available_locales=["EN", "BE", "RU"],
        current_locales=["BE"],
        source_locale="EN",
    )
    assert plan is None


def test_build_orphan_cache_warning_truncates_preview(tmp_path: Path) -> None:
    """Verify build orphan cache warning truncates preview."""
    root = tmp_path / "proj"
    orphan_paths = [
        root / ".tzp" / "cache" / "BE" / "a.bin",
        root / ".tzp" / "cache" / "BE" / "b.bin",
        root / ".tzp" / "cache" / "BE" / "c.bin",
    ]
    plan = build_orphan_cache_warning(
        locale="BE",
        orphan_paths=orphan_paths,
        root=root,
        preview_limit=2,
    )
    assert plan.detailed_text == (
        ".tzp/cache/BE/a.bin\n.tzp/cache/BE/b.bin\n... (1 more)"
    )
    assert plan.orphan_paths == tuple(orphan_paths)


def test_build_orphan_cache_warning_keeps_absolute_paths_outside_root(
    tmp_path: Path,
) -> None:
    """Verify orphan warning preview keeps absolute path for files outside root."""
    root = tmp_path / "proj"
    orphan = tmp_path / "outside" / "orphan.bin"
    plan = build_orphan_cache_warning(
        locale="BE",
        orphan_paths=[orphan],
        root=root,
    )

    assert plan.detailed_text == orphan.as_posix()
    assert plan.orphan_paths == (orphan,)


def test_build_cache_migration_schedule_plan_variants(tmp_path: Path) -> None:
    """Verify build cache migration schedule plan variants."""
    root = tmp_path / "proj"
    path_a = root / ".tzp-cache" / "BE" / "a.bin"
    path_b = root / ".tzp-cache" / "BE" / "b.bin"

    none_plan = build_cache_migration_schedule_plan(legacy_paths=[], batch_size=10)
    immediate_plan = build_cache_migration_schedule_plan(
        legacy_paths=[path_a],
        batch_size=10,
    )
    batched_plan = build_cache_migration_schedule_plan(
        legacy_paths=[path_a, path_b],
        batch_size=1,
    )

    assert none_plan == CacheMigrationSchedulePlan(
        run_immediate=False,
        pending_paths=(),
        reset_migration_count=False,
        start_timer=False,
    )
    assert immediate_plan == CacheMigrationSchedulePlan(
        run_immediate=True,
        pending_paths=(),
        reset_migration_count=False,
        start_timer=False,
    )
    assert batched_plan == CacheMigrationSchedulePlan(
        run_immediate=False,
        pending_paths=(path_a, path_b),
        reset_migration_count=True,
        start_timer=True,
    )


def test_build_cache_migration_batch_plan_variants(tmp_path: Path) -> None:
    """Verify build cache migration batch plan variants."""
    root = tmp_path / "proj"
    path_a = root / ".tzp-cache" / "BE" / "a.bin"
    path_b = root / ".tzp-cache" / "BE" / "b.bin"

    stop_plan = build_cache_migration_batch_plan(
        pending_paths=[],
        batch_size=10,
        migrated_count=2,
    )
    run_plan = build_cache_migration_batch_plan(
        pending_paths=[path_a, path_b],
        batch_size=1,
        migrated_count=2,
    )

    assert stop_plan == CacheMigrationBatchPlan(
        batch_paths=(),
        remaining_paths=(),
        stop_timer=True,
        completion_status_message="Migrated 2 cache file(s).",
    )
    assert run_plan == CacheMigrationBatchPlan(
        batch_paths=(path_a,),
        remaining_paths=(path_b,),
        stop_timer=False,
        completion_status_message=None,
    )


def test_execute_cache_migration_schedule_immediate_success(tmp_path: Path) -> None:
    """Verify execute cache migration schedule immediate success."""
    root = tmp_path / "proj"
    legacy = root / ".tzp-cache" / "BE" / "a.bin"
    calls: list[str] = []
    execution = execute_cache_migration_schedule(
        legacy_paths=[legacy],
        batch_size=10,
        migrated_count=2,
        callbacks=CacheMigrationScheduleCallbacks(
            migrate_all=lambda: 3,
            warn=lambda _msg: calls.append("warn"),
            start_timer=lambda: calls.append("start_timer"),
        ),
    )
    assert execution == CacheMigrationScheduleExecution(
        pending_paths=(),
        migrated_count=5,
    )
    assert calls == []


def test_execute_cache_migration_schedule_batched_starts_timer(tmp_path: Path) -> None:
    """Verify execute cache migration schedule batched starts timer."""
    root = tmp_path / "proj"
    a = root / ".tzp-cache" / "BE" / "a.bin"
    b = root / ".tzp-cache" / "BE" / "b.bin"
    calls: list[str] = []
    execution = execute_cache_migration_schedule(
        legacy_paths=[a, b],
        batch_size=1,
        migrated_count=7,
        callbacks=CacheMigrationScheduleCallbacks(
            migrate_all=lambda: 0,
            warn=lambda _msg: calls.append("warn"),
            start_timer=lambda: calls.append("start_timer"),
        ),
    )
    assert execution == CacheMigrationScheduleExecution(
        pending_paths=(a, b),
        migrated_count=0,
    )
    assert calls == ["start_timer"]


def test_execute_cache_migration_batch_success(tmp_path: Path) -> None:
    """Verify execute cache migration batch success."""
    root = tmp_path / "proj"
    a = root / ".tzp-cache" / "BE" / "a.bin"
    b = root / ".tzp-cache" / "BE" / "b.bin"
    calls: list[str] = []
    execution = execute_cache_migration_batch(
        pending_paths=[a, b],
        batch_size=1,
        migrated_count=4,
        callbacks=CacheMigrationBatchCallbacks(
            migrate_paths=lambda paths: len(paths),
            warn=lambda _msg: calls.append("warn"),
            stop_timer=lambda: calls.append("stop"),
            show_status=lambda _msg: calls.append("status"),
        ),
    )
    assert execution == CacheMigrationBatchExecution(
        remaining_paths=(b,),
        migrated_count=5,
    )
    assert calls == []


def test_execute_cache_migration_batch_stop_and_status(tmp_path: Path) -> None:
    """Verify execute cache migration batch stop and status."""
    calls: list[str] = []
    execution = execute_cache_migration_batch(
        pending_paths=[],
        batch_size=5,
        migrated_count=2,
        callbacks=CacheMigrationBatchCallbacks(
            migrate_paths=lambda _paths: 0,
            warn=lambda _msg: calls.append("warn"),
            stop_timer=lambda: calls.append("stop"),
            show_status=lambda _msg: calls.append("status"),
        ),
    )
    assert execution == CacheMigrationBatchExecution(
        remaining_paths=(),
        migrated_count=2,
    )
    assert calls == ["stop", "status"]


def test_execute_cache_migration_batch_failure_warns_and_stops(tmp_path: Path) -> None:
    """Verify execute cache migration batch failure warns and stops."""
    root = tmp_path / "proj"
    a = root / ".tzp-cache" / "BE" / "a.bin"
    calls: list[str] = []

    def _fail(_paths):
        raise RuntimeError("boom")

    execution = execute_cache_migration_batch(
        pending_paths=[a],
        batch_size=5,
        migrated_count=2,
        callbacks=CacheMigrationBatchCallbacks(
            migrate_paths=_fail,
            warn=lambda _msg: calls.append("warn"),
            stop_timer=lambda: calls.append("stop"),
            show_status=lambda _msg: calls.append("status"),
        ),
    )
    assert execution == CacheMigrationBatchExecution(
        remaining_paths=(a,),
        migrated_count=2,
    )
    assert calls == ["stop", "warn"]


def test_build_locale_switch_plan_marks_apply_for_changed_selection() -> None:
    """Verify build locale switch plan marks apply for changed selection."""
    plan = build_locale_switch_plan(
        requested_locales=["EN", "RU", "BE"],
        available_locales=["EN", "BE", "RU"],
        current_locales=["BE"],
        source_locale="EN",
    )
    assert plan == LocaleSwitchPlan(
        selected_locales=("RU", "BE"),
        lazy_tree=True,
        should_apply=True,
        reset_session_state=True,
        schedule_post_locale_tasks=True,
        tm_bootstrap_pending=True,
    )


def test_build_locale_switch_plan_marks_no_apply_for_same_selection() -> None:
    """Verify build locale switch plan marks no apply for same selection."""
    plan = build_locale_switch_plan(
        requested_locales=["BE"],
        available_locales=["EN", "BE", "RU"],
        current_locales=["EN", "BE", "BE"],
        source_locale="EN",
    )
    assert plan == LocaleSwitchPlan(
        selected_locales=("BE",),
        lazy_tree=False,
        should_apply=False,
        reset_session_state=False,
        schedule_post_locale_tasks=False,
        tm_bootstrap_pending=True,
    )


def test_build_locale_switch_plan_returns_none_when_selection_empty() -> None:
    """Verify build locale switch plan returns none when selection empty."""
    plan = build_locale_switch_plan(
        requested_locales=["EN", "", "XX"],
        available_locales=["EN", "BE", "RU"],
        current_locales=["BE"],
        source_locale="EN",
    )
    assert plan is None


def test_build_locale_reset_plan_defaults() -> None:
    """Verify build locale reset plan defaults."""
    plan = build_locale_reset_plan()
    assert plan == LocaleResetPlan(
        clear_files_by_locale=True,
        clear_opened_files=True,
        clear_conflict_files=True,
        clear_conflict_sources=True,
        clear_conflict_notified=True,
        clear_current_file=True,
        clear_current_model=True,
        clear_table_model=True,
        clear_status_combo=True,
    )


def test_apply_locale_reset_plan_executes_all_enabled_callbacks() -> None:
    """Verify apply locale reset plan executes all enabled callbacks."""
    plan = LocaleResetPlan(
        clear_files_by_locale=True,
        clear_opened_files=True,
        clear_conflict_files=True,
        clear_conflict_sources=True,
        clear_conflict_notified=True,
        clear_current_file=True,
        clear_current_model=True,
        clear_table_model=True,
        clear_status_combo=True,
    )
    calls: list[str] = []
    apply_locale_reset_plan(
        plan=plan,
        clear_files_by_locale=lambda: calls.append("files"),
        clear_opened_files=lambda: calls.append("opened"),
        clear_conflict_files=lambda: calls.append("conflict_files"),
        clear_conflict_sources=lambda: calls.append("conflict_sources"),
        clear_conflict_notified=lambda: calls.append("conflict_notified"),
        clear_current_file=lambda: calls.append("current_file"),
        clear_current_model=lambda: calls.append("current_model"),
        clear_table_model=lambda: calls.append("table"),
        clear_status_combo=lambda: calls.append("status"),
    )
    assert calls == [
        "files",
        "opened",
        "conflict_files",
        "conflict_sources",
        "conflict_notified",
        "current_file",
        "current_model",
        "table",
        "status",
    ]


def test_apply_locale_reset_plan_skips_disabled_callbacks() -> None:
    """Verify apply locale reset plan skips disabled callbacks."""
    plan = LocaleResetPlan(
        clear_files_by_locale=False,
        clear_opened_files=True,
        clear_conflict_files=False,
        clear_conflict_sources=False,
        clear_conflict_notified=True,
        clear_current_file=False,
        clear_current_model=False,
        clear_table_model=False,
        clear_status_combo=True,
    )
    calls: list[str] = []
    apply_locale_reset_plan(
        plan=plan,
        clear_files_by_locale=lambda: calls.append("files"),
        clear_opened_files=lambda: calls.append("opened"),
        clear_conflict_files=lambda: calls.append("conflict_files"),
        clear_conflict_sources=lambda: calls.append("conflict_sources"),
        clear_conflict_notified=lambda: calls.append("conflict_notified"),
        clear_current_file=lambda: calls.append("current_file"),
        clear_current_model=lambda: calls.append("current_model"),
        clear_table_model=lambda: calls.append("table"),
        clear_status_combo=lambda: calls.append("status"),
    )
    assert calls == ["opened", "conflict_notified", "status"]


def test_build_post_locale_startup_plan_for_non_empty_locales() -> None:
    """Verify build post locale startup plan for non empty locales."""
    plan = build_post_locale_startup_plan(selected_locales=["BE", "RU"])
    assert plan == PostLocaleStartupPlan(
        should_schedule=True,
        run_cache_scan=True,
        run_session_resume=True,
        run_auto_open=True,
        task_count=3,
    )


def test_build_post_locale_startup_plan_for_empty_locales() -> None:
    """Verify build post locale startup plan for empty locales."""
    plan = build_post_locale_startup_plan(selected_locales=["", ""])
    assert plan == PostLocaleStartupPlan(
        should_schedule=False,
        run_cache_scan=False,
        run_session_resume=False,
        run_auto_open=False,
        task_count=0,
    )


def test_run_post_locale_startup_tasks_executes_enabled_tasks_in_order() -> None:
    """Verify run post locale startup tasks executes enabled tasks in order."""
    plan = PostLocaleStartupPlan(
        should_schedule=True,
        run_cache_scan=True,
        run_session_resume=True,
        run_auto_open=True,
        task_count=3,
    )
    calls: list[str] = []
    executed = run_post_locale_startup_tasks(
        plan=plan,
        run_cache_scan=lambda: calls.append("scan"),
        run_session_resume=lambda: (calls.append("resume"), False)[1],
        run_auto_open=lambda: calls.append("open"),
    )
    assert executed == 3
    assert calls == ["scan", "resume", "open"]


def test_run_post_locale_startup_tasks_skips_auto_open_when_resume_applies() -> None:
    """Verify startup auto-open fallback is skipped when session resume restores context."""
    plan = PostLocaleStartupPlan(
        should_schedule=True,
        run_cache_scan=True,
        run_session_resume=True,
        run_auto_open=True,
        task_count=3,
    )
    calls: list[str] = []
    executed = run_post_locale_startup_tasks(
        plan=plan,
        run_cache_scan=lambda: calls.append("scan"),
        run_session_resume=lambda: (calls.append("resume"), True)[1],
        run_auto_open=lambda: calls.append("open"),
    )
    assert executed == 2
    assert calls == ["scan", "resume"]


def test_run_post_locale_startup_tasks_skips_disabled_plan() -> None:
    """Verify run post locale startup tasks skips disabled plan."""
    plan = PostLocaleStartupPlan(
        should_schedule=False,
        run_cache_scan=True,
        run_session_resume=True,
        run_auto_open=True,
        task_count=3,
    )
    calls: list[str] = []
    executed = run_post_locale_startup_tasks(
        plan=plan,
        run_cache_scan=lambda: calls.append("scan"),
        run_session_resume=lambda: (calls.append("resume"), False)[1],
        run_auto_open=lambda: calls.append("open"),
    )
    assert executed == 0
    assert calls == []


def test_build_tree_rebuild_plan_for_single_locale() -> None:
    """Verify build tree rebuild plan for single locale."""
    plan = build_tree_rebuild_plan(
        selected_locales=["BE"],
        resize_splitter=False,
    )
    assert plan == TreeRebuildPlan(
        lazy_tree=False,
        expand_all=True,
        preload_single_root=False,
        resize_splitter=False,
    )


def test_build_tree_rebuild_plan_for_multiple_locales() -> None:
    """Verify build tree rebuild plan for multiple locales."""
    plan = build_tree_rebuild_plan(
        selected_locales=["BE", "RU"],
        resize_splitter=True,
    )
    assert plan == TreeRebuildPlan(
        lazy_tree=True,
        expand_all=False,
        preload_single_root=False,
        resize_splitter=True,
    )


def test_build_tree_rebuild_plan_ignores_empty_values() -> None:
    """Verify build tree rebuild plan ignores empty values."""
    plan = build_tree_rebuild_plan(
        selected_locales=["", "RU", ""],
        resize_splitter=True,
    )
    assert plan == TreeRebuildPlan(
        lazy_tree=False,
        expand_all=True,
        preload_single_root=False,
        resize_splitter=True,
    )
