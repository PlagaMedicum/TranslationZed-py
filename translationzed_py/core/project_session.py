"""Project session module."""

from __future__ import annotations

import time
from collections.abc import Callable, Collection, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from translationzed_py.core.app_config import LEGACY_CACHE_DIR


def _cache_roots(root: Path, cache_dir: str) -> tuple[Path, ...]:
    """Execute cache roots."""
    primary = root / cache_dir
    legacy = root / LEGACY_CACHE_DIR
    if legacy == primary:
        return (primary,)
    return (primary, legacy)


@dataclass(frozen=True, slots=True)
class ProjectSessionService:
    """Represent ProjectSessionService."""

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
        """Collect draft files."""
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
        """Find last opened file."""
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
        """Collect orphan cache paths."""
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
        """Normalize selected locales."""
        return normalize_selected_locales(
            requested_locales=requested_locales,
            available_locales=available_locales,
            source_locale=self.source_locale,
        )

    def use_lazy_tree(self, selected_locales: Iterable[str]) -> bool:
        """Execute use lazy tree."""
        return use_lazy_tree(selected_locales)

    def resolve_requested_locales(
        self,
        *,
        requested_locales: Iterable[str] | None,
        last_locales: Iterable[str],
        available_locales: Iterable[str],
        smoke_mode: bool,
    ) -> list[str] | None:
        """Resolve requested locales."""
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
        """Build locale selection plan."""
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
        """Build locale switch plan."""
        return build_locale_switch_plan(
            requested_locales=requested_locales,
            available_locales=available_locales,
            current_locales=current_locales,
            source_locale=self.source_locale,
        )

    def build_locale_reset_plan(self) -> LocaleResetPlan:
        """Build locale reset plan."""
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
        """Apply locale reset plan."""
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
        """Build post locale startup plan."""
        return build_post_locale_startup_plan(selected_locales=selected_locales)

    def run_post_locale_startup_tasks(
        self,
        *,
        plan: PostLocaleStartupPlan,
        run_cache_scan: Callable[[], None],
        run_auto_open: Callable[[], None],
    ) -> int:
        """Run post locale startup tasks."""
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
        """Build tree rebuild plan."""
        return build_tree_rebuild_plan(
            selected_locales=selected_locales,
            resize_splitter=resize_splitter,
        )

    def build_crash_recovery_report(
        self,
        *,
        root: Path,
        selected_locales: Iterable[str],
        now_ms: Callable[[], int] | None = None,
    ) -> CrashRecoveryReport | None:
        """Build crash recovery report."""
        return build_crash_recovery_report(
            root=root,
            cache_dir=self.cache_dir,
            cache_ext=self.cache_ext,
            translation_ext=self.translation_ext,
            selected_locales=selected_locales,
            has_drafts=self.has_drafts,
            now_ms=now_ms,
        )

    def build_crash_recovery_detection_plan(
        self,
        *,
        root: Path,
        selected_locales: Iterable[str],
        startup_accepted: bool,
        previous_session_unclean: bool,
        interrupted_draft_marker: bool,
        now_ms: Callable[[], int] | None = None,
    ) -> CrashRecoveryDetectionPlan:
        """Build crash recovery detection plan."""
        report = self.build_crash_recovery_report(
            root=root,
            selected_locales=selected_locales,
            now_ms=now_ms,
        )
        return build_crash_recovery_detection_plan(
            startup_accepted=startup_accepted,
            report=report,
            previous_session_unclean=previous_session_unclean,
            interrupted_draft_marker=interrupted_draft_marker,
        )

    def build_crash_recovery_apply_plan(
        self,
        *,
        root: Path,
        report: CrashRecoveryReport | None,
        decision: str,
    ) -> CrashRecoveryApplyPlan:
        """Build crash recovery apply plan."""
        return build_crash_recovery_apply_plan(
            root=root,
            cache_dir=self.cache_dir,
            cache_ext=self.cache_ext,
            report=report,
            decision=decision,
        )

    def execute_crash_recovery_apply_plan(
        self,
        *,
        plan: CrashRecoveryApplyPlan,
        unlink_cache_path: Callable[[Path], None] | None = None,
    ) -> CrashRecoveryApplyExecution:
        """Execute crash recovery apply plan."""
        return execute_crash_recovery_apply_plan(
            plan=plan,
            unlink_cache_path=unlink_cache_path,
        )

    def build_orphan_cache_warning(
        self,
        *,
        locale: str,
        orphan_paths: Sequence[Path],
        root: Path,
        preview_limit: int = 20,
    ) -> OrphanCacheWarningPlan:
        """Build orphan cache warning."""
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
        """Build cache migration schedule plan."""
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
        """Build cache migration batch plan."""
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
        """Execute execute cache migration schedule."""
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
        """Execute execute cache migration batch."""
        return execute_cache_migration_batch(
            pending_paths=pending_paths,
            batch_size=batch_size,
            migrated_count=migrated_count,
            callbacks=callbacks,
        )


@dataclass(frozen=True, slots=True)
class LocaleSelectionPlan:
    """Represent LocaleSelectionPlan."""

    selected_locales: tuple[str, ...]
    lazy_tree: bool
    changed: bool


@dataclass(frozen=True, slots=True)
class LocaleSwitchPlan:
    """Represent LocaleSwitchPlan."""

    selected_locales: tuple[str, ...]
    lazy_tree: bool
    should_apply: bool
    reset_session_state: bool
    schedule_post_locale_tasks: bool
    tm_bootstrap_pending: bool


@dataclass(frozen=True, slots=True)
class LocaleResetPlan:
    """Represent LocaleResetPlan."""

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
    """Represent PostLocaleStartupPlan."""

    should_schedule: bool
    run_cache_scan: bool
    run_auto_open: bool
    task_count: int


@dataclass(frozen=True, slots=True)
class TreeRebuildPlan:
    """Represent TreeRebuildPlan."""

    lazy_tree: bool
    expand_all: bool
    preload_single_root: bool
    resize_splitter: bool


@dataclass(frozen=True, slots=True)
class CrashRecoveryAffectedFile:
    """Represent CrashRecoveryAffectedFile."""

    file_path: str
    locale: str
    draft_value_count: int
    status_only_count: int
    cache_mtime_ns: int
    warning: str


@dataclass(frozen=True, slots=True)
class CrashRecoveryReport:
    """Represent CrashRecoveryReport."""

    project_root: str
    generated_at_ms: int
    affected_files: tuple[CrashRecoveryAffectedFile, ...]
    total_files: int
    total_draft_values: int
    total_status_only: int


@dataclass(frozen=True, slots=True)
class CrashRecoveryDetectionPlan:
    """Represent CrashRecoveryDetectionPlan."""

    run_recovery_flow: bool
    report: CrashRecoveryReport | None


@dataclass(frozen=True, slots=True)
class CrashRecoveryApplyPlan:
    """Represent CrashRecoveryApplyPlan."""

    decision: str
    continue_startup: bool
    discard_cache_paths: tuple[Path, ...]


@dataclass(frozen=True, slots=True)
class CrashRecoveryApplyExecution:
    """Represent CrashRecoveryApplyExecution."""

    decision: str
    continue_startup: bool
    discarded_cache_paths: tuple[Path, ...]
    failed_cache_paths: tuple[Path, ...]
    failure_message: str | None


@dataclass(frozen=True, slots=True)
class OrphanCacheWarningPlan:
    """Represent OrphanCacheWarningPlan."""

    window_title: str
    text: str
    informative_text: str
    detailed_text: str
    orphan_paths: tuple[Path, ...]


@dataclass(frozen=True, slots=True)
class CacheMigrationSchedulePlan:
    """Represent CacheMigrationSchedulePlan."""

    run_immediate: bool
    pending_paths: tuple[Path, ...]
    reset_migration_count: bool
    start_timer: bool


@dataclass(frozen=True, slots=True)
class CacheMigrationBatchPlan:
    """Represent CacheMigrationBatchPlan."""

    batch_paths: tuple[Path, ...]
    remaining_paths: tuple[Path, ...]
    stop_timer: bool
    completion_status_message: str | None


@dataclass(frozen=True, slots=True)
class CacheMigrationScheduleCallbacks:
    """Represent CacheMigrationScheduleCallbacks."""

    migrate_all: Callable[[], int]
    warn: Callable[[str], None]
    start_timer: Callable[[], None]


@dataclass(frozen=True, slots=True)
class CacheMigrationBatchCallbacks:
    """Represent CacheMigrationBatchCallbacks."""

    migrate_paths: Callable[[Sequence[Path]], int]
    warn: Callable[[str], None]
    stop_timer: Callable[[], None]
    show_status: Callable[[str], None]


@dataclass(frozen=True, slots=True)
class CacheMigrationScheduleExecution:
    """Represent CacheMigrationScheduleExecution."""

    pending_paths: tuple[Path, ...]
    migrated_count: int


@dataclass(frozen=True, slots=True)
class CacheMigrationBatchExecution:
    """Represent CacheMigrationBatchExecution."""

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
    """Collect draft files."""
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
    """Find last opened file."""
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
    """Collect orphan cache paths."""
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


def build_crash_recovery_report(
    *,
    root: Path,
    cache_dir: str,
    cache_ext: str,
    translation_ext: str,
    selected_locales: Iterable[str],
    has_drafts: Callable[[Path], bool],
    now_ms: Callable[[], int] | None = None,
) -> CrashRecoveryReport | None:
    """Build crash recovery report from draft-bearing cache files."""
    cache_roots = [path for path in _cache_roots(root, cache_dir) if path.exists()]
    if not cache_roots:
        return None
    locales = _ordered_non_empty(selected_locales)
    if not locales:
        return None
    affected: list[CrashRecoveryAffectedFile] = []
    seen_originals: set[Path] = set()
    for cache_root in cache_roots:
        for locale in locales:
            cache_locale = cache_root / locale
            if not cache_locale.exists():
                continue
            for cache_path in sorted(cache_locale.rglob(f"*{cache_ext}")):
                if not has_drafts(cache_path):
                    continue
                original = _original_path_from_cache(
                    root=root,
                    cache_root=cache_root,
                    cache_path=cache_path,
                    translation_ext=translation_ext,
                )
                if original is None or not original.exists():
                    continue
                if original in seen_originals:
                    continue
                seen_originals.add(original)
                draft_count, status_only_count = _read_cache_entry_counts(
                    root=root,
                    file_path=original,
                )
                warning = ""
                if draft_count <= 0:
                    warning = "draft_flag_without_cache_rows"
                cache_mtime_ns = _safe_mtime_ns(cache_path)
                affected.append(
                    CrashRecoveryAffectedFile(
                        file_path=_display_file_path(root=root, file_path=original),
                        locale=locale,
                        draft_value_count=draft_count,
                        status_only_count=status_only_count,
                        cache_mtime_ns=cache_mtime_ns,
                        warning=warning,
                    )
                )
    if not affected:
        return None
    affected.sort(key=lambda rec: (rec.locale, rec.file_path))
    total_draft_values = sum(rec.draft_value_count for rec in affected)
    if total_draft_values <= 0:
        return None
    total_status_only = sum(rec.status_only_count for rec in affected)
    now = now_ms or (lambda: int(time.time() * 1000))
    return CrashRecoveryReport(
        project_root=str(root),
        generated_at_ms=max(0, int(now())),
        affected_files=tuple(affected),
        total_files=len(affected),
        total_draft_values=total_draft_values,
        total_status_only=total_status_only,
    )


def build_crash_recovery_detection_plan(
    *,
    startup_accepted: bool,
    report: CrashRecoveryReport | None,
    previous_session_unclean: bool,
    interrupted_draft_marker: bool,
) -> CrashRecoveryDetectionPlan:
    """Build crash recovery detection plan."""
    has_interrupted_signal = previous_session_unclean or interrupted_draft_marker
    run_recovery_flow = (
        startup_accepted
        and has_interrupted_signal
        and report is not None
        and report.total_draft_values > 0
    )
    return CrashRecoveryDetectionPlan(
        run_recovery_flow=run_recovery_flow,
        report=report if run_recovery_flow else None,
    )


def build_crash_recovery_apply_plan(
    *,
    root: Path,
    cache_dir: str,
    cache_ext: str,
    report: CrashRecoveryReport | None,
    decision: str,
) -> CrashRecoveryApplyPlan:
    """Build crash recovery decision application plan."""
    normalized = str(decision or "").strip().lower()
    if normalized not in {"restore", "discard", "cancel"}:
        raise ValueError(f"Unsupported crash recovery decision: {decision!r}")
    if normalized == "cancel":
        return CrashRecoveryApplyPlan(
            decision=normalized,
            continue_startup=False,
            discard_cache_paths=(),
        )
    if normalized != "discard" or report is None:
        return CrashRecoveryApplyPlan(
            decision=normalized,
            continue_startup=True,
            discard_cache_paths=(),
        )
    paths = _recovery_discard_cache_paths(
        root=root,
        cache_dir=cache_dir,
        cache_ext=cache_ext,
        report=report,
    )
    return CrashRecoveryApplyPlan(
        decision=normalized,
        continue_startup=True,
        discard_cache_paths=paths,
    )


def execute_crash_recovery_apply_plan(
    *,
    plan: CrashRecoveryApplyPlan,
    unlink_cache_path: Callable[[Path], None] | None = None,
) -> CrashRecoveryApplyExecution:
    """Execute crash recovery decision application plan."""
    if unlink_cache_path is None:

        def _default_unlink(path: Path) -> None:
            path.unlink(missing_ok=True)

        unlink_cache_path = _default_unlink
    if not plan.continue_startup or not plan.discard_cache_paths:
        return CrashRecoveryApplyExecution(
            decision=plan.decision,
            continue_startup=plan.continue_startup,
            discarded_cache_paths=(),
            failed_cache_paths=(),
            failure_message=None,
        )
    discarded: list[Path] = []
    failed: list[Path] = []
    for path in plan.discard_cache_paths:
        try:
            unlink_cache_path(path)
            discarded.append(path)
        except Exception:
            failed.append(path)
    message = None
    if failed:
        message = _format_recovery_discard_failure(failed)
    return CrashRecoveryApplyExecution(
        decision=plan.decision,
        continue_startup=plan.continue_startup,
        discarded_cache_paths=tuple(discarded),
        failed_cache_paths=tuple(failed),
        failure_message=message,
    )


def _recovery_discard_cache_paths(
    *,
    root: Path,
    cache_dir: str,
    cache_ext: str,
    report: CrashRecoveryReport,
) -> tuple[Path, ...]:
    out: set[Path] = set()
    for item in report.affected_files:
        file_path = Path(item.file_path)
        original = file_path if file_path.is_absolute() else (root / file_path)
        try:
            rel = original.relative_to(root)
        except ValueError:
            continue
        for cache_root in _cache_roots(root, cache_dir):
            out.add((cache_root / rel).with_suffix(cache_ext))
    return tuple(sorted(out))


def _format_recovery_discard_failure(paths: Sequence[Path]) -> str:
    preview = [path.as_posix() for path in paths[:20]]
    text = "\n".join(preview)
    if len(paths) > 20:
        text = f"{text}\n... ({len(paths) - 20} more)"
    return text


def _ordered_non_empty(values: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        code = str(value or "").strip()
        if not code or code in seen:
            continue
        seen.add(code)
        out.append(code)
    return out


def _original_path_from_cache(
    *,
    root: Path,
    cache_root: Path,
    cache_path: Path,
    translation_ext: str,
) -> Path | None:
    try:
        rel = cache_path.relative_to(cache_root)
    except ValueError:
        return None
    return (root / rel).with_suffix(translation_ext)


def _display_file_path(*, root: Path, file_path: Path) -> str:
    try:
        rel = file_path.relative_to(root)
    except ValueError:
        rel = file_path
    return rel.as_posix()


def _safe_mtime_ns(path: Path) -> int:
    try:
        return int(path.stat().st_mtime_ns)
    except OSError:
        return 0


def _read_cache_entry_counts(*, root: Path, file_path: Path) -> tuple[int, int]:
    from translationzed_py.core import status_cache as _status_cache

    rows = _status_cache.read(root, file_path)
    draft = 0
    status_only = 0
    for item in rows.values():
        if item.value is None:
            status_only += 1
        else:
            draft += 1
    return draft, status_only


def build_orphan_cache_warning(
    *,
    locale: str,
    orphan_paths: Sequence[Path],
    root: Path,
    preview_limit: int = 20,
) -> OrphanCacheWarningPlan:
    """Build orphan cache warning."""
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
    """Build cache migration schedule plan."""
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
    """Build cache migration batch plan."""
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
    """Execute execute cache migration schedule."""
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
    """Execute execute cache migration batch."""
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
    """Normalize selected locales."""
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
    """Execute use lazy tree."""
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
    """Resolve requested locales."""
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
    """Build locale selection plan."""
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
    """Build locale switch plan."""
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
    """Build locale reset plan."""
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
    """Apply locale reset plan."""
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
    """Build post locale startup plan."""
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
    """Run post locale startup tasks."""
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
    """Build tree rebuild plan."""
    selected = [code for code in selected_locales if code]
    lazy_tree = use_lazy_tree(selected)
    preload_single_root = lazy_tree and len(selected) == 1
    return TreeRebuildPlan(
        lazy_tree=lazy_tree,
        expand_all=not lazy_tree,
        preload_single_root=preload_single_root,
        resize_splitter=resize_splitter,
    )
