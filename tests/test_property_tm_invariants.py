"""Randomized TM metamorphic invariants for filtering and suggestions ordering."""

from __future__ import annotations

from collections import Counter

from hypothesis import given
from hypothesis import strategies as st

from tests.hypothesis_profile import prop_settings
from translationzed_py.core.tm_query import TMQueryPolicy, filter_matches
from translationzed_py.core.tm_store import TMMatch
from translationzed_py.core.tm_workflow_service import TMWorkflowService

_TEXT = st.text(
    alphabet=st.characters(min_codepoint=32, max_codepoint=126),
    min_size=0,
    max_size=32,
)
_GROUPING = st.sampled_from(("none", "origin", "score_band"))
_MATCHES = st.lists(
    st.builds(
        TMMatch,
        source_text=_TEXT,
        target_text=_TEXT,
        score=st.integers(min_value=0, max_value=100),
        origin=st.sampled_from(("project", "import")),
        tm_name=st.none(),
        tm_path=st.none(),
        file_path=st.none(),
        key=st.none(),
        updated_at=st.integers(min_value=0, max_value=10_000),
    ),
    min_size=0,
    max_size=60,
)


def _match_key(match: TMMatch) -> tuple[object, ...]:
    return (
        match.source_text,
        match.target_text,
        int(match.score),
        match.origin,
        match.tm_name,
        match.tm_path,
        match.file_path,
        match.key,
        int(match.updated_at),
    )


@given(
    matches=_MATCHES,
    min_score=st.integers(min_value=5, max_value=100),
    origin_project=st.booleans(),
    origin_import=st.booleans(),
    grouping=_GROUPING,
)
@prop_settings(fast_examples=70, slow_examples=320)
def test_tm_suggestions_view_is_deterministic_for_identical_inputs(
    matches: list[TMMatch],
    min_score: int,
    origin_project: bool,
    origin_import: bool,
    grouping: str,
) -> None:
    """Suggestions rendering order/group headers must be stable for same inputs."""
    service = TMWorkflowService()
    policy = TMQueryPolicy(
        source_locale="EN",
        min_score=min_score,
        origin_project=origin_project,
        origin_import=origin_import,
        limit=200,
    )
    left = service.build_suggestions_view(
        matches=matches,
        policy=policy,
        grouping=grouping,
    )
    right = service.build_suggestions_view(
        matches=matches,
        policy=policy,
        grouping=grouping,
    )
    assert [(_match_key(item.match), item.group_label) for item in left.items] == [
        (_match_key(item.match), item.group_label) for item in right.items
    ]


@given(matches=_MATCHES, min_score=st.integers(min_value=5, max_value=100))
@prop_settings(fast_examples=70, slow_examples=320)
def test_tm_origin_filter_results_are_subsets_of_both_origins(
    matches: list[TMMatch],
    min_score: int,
) -> None:
    """Project-only/import-only filters cannot introduce results absent in both-origins."""
    policy_both = TMQueryPolicy(
        source_locale="EN",
        min_score=min_score,
        origin_project=True,
        origin_import=True,
        limit=200,
    )
    policy_project = TMQueryPolicy(
        source_locale="EN",
        min_score=min_score,
        origin_project=True,
        origin_import=False,
        limit=200,
    )
    policy_import = TMQueryPolicy(
        source_locale="EN",
        min_score=min_score,
        origin_project=False,
        origin_import=True,
        limit=200,
    )
    both_counts = Counter(
        _match_key(match) for match in filter_matches(matches, policy=policy_both)
    )
    project_counts = Counter(
        _match_key(match) for match in filter_matches(matches, policy=policy_project)
    )
    import_counts = Counter(
        _match_key(match) for match in filter_matches(matches, policy=policy_import)
    )
    for key, count in project_counts.items():
        assert count <= both_counts[key]
    for key, count in import_counts.items():
        assert count <= both_counts[key]

    disabled = TMQueryPolicy(
        source_locale="EN",
        min_score=min_score,
        origin_project=False,
        origin_import=False,
        limit=200,
    )
    assert filter_matches(matches, policy=disabled) == []


@given(
    matches=_MATCHES,
    scores=st.tuples(
        st.integers(min_value=5, max_value=100),
        st.integers(min_value=5, max_value=100),
    ),
)
@prop_settings(fast_examples=70, slow_examples=320)
def test_tm_min_score_is_monotonic(
    matches: list[TMMatch],
    scores: tuple[int, int],
) -> None:
    """Raising min-score threshold cannot increase filtered result multiset."""
    low, high = sorted(scores)
    low_policy = TMQueryPolicy(
        source_locale="EN",
        min_score=low,
        origin_project=True,
        origin_import=True,
        limit=200,
    )
    high_policy = TMQueryPolicy(
        source_locale="EN",
        min_score=high,
        origin_project=True,
        origin_import=True,
        limit=200,
    )
    low_counts = Counter(
        _match_key(match) for match in filter_matches(matches, policy=low_policy)
    )
    high_counts = Counter(
        _match_key(match) for match in filter_matches(matches, policy=high_policy)
    )
    for key, count in high_counts.items():
        assert count <= low_counts[key]
