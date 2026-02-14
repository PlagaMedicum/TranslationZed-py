from __future__ import annotations

from collections.abc import Callable, Collection, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from translationzed_py.core.app_config import LEGACY_CACHE_DIR


def _cache_roots(root: Path, cache_dir: str) -> tuple[Path, ...]:
    primary = root / cache_dir
    legacy = root / LEGACY_CACHE_DIR
    if legacy == primary:
        return (primary,)
    return (primary, legacy)


@dataclass(frozen=True, slots=True)
class ProjectSessionService:
    cache_dir: str
    cache_ext: str
    translation_ext: str
    has_drafts: Callable[[Path], bool]
    read_last_opened: Callable[[Path], int]
    source_locale: str = "EN"

    def collect_draft_files(
        self,
        *,
        root: Path,
        locales: Iterable[str] | None = None,
        opened_files: Collection[Path] | None = None,
    ) -> list[Path]:
        return collect_draft_files(
            root=root,
            cache_dir=self.cache_dir,
            cache_ext=self.cache_ext,
            translation_ext=self.translation_ext,
            has_drafts=self.has_drafts,
            locales=locales,
            opened_files=opened_files,
        )

    def find_last_opened_file(
        self, *, root: Path, selected_locales: Iterable[str]
    ) -> tuple[Path | None, int]:
        return find_last_opened_file(
            root=root,
            cache_dir=self.cache_dir,
            cache_ext=self.cache_ext,
            translation_ext=self.translation_ext,
            selected_locales=selected_locales,
            read_last_opened=self.read_last_opened,
        )

    def collect_orphan_cache_paths(
        self,
        *,
        root: Path,
        selected_locales: Iterable[str],
        warned_locales: Collection[str] | None = None,
    ) -> dict[str, list[Path]]:
        return collect_orphan_cache_paths(
            root=root,
            cache_dir=self.cache_dir,
            cache_ext=self.cache_ext,
            translation_ext=self.translation_ext,
            selected_locales=selected_locales,
            warned_locales=warned_locales,
        )

    def normalize_selected_locales(
        self,
        *,
        requested_locales: Iterable[str],
        available_locales: Iterable[str],
    ) -> list[str]:
        return normalize_selected_locales(
            requested_locales=requested_locales,
            available_locales=available_locales,
            source_locale=self.source_locale,
        )

    def use_lazy_tree(self, selected_locales: Iterable[str]) -> bool:
        return use_lazy_tree(selected_locales)

    def resolve_requested_locales(
        self,
        *,
        requested_locales: Iterable[str] | None,
        last_locales: Iterable[str],
        available_locales: Iterable[str],
        smoke_mode: bool,
    ) -> list[str] | None:
        return resolve_requested_locales(
            requested_locales=requested_locales,
            last_locales=last_locales,
            available_locales=available_locales,
            smoke_mode=smoke_mode,
            source_locale=self.source_locale,
        )

    def build_locale_selection_plan(
        self,
        *,
        requested_locales: Iterable[str],
        available_locales: Iterable[str],
        current_locales: Iterable[str] = (),
    ) -> LocaleSelectionPlan | None:
        return build_locale_selection_plan(
            requested_locales=requested_locales,
            available_locales=available_locales,
            current_locales=current_locales,
            source_locale=self.source_locale,
        )

    def build_locale_switch_plan(
        self,
        *,
        requested_locales: Iterable[str],
        available_locales: Iterable[str],
        current_locales: Iterable[str],
    ) -> LocaleSwitchPlan | None:
        return build_locale_switch_plan(
            requested_locales=requested_locales,
            available_locales=available_locales,
            current_locales=current_locales,
            source_locale=self.source_locale,
        )

    def build_locale_reset_plan(self) -> LocaleResetPlan:
        return build_locale_reset_plan()

    def apply_locale_reset_plan(
        self,
        *,
        plan: LocaleResetPlan,
        clear_files_by_locale: Callable[[], None],
        clear_opened_files: Callable[[], None],
        clear_conflict_files: Callable[[], None],
        clear_conflict_sources: Callable[[], None],
        clear_conflict_notified: Callable[[], None],
        clear_current_file: Callable[[], None],
        clear_current_model: Callable[[], None],
        clear_table_model: Callable[[], None],
        clear_status_combo: Callable[[], None],
    ) -> None:
        apply_locale_reset_plan(
            plan=plan,
            clear_files_by_locale=clear_files_by_locale,
            clear_opened_files=clear_opened_files,
            clear_conflict_files=clear_conflict_files,
            clear_conflict_sources=clear_conflict_sources,
            clear_conflict_notified=clear_conflict_notified,
            clear_current_file=clear_current_file,
            clear_current_model=clear_current_model,
            clear_table_model=clear_table_model,
            clear_status_combo=clear_status_combo,
        )

    def build_post_locale_startup_plan(
        self, *, selected_locales: Iterable[str]
    ) -> PostLocaleStartupPlan:
        return build_post_locale_startup_plan(selected_locales=selected_locales)

    def run_post_locale_startup_tasks(
        self,
        *,
        plan: PostLocaleStartupPlan,
        run_cache_scan: Callable[[], None],
        run_auto_open: Callable[[], None],
    ) -> int:
        return run_post_locale_startup_tasks(
            plan=plan,
            run_cache_scan=run_cache_scan,
            run_auto_open=run_auto_open,
        )

    def build_tree_rebuild_plan(
        self,
        *,
        selected_locales: Iterable[str],
        resize_splitter: bool,
    ) -> TreeRebuildPlan:
        return build_tree_rebuild_plan(
            selected_locales=selected_locales,
            resize_splitter=resize_splitter,
        )

    def build_orphan_cache_warning(
        self,
        *,
        locale: str,
        orphan_paths: Sequence[Path],
        root: Path,
        preview_limit: int = 20,
    ) -> OrphanCacheWarningPlan:
        return build_orphan_cache_warning(
            locale=locale,
            orphan_paths=orphan_paths,
            root=root,
            preview_limit=preview_limit,
        )

    def build_cache_migration_schedule_plan(
        self,
        *,
        legacy_paths: Sequence[Path],
        batch_size: int,
    ) -> CacheMigrationSchedulePlan:
        return build_cache_migration_schedule_plan(
            legacy_paths=legacy_paths,
            batch_size=batch_size,
        )

    def build_cache_migration_batch_plan(
        self,
        *,
        pending_paths: Sequence[Path],
        batch_size: int,
        migrated_count: int,
    ) -> CacheMigrationBatchPlan:
        return build_cache_migration_batch_plan(
            pending_paths=pending_paths,
            batch_size=batch_size,
            migrated_count=migrated_count,
        )

    def execute_cache_migration_schedule(
        self,
        *,
        legacy_paths: Sequence[Path],
        batch_size: int,
        migrated_count: int,
        callbacks: CacheMigrationScheduleCallbacks,
    ) -> CacheMigrationScheduleExecution:
        return execute_cache_migration_schedule(
            legacy_paths=legacy_paths,
            batch_size=batch_size,
            migrated_count=migrated_count,
            callbacks=callbacks,
        )

    def execute_cache_migration_batch(
        self,
        *,
        pending_paths: Sequence[Path],
        batch_size: int,
        migrated_count: int,
        callbacks: CacheMigrationBatchCallbacks,
    ) -> CacheMigrationBatchExecution:
        return execute_cache_migration_batch(
            pending_paths=pending_paths,
            batch_size=batch_size,
            migrated_count=migrated_count,
            callbacks=callbacks,
        )


@dataclass(frozen=True, slots=True)
class LocaleSelectionPlan:
    selected_locales: tuple[str, ...]
    lazy_tree: bool
    changed: bool


@dataclass(frozen=True, slots=True)
class LocaleSwitchPlan:
    selected_locales: tuple[str, ...]
    lazy_tree: bool
    should_apply: bool
    reset_session_state: bool
    schedule_post_locale_tasks: bool
    tm_bootstrap_pending: bool


@dataclass(frozen=True, slots=True)
class LocaleResetPlan:
    clear_files_by_locale: bool
    clear_opened_files: bool
    clear_conflict_files: bool
    clear_conflict_sources: bool
    clear_conflict_notified: bool
    clear_current_file: bool
    clear_current_model: bool
    clear_table_model: bool
    clear_status_combo: bool


@dataclass(frozen=True, slots=True)
class PostLocaleStartupPlan:
    should_schedule: bool
    run_cache_scan: bool
    run_auto_open: bool
    task_count: int


@dataclass(frozen=True, slots=True)
class TreeRebuildPlan:
    lazy_tree: bool
    expand_all: bool
    preload_single_root: bool
    resize_splitter: bool


@dataclass(frozen=True, slots=True)
class OrphanCacheWarningPlan:
    window_title: str
    text: str
    informative_text: str
    detailed_text: str
    orphan_paths: tuple[Path, ...]


@dataclass(frozen=True, slots=True)
class CacheMigrationSchedulePlan:
    run_immediate: bool
    pending_paths: tuple[Path, ...]
    reset_migration_count: bool
    start_timer: bool


@dataclass(frozen=True, slots=True)
class CacheMigrationBatchPlan:
    batch_paths: tuple[Path, ...]
    remaining_paths: tuple[Path, ...]
    stop_timer: bool
    completion_status_message: str | None


@dataclass(frozen=True, slots=True)
class CacheMigrationScheduleCallbacks:
    migrate_all: Callable[[], int]
    warn: Callable[[str], None]
    start_timer: Callable[[], None]


@dataclass(frozen=True, slots=True)
class CacheMigrationBatchCallbacks:
    migrate_paths: Callable[[Sequence[Path]], int]
    warn: Callable[[str], None]
    stop_timer: Callable[[], None]
    show_status: Callable[[str], None]


@dataclass(frozen=True, slots=True)
class CacheMigrationScheduleExecution:
    pending_paths: tuple[Path, ...]
    migrated_count: int


@dataclass(frozen=True, slots=True)
class CacheMigrationBatchExecution:
    remaining_paths: tuple[Path, ...]
    migrated_count: int


def collect_draft_files(
    *,
    root: Path,
    cache_dir: str,
    cache_ext: str,
    translation_ext: str,
    has_drafts: Callable[[Path], bool],
    locales: Iterable[str] | None = None,
    opened_files: Collection[Path] | None = None,
) -> list[Path]:
    cache_roots = [path for path in _cache_roots(root, cache_dir) if path.exists()]
    if not cache_roots:
        return []
    locale_list = [loc for loc in locales or [] if loc]
    files: list[Path] = []
    for cache_root in cache_roots:
        cache_dirs = (
            [cache_root / loc for loc in locale_list] if locale_list else [cache_root]
        )
        for cache_dir_path in cache_dirs:
            if not cache_dir_path.exists():
                continue
            for cache_path in cache_dir_path.rglob(f"*{cache_ext}"):
                try:
                    rel = cache_path.relative_to(cache_root)
                except ValueError:
                    continue
                original = (root / rel).with_suffix(translation_ext)
                if not original.exists():
                    continue
                if opened_files is not None and original not in opened_files:
                    continue
                if has_drafts(cache_path):
                    files.append(original)
    return sorted(set(files))


def find_last_opened_file(
    *,
    root: Path,
    cache_dir: str,
    cache_ext: str,
    translation_ext: str,
    selected_locales: Iterable[str],
    read_last_opened: Callable[[Path], int],
) -> tuple[Path | None, int]:
    cache_roots = [path for path in _cache_roots(root, cache_dir) if path.exists()]
    if not cache_roots:
        return None, 0
    locales = [loc for loc in selected_locales if loc]
    if not locales:
        return None, 0
    best_ts = 0
    best_path: Path | None = None
    scanned = 0
    for cache_root in cache_roots:
        for locale in locales:
            cache_dir_path = cache_root / locale
            if not cache_dir_path.exists():
                continue
            for cache_path in cache_dir_path.rglob(f"*{cache_ext}"):
                scanned += 1
                ts = read_last_opened(cache_path)
                if ts <= 0:
                    continue
                try:
                    rel = cache_path.relative_to(cache_root)
                except ValueError:
                    continue
                original = (root / rel).with_suffix(translation_ext)
                if not original.exists():
                    continue
                if ts > best_ts:
                    best_ts = ts
                    best_path = original
    return best_path, scanned


def collect_orphan_cache_paths(
    *,
    root: Path,
    cache_dir: str,
    cache_ext: str,
    translation_ext: str,
    selected_locales: Iterable[str],
    warned_locales: Collection[str] | None = None,
) -> dict[str, list[Path]]:
    cache_roots = [path for path in _cache_roots(root, cache_dir) if path.exists()]
    if not cache_roots:
        return {}
    warned = set(warned_locales or ())
    out: dict[str, list[Path]] = {}
    for locale in [loc for loc in selected_locales if loc]:
        if locale in warned:
            continue
        missing_set: set[Path] = set()
        for cache_root in cache_roots:
            locale_cache = cache_root / locale
            if not locale_cache.exists():
                continue
            for cache_path in locale_cache.rglob(f"*{cache_ext}"):
                try:
                    rel = cache_path.relative_to(cache_root)
                except ValueError:
                    continue
                original = (root / rel).with_suffix(translation_ext)
                if not original.exists():
                    missing_set.add(cache_path)
        if missing_set:
            out[locale] = sorted(missing_set)
    return out


def build_orphan_cache_warning(
    *,
    locale: str,
    orphan_paths: Sequence[Path],
    root: Path,
    preview_limit: int = 20,
) -> OrphanCacheWarningPlan:
    rels: list[str] = []
    for path in orphan_paths:
        try:
            rel = path.relative_to(root)
        except ValueError:
            rel = path
        rels.append(rel.as_posix())
    preview = "\n".join(rels[:preview_limit])
    if len(rels) > preview_limit:
        preview = f"{preview}\n... ({len(rels) - preview_limit} more)"
    return OrphanCacheWarningPlan(
        window_title="Orphan cache files",
        text=f"Locale {locale} has cache files without source files.",
        informative_text="Purge deletes those cache files. Dismiss keeps them.",
        detailed_text=preview,
        orphan_paths=tuple(orphan_paths),
    )


def build_cache_migration_schedule_plan(
    *,
    legacy_paths: Sequence[Path],
    batch_size: int,
) -> CacheMigrationSchedulePlan:
    paths = tuple(legacy_paths)
    if not paths:
        return CacheMigrationSchedulePlan(
            run_immediate=False,
            pending_paths=(),
            reset_migration_count=False,
            start_timer=False,
        )
    if len(paths) <= batch_size:
        return CacheMigrationSchedulePlan(
            run_immediate=True,
            pending_paths=(),
            reset_migration_count=False,
            start_timer=False,
        )
    return CacheMigrationSchedulePlan(
        run_immediate=False,
        pending_paths=paths,
        reset_migration_count=True,
        start_timer=True,
    )


def build_cache_migration_batch_plan(
    *,
    pending_paths: Sequence[Path],
    batch_size: int,
    migrated_count: int,
) -> CacheMigrationBatchPlan:
    paths = tuple(pending_paths)
    if not paths:
        message = None
        if migrated_count > 0:
            message = f"Migrated {migrated_count} cache file(s)."
        return CacheMigrationBatchPlan(
            batch_paths=(),
            remaining_paths=(),
            stop_timer=True,
            completion_status_message=message,
        )
    batch = paths[:batch_size]
    remaining = paths[batch_size:]
    return CacheMigrationBatchPlan(
        batch_paths=batch,
        remaining_paths=remaining,
        stop_timer=False,
        completion_status_message=None,
    )


def execute_cache_migration_schedule(
    *,
    legacy_paths: Sequence[Path],
    batch_size: int,
    migrated_count: int,
    callbacks: CacheMigrationScheduleCallbacks,
) -> CacheMigrationScheduleExecution:
    plan = build_cache_migration_schedule_plan(
        legacy_paths=legacy_paths,
        batch_size=batch_size,
    )
    if plan.run_immediate:
        try:
            delta = callbacks.migrate_all()
        except Exception as exc:
            callbacks.warn(str(exc))
            return CacheMigrationScheduleExecution(
                pending_paths=(),
                migrated_count=migrated_count,
            )
        return CacheMigrationScheduleExecution(
            pending_paths=(),
            migrated_count=migrated_count + max(0, int(delta)),
        )
    if plan.start_timer:
        callbacks.start_timer()
    next_count = 0 if plan.reset_migration_count else migrated_count
    return CacheMigrationScheduleExecution(
        pending_paths=plan.pending_paths,
        migrated_count=next_count,
    )


def execute_cache_migration_batch(
    *,
    pending_paths: Sequence[Path],
    batch_size: int,
    migrated_count: int,
    callbacks: CacheMigrationBatchCallbacks,
) -> CacheMigrationBatchExecution:
    plan = build_cache_migration_batch_plan(
        pending_paths=pending_paths,
        batch_size=batch_size,
        migrated_count=migrated_count,
    )
    if plan.stop_timer:
        callbacks.stop_timer()
        if plan.completion_status_message:
            callbacks.show_status(plan.completion_status_message)
        return CacheMigrationBatchExecution(
            remaining_paths=(),
            migrated_count=migrated_count,
        )
    try:
        delta = callbacks.migrate_paths(plan.batch_paths)
    except Exception as exc:
        callbacks.stop_timer()
        callbacks.warn(str(exc))
        return CacheMigrationBatchExecution(
            remaining_paths=tuple(pending_paths),
            migrated_count=migrated_count,
        )
    return CacheMigrationBatchExecution(
        remaining_paths=plan.remaining_paths,
        migrated_count=migrated_count + max(0, int(delta)),
    )


def normalize_selected_locales(
    *,
    requested_locales: Iterable[str],
    available_locales: Iterable[str],
    source_locale: str = "EN",
) -> list[str]:
    allowed = {loc for loc in available_locales if loc and loc != source_locale}
    selected: list[str] = []
    seen: set[str] = set()
    for code in requested_locales:
        if not code or code not in allowed or code in seen:
            continue
        selected.append(code)
        seen.add(code)
    return selected


def use_lazy_tree(selected_locales: Iterable[str]) -> bool:
    count = 0
    for code in selected_locales:
        if not code:
            continue
        count += 1
        if count > 1:
            return True
    return False


def resolve_requested_locales(
    *,
    requested_locales: Iterable[str] | None,
    last_locales: Iterable[str],
    available_locales: Iterable[str],
    smoke_mode: bool,
    source_locale: str = "EN",
) -> list[str] | None:
    if requested_locales is not None:
        return list(requested_locales)
    if not smoke_mode:
        return None
    available = list(available_locales)
    preferred = normalize_selected_locales(
        requested_locales=last_locales,
        available_locales=available,
        source_locale=source_locale,
    )
    if preferred:
        return preferred
    fallback = normalize_selected_locales(
        requested_locales=available,
        available_locales=available,
        source_locale=source_locale,
    )
    if not fallback:
        return []
    return [fallback[0]]


def build_locale_selection_plan(
    *,
    requested_locales: Iterable[str],
    available_locales: Iterable[str],
    current_locales: Iterable[str] = (),
    source_locale: str = "EN",
) -> LocaleSelectionPlan | None:
    selected = normalize_selected_locales(
        requested_locales=requested_locales,
        available_locales=available_locales,
        source_locale=source_locale,
    )
    if not selected:
        return None
    current = normalize_selected_locales(
        requested_locales=current_locales,
        available_locales=available_locales,
        source_locale=source_locale,
    )
    return LocaleSelectionPlan(
        selected_locales=tuple(selected),
        lazy_tree=use_lazy_tree(selected),
        changed=(selected != current),
    )


def build_locale_switch_plan(
    *,
    requested_locales: Iterable[str],
    available_locales: Iterable[str],
    current_locales: Iterable[str],
    source_locale: str = "EN",
) -> LocaleSwitchPlan | None:
    selection = build_locale_selection_plan(
        requested_locales=requested_locales,
        available_locales=available_locales,
        current_locales=current_locales,
        source_locale=source_locale,
    )
    if selection is None:
        return None
    should_apply = selection.changed
    return LocaleSwitchPlan(
        selected_locales=selection.selected_locales,
        lazy_tree=selection.lazy_tree,
        should_apply=should_apply,
        reset_session_state=should_apply,
        schedule_post_locale_tasks=should_apply,
        tm_bootstrap_pending=bool(selection.selected_locales),
    )


def build_locale_reset_plan() -> LocaleResetPlan:
    return LocaleResetPlan(
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


def apply_locale_reset_plan(
    *,
    plan: LocaleResetPlan,
    clear_files_by_locale: Callable[[], None],
    clear_opened_files: Callable[[], None],
    clear_conflict_files: Callable[[], None],
    clear_conflict_sources: Callable[[], None],
    clear_conflict_notified: Callable[[], None],
    clear_current_file: Callable[[], None],
    clear_current_model: Callable[[], None],
    clear_table_model: Callable[[], None],
    clear_status_combo: Callable[[], None],
) -> None:
    if plan.clear_files_by_locale:
        clear_files_by_locale()
    if plan.clear_opened_files:
        clear_opened_files()
    if plan.clear_conflict_files:
        clear_conflict_files()
    if plan.clear_conflict_sources:
        clear_conflict_sources()
    if plan.clear_conflict_notified:
        clear_conflict_notified()
    if plan.clear_current_file:
        clear_current_file()
    if plan.clear_current_model:
        clear_current_model()
    if plan.clear_table_model:
        clear_table_model()
    if plan.clear_status_combo:
        clear_status_combo()


def build_post_locale_startup_plan(
    *, selected_locales: Iterable[str]
) -> PostLocaleStartupPlan:
    has_locales = any(code for code in selected_locales)
    if not has_locales:
        return PostLocaleStartupPlan(
            should_schedule=False,
            run_cache_scan=False,
            run_auto_open=False,
            task_count=0,
        )
    return PostLocaleStartupPlan(
        should_schedule=True,
        run_cache_scan=True,
        run_auto_open=True,
        task_count=2,
    )


def run_post_locale_startup_tasks(
    *,
    plan: PostLocaleStartupPlan,
    run_cache_scan: Callable[[], None],
    run_auto_open: Callable[[], None],
) -> int:
    if not plan.should_schedule:
        return 0
    executed = 0
    if plan.run_cache_scan:
        run_cache_scan()
        executed += 1
    if plan.run_auto_open:
        run_auto_open()
        executed += 1
    return executed


def build_tree_rebuild_plan(
    *,
    selected_locales: Iterable[str],
    resize_splitter: bool,
) -> TreeRebuildPlan:
    selected = [code for code in selected_locales if code]
    lazy_tree = use_lazy_tree(selected)
    preload_single_root = lazy_tree and len(selected) == 1
    return TreeRebuildPlan(
        lazy_tree=lazy_tree,
        expand_all=not lazy_tree,
        preload_single_root=preload_single_root,
        resize_splitter=resize_splitter,
    )
