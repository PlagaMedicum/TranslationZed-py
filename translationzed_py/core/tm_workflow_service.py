from __future__ import annotations

import html
import re
from collections import OrderedDict
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

from .project_scanner import LocaleMeta
from .tm_import_sync import LocaleResolver, TMImportSyncReport, sync_import_folder
from .tm_preferences import (
    TMPreferencesActions,
    TMPreferencesApplyReport,
    actions_from_values,
    apply_actions,
)
from .tm_query import (
    TMQueryKey,
    TMQueryPolicy,
    current_key_from_lookup,
    filter_matches,
    has_enabled_origins,
    make_cache_key,
    normalize_min_score,
    origins_for,
    suggestion_limit_for,
)
from .tm_rebuild import (
    TMRebuildLocale,
    TMRebuildResult,
    collect_rebuild_locales,
    format_rebuild_status,
    rebuild_project_tm,
)
from .tm_store import TMImportFile, TMMatch, TMStore


@dataclass(frozen=True, slots=True)
class TMPendingBatch:
    file_key: str
    target_locale: str
    rows: tuple[tuple[str, str, str, int | None], ...]


@dataclass(frozen=True, slots=True)
class TMQueryPlan:
    mode: Literal["disabled", "no_lookup", "cached", "query"]
    message: str
    cache_key: TMQueryKey | None = None
    matches: list[TMMatch] | None = None


@dataclass(frozen=True, slots=True)
class TMSuggestionItem:
    match: TMMatch
    label: str
    tooltip_html: str


@dataclass(frozen=True, slots=True)
class TMSuggestionsView:
    message: str
    items: tuple[TMSuggestionItem, ...]


@dataclass(frozen=True, slots=True)
class TMLocaleVariantItem:
    locale_code: str
    locale_name: str
    status_tag: str
    value: str
    label: str
    tooltip_html: str


@dataclass(frozen=True, slots=True)
class TMLocaleVariantsView:
    message: str
    items: tuple[TMLocaleVariantItem, ...]


@dataclass(frozen=True, slots=True)
class TMQueryRequest:
    source_text: str
    source_locale: str
    target_locale: str
    min_score: int
    origins: tuple[str, ...]
    limit: int


@dataclass(frozen=True, slots=True)
class TMApplyPlan:
    target_text: str
    mark_for_review: bool


@dataclass(frozen=True, slots=True)
class TMSelectionPlan:
    apply_enabled: bool
    source_preview: str
    target_preview: str
    query_terms: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TMFilterPlan:
    policy: TMQueryPolicy
    prefs_extras: dict[str, str]


@dataclass(frozen=True, slots=True)
class TMUpdatePlan:
    run_update: bool
    stop_timer: bool
    start_timer: bool


@dataclass(frozen=True, slots=True)
class TMRefreshPlan:
    run_update: bool
    flush_current_file: bool
    query_plan: TMQueryPlan | None


class TMDiagnosticsStore(Protocol):
    @property
    def db_path(self) -> Path: ...

    def list_import_files(self) -> list[TMImportFile]: ...

    def query(
        self,
        source_text: str,
        *,
        source_locale: str,
        target_locale: str,
        limit: int = ...,
        min_score: int = ...,
        origins: Iterable[str] | None = ...,
    ) -> list[TMMatch]: ...


@dataclass(slots=True)
class TMWorkflowService:
    cache_limit: int = 128
    _cache: OrderedDict[TMQueryKey, list[TMMatch]] = field(
        init=False,
        repr=False,
        default_factory=OrderedDict,
    )
    _pending: dict[str, dict[str, tuple[str, str, str, int | None]]] = field(
        init=False,
        repr=False,
        default_factory=dict,
    )

    def clear_cache(self) -> None:
        self._cache.clear()

    def queue_updates(self, path: str, rows: Iterable[tuple[str, ...]]) -> None:
        self._cache.clear()
        bucket = self._pending.setdefault(path, {})
        for row in rows:
            if len(row) == 3:
                key, source_text, value_text = row
                row_status: int | None = None
            elif len(row) == 4:
                key, source_text, value_text, status_raw = row
                try:
                    row_status = int(status_raw)
                except (TypeError, ValueError):
                    row_status = None
            else:
                continue
            bucket[key] = (key, source_text, value_text, row_status)

    def pending_batches(
        self,
        *,
        locale_for_path: Callable[[str], str | None],
        paths: Iterable[str] | None = None,
    ) -> list[TMPendingBatch]:
        wanted = None if paths is None else set(paths)
        batches: list[TMPendingBatch] = []
        for file_key, by_key in self._pending.items():
            if wanted is not None and file_key not in wanted:
                continue
            if not by_key:
                continue
            locale = locale_for_path(file_key)
            if not locale:
                continue
            batches.append(
                TMPendingBatch(
                    file_key=file_key,
                    target_locale=locale,
                    rows=tuple(by_key.values()),
                )
            )
        return batches

    def mark_batch_flushed(self, file_key: str) -> None:
        self._pending.pop(file_key, None)

    def plan_query(
        self,
        *,
        lookup: tuple[str, str] | None,
        policy: TMQueryPolicy,
    ) -> TMQueryPlan:
        if not has_enabled_origins(policy):
            return TMQueryPlan(mode="disabled", message="No TM origins enabled.")
        if lookup is None:
            return TMQueryPlan(
                mode="no_lookup", message="Select a row to see TM suggestions."
            )
        source_text, locale = lookup
        cache_key = make_cache_key(
            source_text,
            target_locale=locale,
            policy=policy,
        )
        matches = self._cache.get(cache_key)
        if matches is not None:
            return TMQueryPlan(
                mode="cached",
                message="TM suggestions",
                cache_key=cache_key,
                matches=matches,
            )
        return TMQueryPlan(
            mode="query",
            message="Searching TM...",
            cache_key=cache_key,
            matches=None,
        )

    def accept_query_result(
        self,
        *,
        cache_key: TMQueryKey,
        matches: list[TMMatch],
        lookup: tuple[str, str] | None,
        policy: TMQueryPolicy,
    ) -> bool:
        self._cache[cache_key] = matches
        while len(self._cache) > self.cache_limit:
            self._cache.popitem(last=False)
        current_key = current_key_from_lookup(lookup, policy=policy)
        return current_key == cache_key

    def filter_matches(
        self, matches: list[TMMatch], *, policy: TMQueryPolicy
    ) -> list[TMMatch]:
        return filter_matches(matches, policy=policy)

    def query_terms(self, source_text: str) -> list[str]:
        return query_terms(source_text)

    def build_preferences_actions(
        self, values: dict[str, object]
    ) -> TMPreferencesActions:
        return actions_from_values(values)

    def apply_preferences_actions(
        self,
        *,
        store: TMStore,
        actions: TMPreferencesActions,
        copy_to_import_dir: Callable[[Path], Path],
    ) -> TMPreferencesApplyReport:
        return apply_actions(
            store,
            actions,
            copy_to_import_dir=copy_to_import_dir,
        )

    def sync_import_folder(
        self,
        *,
        store: TMStore,
        tm_dir: Path,
        resolve_locales: LocaleResolver,
        only_paths: set[Path] | None = None,
        pending_only: bool = False,
    ) -> TMImportSyncReport:
        return sync_import_folder(
            store,
            tm_dir,
            resolve_locales=resolve_locales,
            only_paths=only_paths,
            pending_only=pending_only,
        )

    def collect_rebuild_locales(
        self,
        *,
        locale_map: Mapping[str, LocaleMeta],
        selected_locales: list[str] | tuple[str, ...] | set[str],
    ) -> tuple[list[TMRebuildLocale], str]:
        return collect_rebuild_locales(locale_map, selected_locales)

    def rebuild_project_tm(
        self,
        root: Path,
        locales: list[TMRebuildLocale],
        *,
        source_locale: str,
        en_encoding: str,
        batch_size: int = 1000,
    ) -> TMRebuildResult:
        return rebuild_project_tm(
            root,
            locales,
            source_locale=source_locale,
            en_encoding=en_encoding,
            batch_size=batch_size,
        )

    def format_rebuild_status(self, result: TMRebuildResult) -> str:
        return format_rebuild_status(result)

    def build_lookup(
        self,
        *,
        source_text: str,
        target_locale: str | None,
    ) -> tuple[str, str] | None:
        return build_lookup(source_text=source_text, target_locale=target_locale)

    def build_update_plan(
        self,
        *,
        has_store: bool,
        panel_index: int,
        timer_active: bool,
        tm_panel_index: int = 1,
    ) -> TMUpdatePlan:
        run_update = has_store and panel_index == tm_panel_index
        if not run_update:
            return TMUpdatePlan(
                run_update=False,
                stop_timer=False,
                start_timer=False,
            )
        return TMUpdatePlan(
            run_update=True,
            stop_timer=timer_active,
            start_timer=True,
        )

    def build_refresh_plan(
        self,
        *,
        has_store: bool,
        panel_index: int,
        lookup: tuple[str, str] | None,
        policy: TMQueryPolicy,
        has_current_file: bool,
        tm_panel_index: int = 1,
    ) -> TMRefreshPlan:
        update = self.build_update_plan(
            has_store=has_store,
            panel_index=panel_index,
            timer_active=False,
            tm_panel_index=tm_panel_index,
        )
        if not update.run_update:
            return TMRefreshPlan(
                run_update=False,
                flush_current_file=False,
                query_plan=None,
            )
        return TMRefreshPlan(
            run_update=True,
            flush_current_file=has_current_file,
            query_plan=self.plan_query(lookup=lookup, policy=policy),
        )

    def build_filter_plan(
        self,
        *,
        source_locale: str,
        min_score: int,
        origin_project: bool,
        origin_import: bool,
    ) -> TMFilterPlan:
        normalized = normalize_min_score(min_score)
        policy = TMQueryPolicy(
            source_locale=source_locale,
            min_score=normalized,
            origin_project=origin_project,
            origin_import=origin_import,
            limit=suggestion_limit_for(normalized),
        )
        return TMFilterPlan(
            policy=policy,
            prefs_extras={
                "TM_MIN_SCORE": str(normalized),
                "TM_ORIGIN_PROJECT": "true" if origin_project else "false",
                "TM_ORIGIN_IMPORT": "true" if origin_import else "false",
            },
        )

    def build_query_request(self, cache_key: TMQueryKey) -> TMQueryRequest:
        (
            source_text,
            source_locale,
            target_locale,
            min_score,
            origin_project,
            origin_import,
        ) = cache_key
        policy = TMQueryPolicy(
            source_locale=source_locale,
            min_score=min_score,
            origin_project=origin_project,
            origin_import=origin_import,
        )
        return TMQueryRequest(
            source_text=source_text,
            source_locale=source_locale,
            target_locale=target_locale,
            min_score=min_score,
            origins=origins_for(policy),
            limit=suggestion_limit_for(min_score),
        )

    def build_query_request_for_lookup(
        self,
        *,
        lookup: tuple[str, str] | None,
        policy: TMQueryPolicy,
    ) -> TMQueryRequest | None:
        if lookup is None or not has_enabled_origins(policy):
            return None
        source_text, target_locale = lookup
        if not source_text.strip() or not target_locale:
            return None
        min_score = normalize_min_score(policy.min_score)
        return TMQueryRequest(
            source_text=source_text,
            source_locale=policy.source_locale,
            target_locale=target_locale,
            min_score=min_score,
            origins=origins_for(policy),
            limit=max(1, int(policy.limit)),
        )

    def build_apply_plan(self, match: TMMatch | None) -> TMApplyPlan | None:
        if match is None:
            return None
        return TMApplyPlan(
            target_text=match.target_text,
            mark_for_review=True,
        )

    def build_selection_plan(
        self,
        *,
        match: TMMatch | None,
        lookup: tuple[str, str] | None,
    ) -> TMSelectionPlan:
        terms: tuple[str, ...] = ()
        if lookup is not None:
            terms = tuple(self.query_terms(lookup[0]))
        if match is None:
            return TMSelectionPlan(
                apply_enabled=False,
                source_preview="",
                target_preview="",
                query_terms=terms,
            )
        return TMSelectionPlan(
            apply_enabled=True,
            source_preview=match.source_text,
            target_preview=match.target_text,
            query_terms=terms,
        )

    def build_diagnostics_report(
        self,
        *,
        db_path: Path | str,
        policy: TMQueryPolicy,
        import_files: Iterable[TMImportFile],
        lookup: tuple[str, str] | None,
        matches: Iterable[TMMatch] | None = None,
    ) -> str:
        return build_diagnostics_report(
            db_path=db_path,
            policy=policy,
            import_files=import_files,
            lookup=lookup,
            matches=matches,
        )

    def build_diagnostics_report_with_query(
        self,
        *,
        db_path: Path | str,
        policy: TMQueryPolicy,
        import_files: Iterable[TMImportFile],
        lookup: tuple[str, str] | None,
        query_matches: Callable[..., Iterable[TMMatch]],
    ) -> str:
        req = self.build_query_request_for_lookup(lookup=lookup, policy=policy)
        matches: list[TMMatch] = []
        if req is not None:
            matches = list(
                query_matches(
                    req.source_text,
                    source_locale=req.source_locale,
                    target_locale=req.target_locale,
                    limit=req.limit,
                    min_score=req.min_score,
                    origins=req.origins,
                )
            )
        return self.build_diagnostics_report(
            db_path=db_path,
            policy=policy,
            import_files=import_files,
            lookup=lookup,
            matches=matches,
        )

    def diagnostics_report_for_store(
        self,
        *,
        store: TMDiagnosticsStore,
        policy: TMQueryPolicy,
        lookup: tuple[str, str] | None,
    ) -> str:
        return self.build_diagnostics_report_with_query(
            db_path=store.db_path,
            policy=policy,
            import_files=store.list_import_files(),
            lookup=lookup,
            query_matches=store.query,
        )

    def build_suggestions_view(
        self,
        *,
        matches: list[TMMatch],
        policy: TMQueryPolicy,
        source_preview_limit: int = 60,
        target_preview_limit: int = 80,
    ) -> TMSuggestionsView:
        if not matches:
            return TMSuggestionsView(
                message="No TM matches found.",
                items=(),
            )
        filtered = self.filter_matches(matches, policy=policy)
        if not filtered:
            return TMSuggestionsView(
                message="No TM matches (filtered).",
                items=(),
            )
        items = tuple(
            TMSuggestionItem(
                match=match,
                label=format_match_label(
                    match,
                    source_preview_limit=source_preview_limit,
                    target_preview_limit=target_preview_limit,
                ),
                tooltip_html=match_tooltip_html(match),
            )
            for match in filtered
        )
        return TMSuggestionsView(message="TM suggestions", items=items)

    def build_locale_variants_view(
        self,
        *,
        variants: list[tuple[str, str, str, int | None]],
        preview_limit: int = 80,
    ) -> TMLocaleVariantsView:
        if not variants:
            return TMLocaleVariantsView(
                message="No locale variants available.",
                items=(),
            )
        items = tuple(
            TMLocaleVariantItem(
                locale_code=locale_code,
                locale_name=locale_name,
                status_tag=_status_tag(status),
                value=value,
                label=(
                    f"{locale_code} · {locale_name} [{_status_tag(status)}] · "
                    f"{_truncate_text(value, preview_limit)}"
                ),
                tooltip_html=html.escape(value),
            )
            for locale_code, locale_name, value, status in variants
        )
        return TMLocaleVariantsView(message="Locale variants", items=items)


def query_terms(source_text: str) -> list[str]:
    out: list[str] = []
    for raw in re.split(r"\s+", source_text.lower()):
        token = raw.strip(".,;:!?\"'()[]{}<>")
        if len(token) < 2 or token in out:
            continue
        out.append(token)
    return out


def build_lookup(
    *,
    source_text: str,
    target_locale: str | None,
) -> tuple[str, str] | None:
    if not target_locale:
        return None
    if not source_text.strip():
        return None
    return source_text, target_locale


def _truncate_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)] + "..."


def _source_name_for_match(match: TMMatch) -> str:
    if match.tm_name:
        return match.tm_name
    if match.tm_path:
        return match.tm_path
    if match.file_path:
        return Path(match.file_path).name
    return "Project TM"


def format_match_label(
    match: TMMatch,
    *,
    source_preview_limit: int,
    target_preview_limit: int,
) -> str:
    origin = "project" if match.origin == "project" else "import"
    if origin == "project":
        tag = _status_tag(match.row_status)
        origin = f"{origin} [{tag}]"
    source_name = _source_name_for_match(match)
    source_preview = _truncate_text(match.source_text, source_preview_limit)
    target_preview = _truncate_text(match.target_text, target_preview_limit)
    score_label = f"{match.score:>3}%"
    if match.raw_score is not None and match.raw_score != match.score:
        score_label = f"{score_label} (raw {match.raw_score}%)"
    return (
        f"{score_label} · {origin} · {source_name}\n"
        f"S: {source_preview}\n"
        f"T: {target_preview}"
    )


def _status_tag(status: int | None) -> str:
    if status == 0:
        return "U"
    if status == 1:
        return "FR"
    if status == 2:
        return "T"
    if status == 3:
        return "P"
    return "U"


def match_tooltip_html(match: TMMatch) -> str:
    source = html.escape(match.source_text)
    target = html.escape(match.target_text)
    raw = match.raw_score if match.raw_score is not None else match.score
    return (
        '<span style="white-space: pre-wrap;">'
        f"<b>Score</b> {match.score}% (raw {raw}%)"
        f"<br><b>Source</b><br>{source}<br><br><b>Translation</b><br>{target}"
        "</span>"
    )


def build_diagnostics_report(
    *,
    db_path: Path | str,
    policy: TMQueryPolicy,
    import_files: Iterable[TMImportFile],
    lookup: tuple[str, str] | None,
    matches: Iterable[TMMatch] | None = None,
) -> str:
    db_display = Path(str(db_path)).as_posix()
    import_list = list(import_files)
    ready_imports = sum(1 for rec in import_list if rec.status == "ready")
    enabled_imports = sum(
        1 for rec in import_list if rec.status == "ready" and rec.enabled
    )
    pending_imports = len(import_list) - ready_imports
    lines = [
        f"TM DB: {db_display}",
        (
            "Policy: "
            f"min={policy.min_score}% limit={policy.limit} "
            f"origins(project={policy.origin_project}, import={policy.origin_import})"
        ),
        (
            "Imported files: "
            f"total={len(import_list)} ready={ready_imports} "
            f"enabled={enabled_imports} pending_or_error={pending_imports}"
        ),
    ]
    if lookup is None:
        lines.append("Current row: no source text selected.")
        return "\n".join(lines)
    source_text, target_locale = lookup
    match_list = list(matches or [])
    project_count = sum(1 for match in match_list if match.origin == "project")
    import_count = len(match_list) - project_count
    top_score = match_list[0].score if match_list else 0
    unique_sources = len({match.source_text for match in match_list})
    fuzzy_count = sum(1 for match in match_list if match.score < 100)
    recall_density = float(unique_sources) / float(len(match_list)) if match_list else 0
    lines.append(f"Current row: locale={target_locale} query_len={len(source_text)}")
    lines.append(
        "Matches: "
        f"visible={len(match_list)} top_score={top_score}% "
        f"project={project_count} import={import_count} "
        f"fuzzy={fuzzy_count} unique_sources={unique_sources} "
        f"recall_density={recall_density:.2f}"
    )
    return "\n".join(lines)
