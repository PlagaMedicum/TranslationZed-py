#!/usr/bin/env python3
"""Run fixture-backed performance scenarios with configurable time budgets."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from translationzed_py.core import parse_lazy
from translationzed_py.core.project_scanner import scan_root_with_errors


def _budget_ms(env_name: str, default_ms: float) -> float:
    raw = os.getenv(env_name, "")
    if not raw:
        return default_ms
    try:
        return float(raw)
    except ValueError:
        return default_ms


def _measure(label: str, budget_ms: float, fn, info: str) -> tuple[bool, object]:
    start = time.perf_counter()
    result = fn()
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    ok = elapsed_ms <= budget_ms
    status = "OK" if ok else "SLOW"
    print(
        f"{label}: {elapsed_ms:.1f}ms (budget {budget_ms:.1f}ms) [{info}] {status}",
        flush=True,
    )
    return ok, result


def _pick_indices(count: int) -> list[int]:
    if count <= 0:
        return []
    indices = {0, count // 2, count - 1}
    return sorted(idx for idx in indices if 0 <= idx < count)


def main() -> int:
    """Execute performance scenario probes and return pass/fail status."""
    root_arg = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    env_root_raw = os.getenv("TZP_PERF_ROOT", "").strip()
    root = Path("tests/fixtures/perf_root")
    if root_arg:
        root = root_arg.expanduser()
    elif env_root_raw:
        env_root = Path(env_root_raw).expanduser()
        if env_root.is_dir():
            root = env_root
        else:
            print(
                f"Warning: TZP_PERF_ROOT does not exist, using fixture root: {env_root}",
                file=sys.stderr,
            )
    root = root.resolve()
    if not root.is_dir():
        print(f"Missing translations root: {root}", file=sys.stderr)
        print("Set TZP_PERF_ROOT or pass a path argument.", file=sys.stderr)
        return 2

    locales, errors = scan_root_with_errors(root)
    if errors:
        print("language.txt warnings:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)

    meta = locales.get("BE")
    if not meta:
        print("Locale BE not found or invalid language.txt.", file=sys.stderr)
        return 2

    targets = [
        root / "BE" / "SurvivalGuide_BE.txt",
        root / "BE" / "Recorded_Media_BE.txt",
        root / "BE" / "News_BE.txt",
    ]
    for path in targets:
        if not path.exists():
            print(f"Missing file: {path}", file=sys.stderr)
            return 2

    parse_budget = _budget_ms("TZP_PERF_SCEN_PARSE_MS", 4000.0)
    maxlen_budget = _budget_ms("TZP_PERF_SCEN_MAXLEN_MS", 400.0)
    preview_budget = _budget_ms("TZP_PERF_SCEN_PREVIEW_MS", 50.0)
    prefetch_budget = _budget_ms("TZP_PERF_SCEN_PREFETCH_MS", 200.0)
    preview_limit = int(os.getenv("TZP_PERF_SCEN_PREVIEW_LIMIT", "200"))
    prefetch_window = int(os.getenv("TZP_PERF_SCEN_PREFETCH_WINDOW", "400"))

    any_fail = False
    for path in targets:
        print(f"\n== {path.relative_to(root)} ==")
        ok, pf = _measure(
            "parse_lazy",
            parse_budget,
            lambda p=path: parse_lazy(p, encoding=meta.charset),
            f"charset={meta.charset}",
        )
        any_fail |= not ok
        entries = pf.entries
        count = len(entries)

        if hasattr(entries, "max_value_length"):
            ok, max_len = _measure(
                "max_value_length",
                maxlen_budget,
                entries.max_value_length,
                f"entries={count}",
            )
            any_fail |= not ok
        else:
            max_len = "n/a"

        if hasattr(entries, "preview_at"):
            indices = _pick_indices(count)

            def _run_preview(
                *,
                entries_ref=entries,
                indices_ref=indices,
                preview_limit_ref=preview_limit,
            ) -> None:
                for idx in indices_ref:
                    entries_ref.preview_at(idx, preview_limit_ref)

            ok, _ = _measure(
                "preview_at",
                preview_budget,
                _run_preview,
                f"indices={indices} limit={preview_limit} max_len={max_len}",
            )
            any_fail |= not ok

        if hasattr(entries, "prefetch") and count > 0:
            window = max(1, min(prefetch_window, count))
            ok, _ = _measure(
                "prefetch",
                prefetch_budget,
                lambda w=window, entries_ref=entries: entries_ref.prefetch(0, w - 1),
                f"window={window} entries={count}",
            )
            any_fail |= not ok

    return 1 if any_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
