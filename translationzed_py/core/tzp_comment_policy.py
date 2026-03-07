"""Contracts for namespaced program-generated status comments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .model import Status

TZP_STATUS_NAMESPACE = "TZP:"
TZP_COMMENT_PREFIX_DEFAULT = "--"

_STATUS_BY_NORMALIZED_TEXT: dict[str, Status] = {
    "FOR REVIEW": Status.FOR_REVIEW,
    "TRANSLATED": Status.TRANSLATED,
    "PROOFREAD": Status.PROOFREAD,
}

_TZP_TEXT_BY_STATUS: dict[Status, str] = {
    Status.FOR_REVIEW: "FOR_REVIEW",
    Status.TRANSLATED: "TRANSLATED",
    Status.PROOFREAD: "PROOFREAD",
}

TZPCommentPlanAction = Literal["insert", "update", "remove", "noop"]


@dataclass(frozen=True, slots=True)
class TZPCommentWritePlan:
    """Deterministic write decision for one status-comment slot."""

    action: TZPCommentPlanAction
    rendered_comment: str | None
    existing_status: Status | None


def _strip_comment_delimiters(comment_text: str) -> str:
    text = comment_text.strip()
    if text.startswith("--") or text.startswith("//"):
        return text[2:].strip()
    if text.startswith("#"):
        return text[1:].strip()
    if text.startswith("/*") and text.endswith("*/"):
        return text[2:-2].strip()
    return text


def _status_from_text(text: str) -> Status | None:
    normalized = " ".join(text.strip().upper().replace("_", " ").split())
    return _STATUS_BY_NORMALIZED_TEXT.get(normalized)


def parse_tzp_status_comment(comment_text: str) -> Status | None:
    """Return status for a namespaced `TZP:` comment, or `None` when absent."""
    body = _strip_comment_delimiters(comment_text)
    if not body.upper().startswith(TZP_STATUS_NAMESPACE):
        return None
    payload = body[len(TZP_STATUS_NAMESPACE) :].strip()
    return _status_from_text(payload)


def parse_status_comment(comment_text: str) -> Status | None:
    """Return status for either namespaced or legacy status comment text."""
    tzp_status = parse_tzp_status_comment(comment_text)
    if tzp_status is not None:
        return tzp_status
    body = _strip_comment_delimiters(comment_text)
    return _status_from_text(body)


def format_tzp_status_comment(
    status: Status,
    *,
    comment_prefix: str = TZP_COMMENT_PREFIX_DEFAULT,
) -> str:
    """Render one canonical namespaced program-generated status comment."""
    prefix = comment_prefix.strip()
    if not prefix:
        raise ValueError("comment_prefix must not be empty")
    tzp_text = _TZP_TEXT_BY_STATUS.get(status)
    if tzp_text is None:
        raise ValueError("TZP status comments support FOR_REVIEW/TRANSLATED/PROOFREAD")
    return f"{prefix} {TZP_STATUS_NAMESPACE}{tzp_text}"


def build_tzp_comment_write_plan(
    *,
    existing_comment: str | None,
    desired_status: Status | None,
    comment_prefix: str = TZP_COMMENT_PREFIX_DEFAULT,
) -> TZPCommentWritePlan:
    """Return a deterministic write action while protecting user comments."""
    current_text = (existing_comment or "").strip()
    existing_status = parse_tzp_status_comment(current_text) if current_text else None

    if desired_status is None or desired_status is Status.UNTOUCHED:
        if existing_status is None:
            return TZPCommentWritePlan(
                action="noop",
                rendered_comment=None,
                existing_status=None,
            )
        return TZPCommentWritePlan(
            action="remove",
            rendered_comment=None,
            existing_status=existing_status,
        )

    rendered = format_tzp_status_comment(
        desired_status,
        comment_prefix=comment_prefix,
    )
    if existing_status is None:
        return TZPCommentWritePlan(
            action="insert",
            rendered_comment=rendered,
            existing_status=None,
        )
    if current_text == rendered:
        return TZPCommentWritePlan(
            action="noop",
            rendered_comment=rendered,
            existing_status=existing_status,
        )
    return TZPCommentWritePlan(
        action="update",
        rendered_comment=rendered,
        existing_status=existing_status,
    )


__all__ = [
    "TZP_STATUS_NAMESPACE",
    "TZP_COMMENT_PREFIX_DEFAULT",
    "TZPCommentWritePlan",
    "build_tzp_comment_write_plan",
    "format_tzp_status_comment",
    "parse_status_comment",
    "parse_tzp_status_comment",
]
