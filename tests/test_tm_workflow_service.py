from __future__ import annotations

from pathlib import Path

from translationzed_py.core.tm_query import TMQueryPolicy
from translationzed_py.core.tm_store import TMImportFile, TMMatch
from translationzed_py.core.tm_workflow_service import TMWorkflowService


def _match(
    *,
    source: str,
    target: str,
    score: int,
    origin: str = "project",
    row_status: int | None = None,
) -> TMMatch:
    return TMMatch(
        source_text=source,
        target_text=target,
        score=score,
        origin=origin,
        tm_name=None,
        tm_path=None,
        file_path=None,
        key=None,
        updated_at=0,
        row_status=row_status,
    )


def _import_file(
    *,
    status: str,
    enabled: bool,
    tm_name: str = "imported",
) -> TMImportFile:
    return TMImportFile(
        tm_path="/tmp/sample.tmx",
        tm_name=tm_name,
        source_locale="EN",
        target_locale="BE",
        source_locale_raw="",
        target_locale_raw="",
        segment_count=10,
        mtime_ns=1,
        file_size=1,
        enabled=enabled,
        status=status,
        note="",
        updated_at=1,
    )


def test_tm_workflow_queue_and_flush_batches() -> None:
    service = TMWorkflowService()
    service.queue_updates(
        "root/BE/a.txt",
        [("k1", "src1", "tr1", 2), ("k2", "src2", "tr2")],
    )
    service.queue_updates("root/RU/a.txt", [("k1", "src1", "ru1")])

    batches = service.pending_batches(
        locale_for_path=lambda path: path.split("/")[1], paths=["root/BE/a.txt"]
    )

    assert len(batches) == 1
    assert batches[0].file_key == "root/BE/a.txt"
    assert batches[0].target_locale == "BE"
    assert len(batches[0].rows) == 2
    assert batches[0].rows[0][3] == 2
    assert batches[0].rows[1][3] is None

    service.mark_batch_flushed("root/BE/a.txt")
    remaining = service.pending_batches(locale_for_path=lambda path: path.split("/")[1])
    assert len(remaining) == 1
    assert remaining[0].target_locale == "RU"


def test_tm_workflow_query_plan_modes() -> None:
    service = TMWorkflowService()
    disabled = service.plan_query(
        lookup=("abc", "BE"),
        policy=TMQueryPolicy(origin_project=False, origin_import=False),
    )
    assert disabled.mode == "disabled"

    no_lookup = service.plan_query(lookup=None, policy=TMQueryPolicy())
    assert no_lookup.mode == "no_lookup"

    query = service.plan_query(lookup=("abc", "BE"), policy=TMQueryPolicy())
    assert query.mode == "query"
    assert query.cache_key is not None

    matches = [_match(source="abc", target="def", score=100)]
    assert service.accept_query_result(
        cache_key=query.cache_key,
        matches=matches,
        lookup=("abc", "BE"),
        policy=TMQueryPolicy(),
    )
    cached = service.plan_query(lookup=("abc", "BE"), policy=TMQueryPolicy())
    assert cached.mode == "cached"
    assert cached.matches == matches


def test_tm_workflow_query_cache_limit_and_filtering() -> None:
    service = TMWorkflowService(cache_limit=1)
    first = service.plan_query(lookup=("one", "BE"), policy=TMQueryPolicy())
    second = service.plan_query(lookup=("two", "BE"), policy=TMQueryPolicy())
    service.accept_query_result(
        cache_key=first.cache_key,
        matches=[_match(source="one", target="1", score=80)],
        lookup=("one", "BE"),
        policy=TMQueryPolicy(),
    )
    service.accept_query_result(
        cache_key=second.cache_key,
        matches=[_match(source="two", target="2", score=90)],
        lookup=("two", "BE"),
        policy=TMQueryPolicy(),
    )

    first_again = service.plan_query(lookup=("one", "BE"), policy=TMQueryPolicy())
    assert first_again.mode == "query"

    filtered = service.filter_matches(
        [
            _match(source="s", target="a", score=100, origin="project"),
            _match(source="s", target="b", score=55, origin="import"),
            _match(source="s", target="c", score=25, origin="import"),
        ],
        policy=TMQueryPolicy(min_score=30, origin_project=False, origin_import=True),
    )
    assert len(filtered) == 1
    assert filtered[0].target_text == "b"


def test_tm_workflow_query_terms_tokenize_and_deduplicate() -> None:
    service = TMWorkflowService()
    terms = service.query_terms("Drop one, drop <LINE> one!")
    assert terms == ["drop", "one", "line"]


def test_tm_workflow_preference_actions_wrappers(tmp_path: Path) -> None:
    service = TMWorkflowService()
    remove_path = tmp_path / "old.tmx"
    import_path = tmp_path / "new.tmx"
    values = {
        "tm_remove_paths": [str(remove_path)],
        "tm_enabled": {str(remove_path): False},
        "tm_import_paths": [str(import_path)],
    }
    actions = service.build_preferences_actions(values)
    assert str(remove_path) in actions.remove_paths
    assert actions.enabled_map[str(remove_path)] is False
    assert actions.import_paths == [str(import_path)]

    class _Store:
        def __init__(self) -> None:
            self.deleted: list[str] = []
            self.enabled: list[tuple[str, bool]] = []

        def delete_import_file(self, tm_path: str) -> None:
            self.deleted.append(tm_path)

        def set_import_enabled(self, tm_path: str, enabled: bool) -> None:
            self.enabled.append((tm_path, enabled))

    store = _Store()
    report = service.apply_preferences_actions(
        store=store,  # type: ignore[arg-type]
        actions=actions,
        copy_to_import_dir=lambda path: path,
    )
    assert report.failures == ()
    assert report.sync_paths == (import_path,)
    assert store.deleted == [str(remove_path)]
    assert store.enabled == []


def test_tm_workflow_sync_import_folder_wrapper_delegates(monkeypatch) -> None:
    service = TMWorkflowService()
    calls: dict[str, object] = {}

    def _fake_sync_import_folder(  # type: ignore[no-untyped-def]
        store,
        tm_dir,
        *,
        resolve_locales,
        only_paths=None,
        pending_only=False,
    ):
        calls["store"] = store
        calls["tm_dir"] = tm_dir
        calls["resolve_locales"] = resolve_locales
        calls["only_paths"] = only_paths
        calls["pending_only"] = pending_only
        return "ok"

    monkeypatch.setattr(
        "translationzed_py.core.tm_workflow_service.sync_import_folder",
        _fake_sync_import_folder,
    )

    report = service.sync_import_folder(
        store=object(),  # type: ignore[arg-type]
        tm_dir=Path("/tmp/tm"),
        resolve_locales=lambda _path, _langs: (("EN", "BE"), False),
        only_paths={Path("/tmp/tm/a.tmx")},
        pending_only=True,
    )

    assert report == "ok"
    assert str(calls["tm_dir"]) == "/tmp/tm"
    assert calls["pending_only"] is True
    assert {str(p) for p in calls["only_paths"]} == {"/tmp/tm/a.tmx"}
    assert callable(calls["resolve_locales"])


def test_tm_workflow_collect_rebuild_locales_wrapper_delegates(monkeypatch) -> None:
    service = TMWorkflowService()
    calls: dict[str, object] = {}

    def _fake_collect(locale_map, selected_locales):  # type: ignore[no-untyped-def]
        calls["locale_map"] = locale_map
        calls["selected_locales"] = selected_locales
        return (["spec"], "utf-16")

    monkeypatch.setattr(
        "translationzed_py.core.tm_workflow_service.collect_rebuild_locales",
        _fake_collect,
    )
    locale_map = {"EN": object()}
    specs, en_encoding = service.collect_rebuild_locales(
        locale_map=locale_map,  # type: ignore[arg-type]
        selected_locales=["BE"],
    )
    assert specs == ["spec"]
    assert en_encoding == "utf-16"
    assert calls["locale_map"] is locale_map
    assert calls["selected_locales"] == ["BE"]


def test_tm_workflow_rebuild_project_tm_wrapper_delegates(monkeypatch) -> None:
    service = TMWorkflowService()
    calls: dict[str, object] = {}

    def _fake_rebuild(root, locales, **kwargs):  # type: ignore[no-untyped-def]
        calls["root"] = root
        calls["locales"] = locales
        calls.update(kwargs)
        return "ok"

    monkeypatch.setattr(
        "translationzed_py.core.tm_workflow_service.rebuild_project_tm",
        _fake_rebuild,
    )
    result = service.rebuild_project_tm(
        Path("/tmp/proj"),
        locales=[],
        source_locale="EN",
        en_encoding="utf-8",
        batch_size=123,
    )
    assert result == "ok"
    assert str(calls["root"]) == "/tmp/proj"
    assert calls["locales"] == []
    assert calls["source_locale"] == "EN"
    assert calls["en_encoding"] == "utf-8"
    assert calls["batch_size"] == 123


def test_tm_workflow_format_rebuild_status_wrapper_delegates(monkeypatch) -> None:
    service = TMWorkflowService()
    calls: dict[str, object] = {}

    def _fake_format(result):  # type: ignore[no-untyped-def]
        calls["result"] = result
        return "formatted"

    monkeypatch.setattr(
        "translationzed_py.core.tm_workflow_service.format_rebuild_status",
        _fake_format,
    )
    token = object()
    assert service.format_rebuild_status(token) == "formatted"  # type: ignore[arg-type]
    assert calls["result"] is token


def test_tm_workflow_build_suggestions_view_formats_items() -> None:
    service = TMWorkflowService()
    matches = [
        _match(
            source="Drop all",
            target="Скінуць усё",
            score=85,
            origin="project",
            row_status=1,
        ),
        _match(source="Drop one", target="Скінуць шт.", score=20, origin="import"),
    ]
    view = service.build_suggestions_view(
        matches=matches,
        policy=TMQueryPolicy(min_score=30, origin_project=True, origin_import=True),
    )
    assert view.message == "TM suggestions"
    assert len(view.items) == 1
    item = view.items[0]
    assert item.match.source_text == "Drop all"
    assert "project" in item.label
    assert "[FR]" in item.label
    assert "S: Drop all" in item.label
    assert "Translation" in item.tooltip_html


def test_tm_workflow_build_suggestions_view_imported_label_has_no_status_tag() -> None:
    service = TMWorkflowService()
    view = service.build_suggestions_view(
        matches=[
            _match(source="Drop one", target="Скінуць шт.", score=70, origin="import")
        ],
        policy=TMQueryPolicy(min_score=5, origin_project=False, origin_import=True),
    )
    assert len(view.items) == 1
    assert "import" in view.items[0].label
    assert "import [" not in view.items[0].label


def test_tm_workflow_build_locale_variants_view_formats_compact_items() -> None:
    service = TMWorkflowService()
    view = service.build_locale_variants_view(
        variants=[
            ("RU", "Russian", "Скінуць усё", 2),
            ("KO", "Korean", "모두 버리기", 1),
        ],
        preview_limit=10,
    )
    assert view.message == "Locale variants"
    assert len(view.items) == 2
    assert view.items[0].label.startswith("RU · Russian [T]")
    assert view.items[1].label.startswith("KO · Korean [FR]")
    assert "모두 버리기" in view.items[1].tooltip_html


def test_tm_workflow_build_suggestions_view_empty_and_filtered_messages() -> None:
    service = TMWorkflowService()
    empty = service.build_suggestions_view(
        matches=[],
        policy=TMQueryPolicy(),
    )
    assert empty.message == "No TM matches found."
    assert empty.items == ()

    filtered = service.build_suggestions_view(
        matches=[_match(source="Drop", target="Скінуць", score=10)],
        policy=TMQueryPolicy(min_score=50),
    )
    assert filtered.message == "No TM matches (filtered)."
    assert filtered.items == ()


def test_tm_workflow_build_query_request_from_cache_key() -> None:
    service = TMWorkflowService()
    key = ("Drop one", "EN", "BE", 20, True, False)
    req = service.build_query_request(key)
    assert req.source_text == "Drop one"
    assert req.source_locale == "EN"
    assert req.target_locale == "BE"
    assert req.min_score == 20
    assert req.origins == ("project",)
    assert req.limit >= 60


def test_tm_workflow_build_apply_plan() -> None:
    service = TMWorkflowService()
    plan = service.build_apply_plan(
        _match(source="Drop one", target="Скінуць шт.", score=92)
    )
    assert plan is not None
    assert plan.target_text == "Скінуць шт."
    assert plan.mark_for_review is True
    assert service.build_apply_plan(None) is None


def test_tm_workflow_build_selection_plan() -> None:
    service = TMWorkflowService()
    no_match = service.build_selection_plan(
        match=None,
        lookup=("Drop one", "BE"),
    )
    assert no_match.apply_enabled is False
    assert no_match.source_preview == ""
    assert no_match.target_preview == ""
    assert "drop" in no_match.query_terms

    with_match = service.build_selection_plan(
        match=_match(source="Drop one", target="Скінуць шт.", score=92),
        lookup=("Drop one", "BE"),
    )
    assert with_match.apply_enabled is True
    assert with_match.source_preview == "Drop one"
    assert with_match.target_preview == "Скінуць шт."
    assert "drop" in with_match.query_terms


def test_tm_workflow_build_lookup_validates_source_and_locale() -> None:
    service = TMWorkflowService()
    assert service.build_lookup(source_text="Drop one", target_locale="BE") == (
        "Drop one",
        "BE",
    )
    assert service.build_lookup(source_text="   ", target_locale="BE") is None
    assert service.build_lookup(source_text="Drop one", target_locale=None) is None


def test_tm_workflow_build_update_plan() -> None:
    service = TMWorkflowService()
    skip = service.build_update_plan(
        has_store=False,
        panel_index=1,
        timer_active=True,
    )
    assert skip.run_update is False
    assert skip.stop_timer is False
    assert skip.start_timer is False

    inactive_panel = service.build_update_plan(
        has_store=True,
        panel_index=0,
        timer_active=True,
    )
    assert inactive_panel.run_update is False
    assert inactive_panel.stop_timer is False
    assert inactive_panel.start_timer is False

    start = service.build_update_plan(
        has_store=True,
        panel_index=1,
        timer_active=False,
    )
    assert start.run_update is True
    assert start.stop_timer is False
    assert start.start_timer is True

    restart = service.build_update_plan(
        has_store=True,
        panel_index=1,
        timer_active=True,
    )
    assert restart.run_update is True
    assert restart.stop_timer is True
    assert restart.start_timer is True


def test_tm_workflow_build_refresh_plan() -> None:
    service = TMWorkflowService()
    disabled = service.build_refresh_plan(
        has_store=False,
        panel_index=1,
        lookup=("Drop one", "BE"),
        policy=TMQueryPolicy(),
        has_current_file=True,
    )
    assert disabled.run_update is False
    assert disabled.flush_current_file is False
    assert disabled.query_plan is None

    no_lookup = service.build_refresh_plan(
        has_store=True,
        panel_index=1,
        lookup=None,
        policy=TMQueryPolicy(),
        has_current_file=False,
    )
    assert no_lookup.run_update is True
    assert no_lookup.flush_current_file is False
    assert no_lookup.query_plan is not None
    assert no_lookup.query_plan.mode == "no_lookup"

    query = service.build_refresh_plan(
        has_store=True,
        panel_index=1,
        lookup=("Drop one", "BE"),
        policy=TMQueryPolicy(),
        has_current_file=True,
    )
    assert query.run_update is True
    assert query.flush_current_file is True
    assert query.query_plan is not None
    assert query.query_plan.mode == "query"


def test_tm_workflow_build_filter_plan_normalizes_min_score_and_extras() -> None:
    service = TMWorkflowService()
    plan = service.build_filter_plan(
        source_locale="EN",
        min_score=3,
        origin_project=False,
        origin_import=True,
    )
    assert plan.policy.source_locale == "EN"
    assert plan.policy.min_score == 5
    assert plan.policy.limit >= 120
    assert plan.policy.origin_project is False
    assert plan.policy.origin_import is True
    assert plan.prefs_extras == {
        "TM_MIN_SCORE": "5",
        "TM_ORIGIN_PROJECT": "false",
        "TM_ORIGIN_IMPORT": "true",
    }


def test_tm_workflow_build_query_request_for_lookup() -> None:
    service = TMWorkflowService()
    req = service.build_query_request_for_lookup(
        lookup=("Drop one", "BE"),
        policy=TMQueryPolicy(min_score=3, origin_project=False, origin_import=True),
    )
    assert req is not None
    assert req.source_text == "Drop one"
    assert req.target_locale == "BE"
    assert req.min_score == 5
    assert req.origins == ("import",)

    none_req = service.build_query_request_for_lookup(
        lookup=None,
        policy=TMQueryPolicy(),
    )
    assert none_req is None


def test_tm_workflow_build_diagnostics_report() -> None:
    service = TMWorkflowService()
    policy = TMQueryPolicy(
        min_score=25, limit=60, origin_project=True, origin_import=True
    )
    report_no_lookup = service.build_diagnostics_report(
        db_path="/tmp/tm.sqlite",
        policy=policy,
        import_files=[
            _import_file(status="ready", enabled=True),
            _import_file(status="error", enabled=True, tm_name="bad"),
        ],
        lookup=None,
        matches=None,
    )
    assert "TM DB: /tmp/tm.sqlite" in report_no_lookup
    assert "Policy: min=25% limit=60" in report_no_lookup
    assert (
        "Imported files: total=2 ready=1 enabled=1 pending_or_error=1"
        in report_no_lookup
    )
    assert "Current row: no source text selected." in report_no_lookup

    report_lookup = service.build_diagnostics_report(
        db_path="/tmp/tm.sqlite",
        policy=policy,
        import_files=[],
        lookup=("Drop one", "BE"),
        matches=[
            _match(source="Drop one", target="x", score=100, origin="project"),
            _match(source="Drop all", target="y", score=72, origin="import"),
        ],
    )
    assert "Current row: locale=BE query_len=8" in report_lookup
    assert "Matches: visible=2 top_score=100% project=1 import=1" in report_lookup
    assert "fuzzy=1 unique_sources=2 recall_density=1.00" in report_lookup


def test_tm_workflow_build_diagnostics_report_with_query() -> None:
    service = TMWorkflowService()
    policy = TMQueryPolicy(
        min_score=3, limit=12, origin_project=False, origin_import=True
    )

    captured: dict[str, object] = {}

    def _query(source_text, **kwargs):  # noqa: ANN001
        captured["source_text"] = source_text
        captured.update(kwargs)
        return [_match(source="Drop one", target="x", score=77, origin="import")]

    report = service.build_diagnostics_report_with_query(
        db_path="/tmp/tm.sqlite",
        policy=policy,
        import_files=[],
        lookup=("Drop one", "BE"),
        query_matches=_query,
    )
    assert captured["source_text"] == "Drop one"
    assert captured["source_locale"] == "EN"
    assert captured["target_locale"] == "BE"
    assert captured["min_score"] == 5
    assert captured["origins"] == ("import",)
    assert "Matches: visible=1 top_score=77% project=0 import=1" in report

    captured.clear()
    report_no_lookup = service.build_diagnostics_report_with_query(
        db_path="/tmp/tm.sqlite",
        policy=policy,
        import_files=[],
        lookup=None,
        query_matches=_query,
    )
    assert captured == {}
    assert "Current row: no source text selected." in report_no_lookup


def test_tm_workflow_diagnostics_report_for_store_adapter() -> None:
    service = TMWorkflowService()

    class _Store:
        db_path = Path("/tmp/store.sqlite")

        def list_import_files(self) -> list[TMImportFile]:
            return [_import_file(status="ready", enabled=True)]

        def query(self, source_text, **kwargs):  # noqa: ANN001
            assert source_text == "Drop all"
            assert kwargs["target_locale"] == "BE"
            return [_match(source="Drop all", target="Пакід. усё", score=88)]

    report = service.diagnostics_report_for_store(
        store=_Store(),
        policy=TMQueryPolicy(min_score=20),
        lookup=("Drop all", "BE"),
    )
    assert "TM DB: /tmp/store.sqlite" in report
    assert "Imported files: total=1 ready=1 enabled=1 pending_or_error=0" in report
    assert "Matches: visible=1 top_score=88% project=1 import=0" in report
