from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RenderCostDecision:
    render_heavy: bool
    preview_limit: int | None


@dataclass(frozen=True, slots=True)
class RenderWorkflowService:
    def decide_render_cost(
        self,
        *,
        max_value_length: int,
        large_text_optimizations: bool,
        render_heavy_threshold: int,
        preview_limit: int,
    ) -> RenderCostDecision:
        if not large_text_optimizations:
            return RenderCostDecision(render_heavy=False, preview_limit=None)
        if max_value_length >= render_heavy_threshold:
            return RenderCostDecision(
                render_heavy=True,
                preview_limit=preview_limit,
            )
        return RenderCostDecision(render_heavy=False, preview_limit=None)

    def is_large_file(
        self,
        *,
        has_model: bool,
        row_count: int,
        file_size: int,
        row_threshold: int,
        bytes_threshold: int,
        large_text_optimizations: bool,
        render_heavy: bool,
    ) -> bool:
        if not has_model:
            return False
        return bool(
            row_count >= row_threshold
            or file_size >= bytes_threshold
            or (large_text_optimizations and render_heavy)
        )

    def visible_row_span(
        self,
        *,
        total_rows: int,
        first_visible: int,
        last_visible: int,
        margin_pct: float,
    ) -> tuple[int, int] | None:
        if total_rows <= 0:
            return None
        first = 0 if first_visible < 0 else first_visible
        last = (total_rows - 1) if last_visible < 0 else last_visible
        visible = max(1, last - first + 1)
        margin = max(2, int(visible * margin_pct))
        start = max(0, first - margin)
        end = min(total_rows - 1, last + margin)
        return start, end

    def prefetch_span(
        self,
        *,
        span: tuple[int, int] | None,
        total_rows: int,
        margin: int,
        large_file_mode: bool,
    ) -> tuple[int, int] | None:
        if span is None or total_rows <= 0:
            return None
        start, end = span
        effective_margin = min(margin, 50) if large_file_mode else margin
        return (
            max(0, start - effective_margin),
            min(total_rows - 1, end + effective_margin),
        )

    def resume_resize_span(
        self,
        *,
        span: tuple[int, int] | None,
        cursor: int | None,
    ) -> tuple[int, int] | None:
        if span is None:
            return None
        start, end = span
        if cursor is not None:
            start = max(start, cursor)
        if start > end:
            return None
        return start, end
