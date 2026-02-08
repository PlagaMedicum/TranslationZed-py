from __future__ import annotations

from translationzed_py.core.tm_query import TMQueryPolicy
from translationzed_py.core.tm_store import TMMatch
from translationzed_py.core.tm_workflow_service import TMWorkflowService


def _match(*, source: str, target: str, score: int, origin: str = "project") -> TMMatch:
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
    )


def test_tm_workflow_queue_and_flush_batches() -> None:
    service = TMWorkflowService()
    service.queue_updates(
        "root/BE/a.txt",
        [("k1", "src1", "tr1"), ("k2", "src2", "tr2")],
    )
    service.queue_updates("root/RU/a.txt", [("k1", "src1", "ru1")])

    batches = service.pending_batches(
        locale_for_path=lambda path: path.split("/")[1], paths=["root/BE/a.txt"]
    )

    assert len(batches) == 1
    assert batches[0].file_key == "root/BE/a.txt"
    assert batches[0].target_locale == "BE"
    assert len(batches[0].rows) == 2

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
            _match(source="s", target="b", score=40, origin="import"),
            _match(source="s", target="c", score=25, origin="import"),
        ],
        policy=TMQueryPolicy(min_score=30, origin_project=False, origin_import=True),
    )
    assert len(filtered) == 1
    assert filtered[0].target_text == "b"
