"""Test module for qa perf autoderived."""

from __future__ import annotations

import gc
import os
import time
from pathlib import Path

from translationzed_py.core import parse_lazy
from translationzed_py.core.qa_service import QAInputRow, QAService


def _budget_ms(env_name: str, default_ms: float) -> float:
    raw = os.getenv(env_name, "")
    if not raw:
        return default_ms
    try:
        return float(raw)
    except ValueError:
        return default_ms


def _perf_fixture_path(name: str) -> Path:
    return Path(__file__).parent / "fixtures" / "perf_root" / "BE" / name


def _run_fixture_scan_perf(
    *,
    fixture_name: str,
    perf_label: str,
    budget_env: str,
    budget_default_ms: float,
    perf_recorder,
) -> None:
    path = _perf_fixture_path(fixture_name)
    pf = parse_lazy(path, encoding="utf-8")
    rows = tuple(
        QAInputRow(row=idx, source_text=entry.value, target_text=entry.value)
        for idx, entry in enumerate(pf.entries)
    )
    service = QAService()
    budget_ms = _budget_ms(budget_env, budget_default_ms)

    gc.collect()
    start = time.perf_counter()
    findings = service.scan_rows(
        file=path,
        rows=rows,
        check_trailing=True,
        check_newlines=True,
        check_tokens=True,
        check_same_as_source=False,
    )
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    assert findings == ()
    perf_recorder(
        perf_label,
        elapsed_ms,
        budget_ms,
        f"entries={len(rows)} file={fixture_name}",
    )
    assert elapsed_ms <= budget_ms


def test_qa_scan_perf_survivalguide_fixture(perf_recorder) -> None:
    """Verify qa scan perf survivalguide fixture."""
    _run_fixture_scan_perf(
        fixture_name="SurvivalGuide_BE.txt",
        perf_label="qa scan survivalguide",
        budget_env="TZP_PERF_QA_SCAN_MS",
        budget_default_ms=1200.0,
        perf_recorder=perf_recorder,
    )


def test_qa_scan_perf_recorded_media_fixture(perf_recorder) -> None:
    """Verify qa scan perf recorded media fixture."""
    _run_fixture_scan_perf(
        fixture_name="Recorded_Media_BE.txt",
        perf_label="qa scan recorded_media",
        budget_env="TZP_PERF_QA_SCAN_MS",
        budget_default_ms=1200.0,
        perf_recorder=perf_recorder,
    )
