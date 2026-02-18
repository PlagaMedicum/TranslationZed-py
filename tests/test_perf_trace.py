"""Test module for GUI performance trace helpers."""

from __future__ import annotations

from io import StringIO

from translationzed_py.gui.perf_trace import (
    _DEFAULT_CATEGORIES,
    PerfTrace,
    _parse_categories,
)


def test_parse_categories_accepts_switches_and_filters_unknown_values() -> None:
    """Verify category parser handles booleans, all, and invalid names."""
    assert _parse_categories("") == set()
    assert _parse_categories("  ") == set()
    assert _parse_categories("true") == _DEFAULT_CATEGORIES
    assert _parse_categories("1") == _DEFAULT_CATEGORIES
    assert _parse_categories("paint,unknown,layout") == {"paint", "layout"}
    assert _parse_categories("cache_scan,all,ignored") == _DEFAULT_CATEGORIES


def test_from_env_reads_trace_env_and_enables_categories(monkeypatch) -> None:
    """Verify trace can be constructed from the environment."""
    monkeypatch.setenv("TZP_PERF_TRACE", "selection,row_resize")
    trace = PerfTrace.from_env()
    assert trace.enabled is True
    assert trace._categories == {"selection", "row_resize"}


def test_start_stop_and_record_manage_bucket_lifecycle(monkeypatch) -> None:
    """Verify trace records timing data and flushes with stable formatting."""

    class _FlushingWriter:
        """Capture writes while simulating flush failures."""

        def __init__(self) -> None:
            self.buffer = StringIO()
            self.flush_calls = 0

        def write(self, text: str) -> None:
            """Capture output lines."""
            self.buffer.write(text)

        def flush(self) -> None:
            """Raise to exercise suppress(Exception) branch."""
            self.flush_calls += 1
            raise RuntimeError("flush failed")

    writer = _FlushingWriter()
    trace = PerfTrace({"paint"}, interval_s=0.0, out=writer)
    trace._last_flush = 0.0

    start_times = iter([10.0, 10.005])
    monotonic_times = iter([100.0, 100.0, 100.0, 100.0])
    monkeypatch.setattr(
        "translationzed_py.gui.perf_trace.time.perf_counter", lambda: next(start_times)
    )
    monkeypatch.setattr(
        "translationzed_py.gui.perf_trace.time.monotonic", lambda: next(monotonic_times)
    )

    assert trace.start("layout") is None
    start = trace.start("paint")
    assert start == 10.0

    trace.stop("paint", start, items=3, unit="cells")
    output = writer.buffer.getvalue()
    assert "perf paint: 1 calls, 3 cells" in output
    assert "1.6667ms/cells" in output
    assert writer.flush_calls == 1
    assert trace._buckets == {}


def test_record_handles_disabled_trace_unit_mismatch_and_empty_flush(
    monkeypatch,
) -> None:
    """Verify disabled mode, unit mismatch, and explicit empty flush behavior."""
    disabled = PerfTrace(set())
    assert disabled.enabled is False
    assert disabled.start("paint") is None
    disabled.record("paint", 1.0, items=2)
    disabled.stop("paint", None)
    assert disabled._buckets == {}

    out = StringIO()
    trace = PerfTrace({"paint"}, interval_s=60.0, out=out)
    trace._last_flush = 100.0

    monotonic_times = iter([101.0, 102.0])
    monkeypatch.setattr(
        "translationzed_py.gui.perf_trace.time.monotonic", lambda: next(monotonic_times)
    )

    trace.record("paint", 6.0, items=-10, unit="rows")
    trace.record("paint", 4.0, items=2, unit="files")
    trace._flush(200.0)

    output = out.getvalue()
    assert "perf paint: 2 calls, 2 rows" in output
    assert "5.0000ms/rows" in output
    assert trace._buckets == {}

    trace._flush(250.0)
    assert trace._last_flush == 250.0
