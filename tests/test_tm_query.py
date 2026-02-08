from translationzed_py.core.tm_query import (
    TMQueryPolicy,
    current_key_from_lookup,
    filter_matches,
    has_enabled_origins,
    make_cache_key,
    normalize_min_score,
    origins_for,
)
from translationzed_py.core.tm_store import TMMatch


def _match(score: int, origin: str) -> TMMatch:
    return TMMatch(
        source_text="s",
        target_text="t",
        score=score,
        origin=origin,
        tm_name=None,
        tm_path=None,
        file_path=None,
        key=None,
        updated_at=1,
    )


def test_tm_query_key_helpers() -> None:
    policy = TMQueryPolicy(
        source_locale="EN",
        min_score=70,
        origin_project=True,
        origin_import=False,
    )
    key = make_cache_key("hello", target_locale="BE", policy=policy)
    assert key == ("hello", "EN", "BE", 70, True, False)
    assert current_key_from_lookup(("hello", "BE"), policy=policy) == key
    assert current_key_from_lookup(None, policy=policy) is None


def test_tm_query_origin_controls_and_filtering() -> None:
    disabled = TMQueryPolicy(origin_project=False, origin_import=False)
    assert has_enabled_origins(disabled) is False
    assert origins_for(disabled) == ()

    project_only = TMQueryPolicy(min_score=60, origin_project=True, origin_import=False)
    matches = [_match(100, "project"), _match(99, "import"), _match(50, "project")]
    filtered = filter_matches(matches, policy=project_only)
    assert len(filtered) == 1
    assert filtered[0].origin == "project"
    assert filtered[0].score == 100


def test_tm_query_min_score_normalization_range() -> None:
    assert normalize_min_score(1) == 5
    assert normalize_min_score(10) == 10
    assert normalize_min_score(50) == 50
    assert normalize_min_score(200) == 100


def test_tm_query_default_min_score_is_precision_first() -> None:
    assert TMQueryPolicy().min_score == 50
