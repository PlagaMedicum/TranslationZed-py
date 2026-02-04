import os
from collections.abc import Callable
from pathlib import Path

import pytest

# Ensure Qt runs headless in CI/CLI environments without a display server.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_PERF_SAMPLES: list[tuple[str, float, float, str]] = []


def _record_perf(label: str, elapsed_ms: float, budget_ms: float, detail: str) -> None:
    _PERF_SAMPLES.append((label, elapsed_ms, budget_ms, detail))


@pytest.fixture()
def perf_recorder() -> Callable[[str, float, float, str], None]:
    return _record_perf


def pytest_terminal_summary(terminalreporter, exitstatus, config) -> None:  # type: ignore[no-untyped-def]
    if not _PERF_SAMPLES:
        return
    terminalreporter.section("Performance")
    for label, elapsed_ms, budget_ms, detail in _PERF_SAMPLES:
        suffix = f" [{detail}]" if detail else ""
        terminalreporter.line(
            f"{label}: {elapsed_ms:.1f}ms (budget {budget_ms:.1f}ms){suffix}"
        )


@pytest.fixture()
def prod_like_root() -> Path:
    return Path(__file__).parent / "fixtures" / "prod_like"
