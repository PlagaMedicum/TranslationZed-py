from __future__ import annotations

from pathlib import Path

from translationzed_py.core.project_session import (
    CacheMigrationBatchCallbacks,
    CacheMigrationBatchExecution,
    CacheMigrationBatchPlan,
    CacheMigrationScheduleCallbacks,
    CacheMigrationScheduleExecution,
    CacheMigrationSchedulePlan,
    LocaleResetPlan,
    LocaleSelectionPlan,
    LocaleSwitchPlan,
    OrphanCacheWarningPlan,
    PostLocaleStartupPlan,
    ProjectSessionService,
    TreeRebuildPlan,
    apply_locale_reset_plan,
    build_cache_migration_batch_plan,
    build_cache_migration_schedule_plan,
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
    find_last_opened_file,
    normalize_selected_locales,
    resolve_requested_locales,
    run_post_locale_startup_tasks,
    use_lazy_tree,
)


def _touch(path: Path, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_collect_draft_files_filters_by_opened_and_locale(tmp_path: Path) -> None:
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


def test_collect_draft_files_skips_missing_originals(tmp_path: Path) -> None:
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


def test_collect_draft_files_reads_legacy_cache_dir(tmp_path: Path) -> None:
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


def test_collect_orphan_cache_paths_filters_warned_locales(tmp_path: Path) -> None:
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


def test_project_session_service_delegates_to_helpers(tmp_path: Path) -> None:
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
        run_auto_open=True,
        task_count=2,
    )
    calls: list[str] = []
    assert (
        svc.run_post_locale_startup_tasks(
            plan=startup_plan,
            run_cache_scan=lambda: calls.append("scan"),
            run_auto_open=lambda: calls.append("open"),
        )
        == 2
    )
    assert calls == ["scan", "open"]
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


def test_normalize_selected_locales_filters_source_unknown_and_duplicates() -> None:
    selected = normalize_selected_locales(
        requested_locales=["", "EN", "BE", "BE", "RU", "XX", "RU"],
        available_locales=["EN", "BE", "RU"],
        source_locale="EN",
    )
    assert selected == ["BE", "RU"]


def test_use_lazy_tree_requires_more_than_one_locale() -> None:
    assert use_lazy_tree([]) is False
    assert use_lazy_tree(["BE"]) is False
    assert use_lazy_tree(["BE", ""]) is False
    assert use_lazy_tree(["BE", "RU"]) is True


def test_resolve_requested_locales_uses_explicit_request() -> None:
    selected = resolve_requested_locales(
        requested_locales=["RU", "BE"],
        last_locales=["BE"],
        available_locales=["EN", "BE", "RU"],
        smoke_mode=False,
        source_locale="EN",
    )
    assert selected == ["RU", "BE"]


def test_resolve_requested_locales_prefers_last_locales_in_smoke_mode() -> None:
    selected = resolve_requested_locales(
        requested_locales=None,
        last_locales=["EN", "RU", "RU"],
        available_locales=["EN", "BE", "RU"],
        smoke_mode=True,
        source_locale="EN",
    )
    assert selected == ["RU"]


def test_resolve_requested_locales_uses_first_available_in_smoke_mode() -> None:
    selected = resolve_requested_locales(
        requested_locales=None,
        last_locales=[],
        available_locales=["EN", "BE", "RU"],
        smoke_mode=True,
        source_locale="EN",
    )
    assert selected == ["BE"]


def test_resolve_requested_locales_returns_none_without_smoke_mode() -> None:
    selected = resolve_requested_locales(
        requested_locales=None,
        last_locales=["BE"],
        available_locales=["EN", "BE", "RU"],
        smoke_mode=False,
        source_locale="EN",
    )
    assert selected is None


def test_build_locale_selection_plan_deduplicates_and_flags_change() -> None:
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
    plan = build_locale_selection_plan(
        requested_locales=["EN", "", "XX"],
        available_locales=["EN", "BE", "RU"],
        current_locales=["BE"],
        source_locale="EN",
    )
    assert plan is None


def test_build_orphan_cache_warning_truncates_preview(tmp_path: Path) -> None:
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


def test_build_cache_migration_schedule_plan_variants(tmp_path: Path) -> None:
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
    plan = build_locale_switch_plan(
        requested_locales=["EN", "", "XX"],
        available_locales=["EN", "BE", "RU"],
        current_locales=["BE"],
        source_locale="EN",
    )
    assert plan is None


def test_build_locale_reset_plan_defaults() -> None:
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
    plan = build_post_locale_startup_plan(selected_locales=["BE", "RU"])
    assert plan == PostLocaleStartupPlan(
        should_schedule=True,
        run_cache_scan=True,
        run_auto_open=True,
        task_count=2,
    )


def test_build_post_locale_startup_plan_for_empty_locales() -> None:
    plan = build_post_locale_startup_plan(selected_locales=["", ""])
    assert plan == PostLocaleStartupPlan(
        should_schedule=False,
        run_cache_scan=False,
        run_auto_open=False,
        task_count=0,
    )


def test_run_post_locale_startup_tasks_executes_enabled_tasks_in_order() -> None:
    plan = PostLocaleStartupPlan(
        should_schedule=True,
        run_cache_scan=True,
        run_auto_open=True,
        task_count=2,
    )
    calls: list[str] = []
    executed = run_post_locale_startup_tasks(
        plan=plan,
        run_cache_scan=lambda: calls.append("scan"),
        run_auto_open=lambda: calls.append("open"),
    )
    assert executed == 2
    assert calls == ["scan", "open"]


def test_run_post_locale_startup_tasks_skips_disabled_plan() -> None:
    plan = PostLocaleStartupPlan(
        should_schedule=False,
        run_cache_scan=True,
        run_auto_open=True,
        task_count=2,
    )
    calls: list[str] = []
    executed = run_post_locale_startup_tasks(
        plan=plan,
        run_cache_scan=lambda: calls.append("scan"),
        run_auto_open=lambda: calls.append("open"),
    )
    assert executed == 0
    assert calls == []


def test_build_tree_rebuild_plan_for_single_locale() -> None:
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
