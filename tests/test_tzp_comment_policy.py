"""Contract tests for namespaced TZP status comment policy helpers."""

from __future__ import annotations

import pytest

from translationzed_py.core.model import Status
from translationzed_py.core.tzp_comment_policy import (
    build_tzp_comment_write_plan,
    format_tzp_status_comment,
    parse_status_comment,
    parse_tzp_status_comment,
)


@pytest.mark.parametrize(
    ("comment_text", "expected"),
    [
        ("-- TZP:PROOFREAD", Status.PROOFREAD),
        ("// tzp:translated", Status.TRANSLATED),
        ("/* TZP: for_review */", Status.FOR_REVIEW),
    ],
)
def test_parse_tzp_status_comment_accepts_namespaced_styles(
    comment_text: str, expected: Status
) -> None:
    """Namespaced comments should parse consistently across comment styles."""
    assert parse_tzp_status_comment(comment_text) is expected


@pytest.mark.parametrize(
    ("comment_text", "expected"),
    [
        ("-- PROOFREAD", Status.PROOFREAD),
        ("// translated", Status.TRANSLATED),
        ("/* FOR_REVIEW */", Status.FOR_REVIEW),
        ("-- TZP:PROOFREAD", Status.PROOFREAD),
    ],
)
def test_parse_status_comment_accepts_legacy_and_namespaced(
    comment_text: str, expected: Status
) -> None:
    """Legacy status comments remain supported while TZP namespacing is accepted."""
    assert parse_status_comment(comment_text) is expected


def test_parse_tzp_status_comment_rejects_non_namespaced_text() -> None:
    """Strict TZP parser should ignore plain user comments and legacy tags."""
    assert parse_tzp_status_comment("-- translator note") is None
    assert parse_tzp_status_comment("-- PROOFREAD") is None


def test_parse_tzp_status_comment_supports_hash_prefix_and_plain_text() -> None:
    """Hash comments and plain status text should normalize through delimiters."""
    assert parse_tzp_status_comment("# TZP:TRANSLATED") is Status.TRANSLATED
    assert parse_status_comment("PROOFREAD") is Status.PROOFREAD


def test_format_tzp_status_comment_roundtrip() -> None:
    """Canonical TZP formatting should be parsed back losslessly."""
    rendered = format_tzp_status_comment(Status.PROOFREAD)
    assert rendered == "-- TZP:PROOFREAD"
    assert parse_tzp_status_comment(rendered) is Status.PROOFREAD


def test_format_tzp_status_comment_rejects_invalid_inputs() -> None:
    """Formatting should reject unsupported status/prefix combinations."""
    with pytest.raises(ValueError, match="support FOR_REVIEW/TRANSLATED/PROOFREAD"):
        format_tzp_status_comment(Status.UNTOUCHED)
    with pytest.raises(ValueError, match="comment_prefix must not be empty"):
        format_tzp_status_comment(Status.TRANSLATED, comment_prefix=" ")


def test_build_tzp_comment_write_plan_insert_for_missing_comment() -> None:
    """Missing TZP comments should produce deterministic insert action."""
    plan = build_tzp_comment_write_plan(
        existing_comment=None,
        desired_status=Status.TRANSLATED,
    )
    assert plan.action == "insert"
    assert plan.rendered_comment == "-- TZP:TRANSLATED"
    assert plan.existing_status is None


def test_build_tzp_comment_write_plan_noop_for_matching_canonical() -> None:
    """Already canonical comments should not trigger rewrites."""
    plan = build_tzp_comment_write_plan(
        existing_comment="-- TZP:PROOFREAD",
        desired_status=Status.PROOFREAD,
    )
    assert plan.action == "noop"
    assert plan.rendered_comment == "-- TZP:PROOFREAD"
    assert plan.existing_status is Status.PROOFREAD


def test_build_tzp_comment_write_plan_update_for_noncanonical_tzp_text() -> None:
    """Equivalent but non-canonical TZP comments should be rewritten canonically."""
    plan = build_tzp_comment_write_plan(
        existing_comment="// tzp: proofread",
        desired_status=Status.PROOFREAD,
    )
    assert plan.action == "update"
    assert plan.rendered_comment == "-- TZP:PROOFREAD"
    assert plan.existing_status is Status.PROOFREAD


def test_build_tzp_comment_write_plan_remove_when_status_clears() -> None:
    """Clearing status should remove existing TZP comments only."""
    tzp_plan = build_tzp_comment_write_plan(
        existing_comment="-- TZP:FOR_REVIEW",
        desired_status=None,
    )
    assert tzp_plan.action == "remove"
    assert tzp_plan.rendered_comment is None
    assert tzp_plan.existing_status is Status.FOR_REVIEW

    user_comment_plan = build_tzp_comment_write_plan(
        existing_comment="-- translator note",
        desired_status=Status.UNTOUCHED,
    )
    assert user_comment_plan.action == "noop"
    assert user_comment_plan.rendered_comment is None
    assert user_comment_plan.existing_status is None
