from __future__ import annotations

from dataclasses import dataclass

from .tm_store import TMMatch

# UI/filters allow 30..100; app default is set at the GUI layer.
_MIN_SCORE = 30
_MAX_SCORE = 100

TMQueryKey = tuple[str, str, str, int, bool, bool]


@dataclass(frozen=True, slots=True)
class TMQueryPolicy:
    source_locale: str = "EN"
    min_score: int = _MIN_SCORE
    origin_project: bool = True
    origin_import: bool = True
    limit: int = 12


def normalize_min_score(value: int) -> int:
    return max(_MIN_SCORE, min(_MAX_SCORE, int(value)))


def has_enabled_origins(policy: TMQueryPolicy) -> bool:
    return policy.origin_project or policy.origin_import


def origins_for(policy: TMQueryPolicy) -> tuple[str, ...]:
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
    if lookup is None:
        return None
    source_text, target_locale = lookup
    return make_cache_key(source_text, target_locale=target_locale, policy=policy)


def filter_matches(matches: list[TMMatch], *, policy: TMQueryPolicy) -> list[TMMatch]:
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
