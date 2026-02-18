"""TM query policy helpers for score normalization and match filtering."""

from __future__ import annotations

from dataclasses import dataclass

from .tm_store import TMMatch

# TM filters allow broad recall (5..100) while keeping default precision at 50%.
_MIN_SCORE = 5
_DEFAULT_SCORE = 50
_MAX_SCORE = 100
_HIGH_RECALL_SCORE = 10
_MEDIUM_RECALL_SCORE = 20
_LOW_RECALL_SCORE = 40

TMQueryKey = tuple[str, str, str, int, bool, bool]


@dataclass(frozen=True, slots=True)
class TMQueryPolicy:
    """Capture query-time filtering and scoring preferences for TM lookups."""

    source_locale: str = "EN"
    min_score: int = _DEFAULT_SCORE
    origin_project: bool = True
    origin_import: bool = True
    limit: int = 12


def normalize_min_score(value: int) -> int:
    """Clamp requested minimum score to the supported score range."""
    return max(_MIN_SCORE, min(_MAX_SCORE, int(value)))


def suggestion_limit_for(min_score: int) -> int:
    """Scale result-list depth by requested recall."""
    score = normalize_min_score(min_score)
    if score <= _HIGH_RECALL_SCORE:
        return 200
    if score <= _MEDIUM_RECALL_SCORE:
        return 120
    if score <= _LOW_RECALL_SCORE:
        return 60
    return 30


def has_enabled_origins(policy: TMQueryPolicy) -> bool:
    """Return whether at least one TM origin is enabled."""
    return policy.origin_project or policy.origin_import


def origins_for(policy: TMQueryPolicy) -> tuple[str, ...]:
    """Return enabled origin labels in stable query order."""
    origins: list[str] = []
    if policy.origin_project:
        origins.append("project")
    if policy.origin_import:
        origins.append("import")
    return tuple(origins)


def make_cache_key(
    source_text: str,
    *,
    target_locale: str,
    policy: TMQueryPolicy,
) -> TMQueryKey:
    """Build cache key tuple for current query text and policy inputs."""
    return (
        source_text,
        policy.source_locale,
        target_locale,
        normalize_min_score(policy.min_score),
        policy.origin_project,
        policy.origin_import,
    )


def current_key_from_lookup(
    lookup: tuple[str, str] | None,
    *,
    policy: TMQueryPolicy,
) -> TMQueryKey | None:
    """Build current query cache key from lookup tuple when present."""
    if lookup is None:
        return None
    source_text, target_locale = lookup
    return make_cache_key(source_text, target_locale=target_locale, policy=policy)


def filter_matches(matches: list[TMMatch], *, policy: TMQueryPolicy) -> list[TMMatch]:
    """Filter matches by score floor and enabled origin constraints."""
    min_score = normalize_min_score(policy.min_score)
    filtered: list[TMMatch] = []
    for match in matches:
        if match.score < min_score:
            continue
        if match.origin == "project":
            if not policy.origin_project:
                continue
        elif not policy.origin_import:
            continue
        filtered.append(match)
    return filtered
