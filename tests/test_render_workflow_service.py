"""Test module for render workflow service."""

from __future__ import annotations

from translationzed_py.core.render_workflow_service import RenderWorkflowService


def test_render_workflow_decide_render_cost() -> None:
    """Verify render workflow decide render cost."""
    service = RenderWorkflowService()
    heavy = service.decide_render_cost(
        max_value_length=5000,
        large_text_optimizations=True,
        render_heavy_threshold=1000,
        preview_limit=200,
    )
    assert heavy.render_heavy is True
    assert heavy.preview_limit == 200

    light = service.decide_render_cost(
        max_value_length=200,
        large_text_optimizations=True,
        render_heavy_threshold=1000,
        preview_limit=200,
    )
    assert light.render_heavy is False
    assert light.preview_limit is None


def test_render_workflow_large_file_and_visible_span() -> None:
    """Verify render workflow large file and visible span."""
    service = RenderWorkflowService()
    assert service.is_large_file(
        has_model=True,
        row_count=6000,
        file_size=10,
        row_threshold=5000,
        bytes_threshold=1_000_000,
        large_text_optimizations=True,
        render_heavy=False,
    )
    assert not service.is_large_file(
        has_model=False,
        row_count=0,
        file_size=0,
        row_threshold=1,
        bytes_threshold=1,
        large_text_optimizations=False,
        render_heavy=False,
    )

    span = service.visible_row_span(
        total_rows=100,
        first_visible=10,
        last_visible=19,
        margin_pct=0.2,
    )
    assert span is not None
    assert span[0] <= 10
    assert span[1] >= 19


def test_render_workflow_prefetch_and_resume() -> None:
    """Verify render workflow prefetch and resume."""
    service = RenderWorkflowService()
    prefetch = service.prefetch_span(
        span=(20, 40),
        total_rows=80,
        margin=100,
        large_file_mode=True,
        render_heavy=False,
    )
    assert prefetch == (0, 79)

    heavy_prefetch = service.prefetch_span(
        span=(20, 40),
        total_rows=200,
        margin=200,
        large_file_mode=False,
        render_heavy=True,
    )
    assert heavy_prefetch == (8, 52)

    heavy_large_prefetch = service.prefetch_span(
        span=(20, 40),
        total_rows=200,
        margin=200,
        large_file_mode=True,
        render_heavy=True,
    )
    assert heavy_large_prefetch == (12, 48)

    resumed = service.resume_resize_span(span=(20, 40), cursor=30)
    assert resumed == (30, 40)
    assert service.resume_resize_span(span=(20, 25), cursor=40) is None


def test_render_workflow_handles_disabled_optimizations_and_empty_spans() -> None:
    """Verify render workflow handles disabled mode and empty span inputs."""
    service = RenderWorkflowService()

    decision = service.decide_render_cost(
        max_value_length=9999,
        large_text_optimizations=False,
        render_heavy_threshold=1,
        preview_limit=10,
    )
    assert decision.render_heavy is False
    assert decision.preview_limit is None

    assert (
        service.visible_row_span(
            total_rows=0,
            first_visible=0,
            last_visible=1,
            margin_pct=0.2,
        )
        is None
    )
    assert (
        service.prefetch_span(
            span=None,
            total_rows=10,
            margin=2,
            large_file_mode=False,
            render_heavy=False,
        )
        is None
    )
    assert (
        service.prefetch_span(
            span=(1, 2),
            total_rows=0,
            margin=2,
            large_file_mode=False,
            render_heavy=False,
        )
        is None
    )
    assert service.resume_resize_span(span=None, cursor=0) is None
