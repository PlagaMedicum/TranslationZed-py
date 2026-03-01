"""Text matching primitives used by TM fuzzy-query heuristics."""

from __future__ import annotations

from collections.abc import Callable


def token_matches_uncached(
    query_token: str,
    candidate_token: str,
    *,
    use_en_stemming: bool,
    stem_token_cached: Callable[[str], str],
) -> bool:
    """Return whether tokens should be treated as fuzzy-equivalent."""
    if query_token == candidate_token:
        return True
    if use_en_stemming:
        query_stem = stem_token_cached(query_token)
        candidate_stem = stem_token_cached(candidate_token)
        if len(query_stem) >= 3 and query_stem == candidate_stem:
            return True
    if len(query_token) == len(candidate_token) and len(query_token) >= 4:
        if query_token[:2] != candidate_token[:2]:
            return False
        if query_token[-1] != candidate_token[-1]:
            return False
        mismatches = 0
        for q_char, c_char in zip(query_token, candidate_token, strict=False):
            if q_char != c_char:
                mismatches += 1
                if mismatches > 1:
                    break
        if mismatches == 1:
            return True
    shorter, longer = (
        (query_token, candidate_token)
        if len(query_token) <= len(candidate_token)
        else (candidate_token, query_token)
    )
    if len(shorter) < 4:
        return False
    ratio = len(shorter) / len(longer)
    if (longer.startswith(shorter) or longer.endswith(shorter)) and ratio >= 0.50:
        return True
    if shorter in longer:
        return ratio >= 0.67
    return False


def contains_composed_phrase_uncached(
    text: str,
    query: str,
    *,
    use_en_stemming: bool,
    query_tokens_cached: Callable[[str], tuple[str, ...]],
    token_matches: Callable[[str, str], bool],
) -> bool:
    """Return whether query-token sequence appears in-order in candidate text."""
    parts = query_tokens_cached(query)
    if not parts:
        return False
    text_tokens = query_tokens_cached(text)
    if not text_tokens:
        return False
    if len(parts) == 1:
        token = parts[0]
        return any(token_matches(token, cand) for cand in text_tokens)
    pos = 0
    for part in parts:
        found = False
        while pos < len(text_tokens):
            if token_matches(part, text_tokens[pos]):
                found = True
                pos += 1
                break
            pos += 1
        if not found:
            return False
    return True
