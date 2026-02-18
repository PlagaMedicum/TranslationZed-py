#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BenchSample:
    """Normalized benchmark sample for comparison."""

    name: str
    median_ms: float


def _load_json(path: Path) -> dict[str, object]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RuntimeError(f"Cannot read benchmark file {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid benchmark JSON at {path}: {exc}") from exc


def _samples_from_pytest_benchmark(
    payload: dict[str, object],
) -> dict[str, BenchSample]:
    rows = payload.get("benchmarks")
    if not isinstance(rows, list):
        raise RuntimeError("Benchmark JSON is missing 'benchmarks' list.")

    out: dict[str, BenchSample] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = row.get("name")
        stats = row.get("stats")
        if not isinstance(name, str) or not isinstance(stats, dict):
            continue
        median = stats.get("median")
        if not isinstance(median, (float, int)):
            continue
        out[name] = BenchSample(name=name, median_ms=float(median) * 1000.0)

    if not out:
        raise RuntimeError("No benchmark medians found in current benchmark JSON.")
    return out


def _samples_from_baseline(
    payload: dict[str, object],
    *,
    platform_key: str,
) -> dict[str, BenchSample]:
    platforms = payload.get("platforms")
    if isinstance(platforms, dict):
        selected = platforms.get(platform_key)
        if selected is None:
            return {}
        if not isinstance(selected, dict):
            raise RuntimeError(
                f"Invalid baseline platform section for '{platform_key}'."
            )
        payload = selected

    raw = payload.get("benchmarks")
    if not isinstance(raw, dict):
        raise RuntimeError("Baseline JSON must contain a 'benchmarks' object.")

    out: dict[str, BenchSample] = {}
    for name, row in raw.items():
        if not isinstance(name, str) or not isinstance(row, dict):
            continue
        median_ms = row.get("median_ms")
        if isinstance(median_ms, (float, int)):
            out[name] = BenchSample(name=name, median_ms=float(median_ms))
    return out


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check pytest-benchmark medians against baseline thresholds."
    )
    parser.add_argument("--baseline", required=True, help="Path to baseline JSON file.")
    parser.add_argument(
        "--current", required=True, help="Path to current benchmark JSON."
    )
    parser.add_argument(
        "--threshold-percent",
        type=float,
        default=20.0,
        help="Maximum allowed median regression percentage before failing.",
    )
    parser.add_argument(
        "--mode",
        choices=("warn", "fail"),
        default="fail",
        help="warn: print regressions only. fail: return non-zero on regressions.",
    )
    parser.add_argument(
        "--platform",
        default="linux",
        help="Platform key to read from baseline 'platforms' map.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    baseline_path = Path(args.baseline).resolve()
    current_path = Path(args.current).resolve()

    baseline_payload = _load_json(baseline_path)
    current_payload = _load_json(current_path)

    baseline = _samples_from_baseline(baseline_payload, platform_key=args.platform)
    if not baseline:
        print(
            f"Benchmark baseline has no '{args.platform}' section; skipping regression check.",
            file=sys.stderr,
        )
        return 0

    current = _samples_from_pytest_benchmark(current_payload)

    missing = sorted(name for name in baseline if name not in current)
    regressions: list[tuple[str, float, float, float]] = []
    allowed_factor = 1.0 + (args.threshold_percent / 100.0)

    for name, base in baseline.items():
        sample = current.get(name)
        if sample is None:
            continue
        ratio = sample.median_ms / base.median_ms if base.median_ms > 0 else 0.0
        if ratio > allowed_factor:
            regressions.append((name, base.median_ms, sample.median_ms, ratio))

    if missing:
        print("Missing benchmarks in current run:")
        for name in missing:
            print(f"- {name}")

    if regressions:
        print(
            "Benchmark regressions above "
            f"{args.threshold_percent:.1f}% threshold ({args.platform}):"
        )
        for name, base_ms, current_ms, ratio in regressions:
            growth = (ratio - 1.0) * 100.0
            print(
                f"- {name}: baseline={base_ms:.2f}ms current={current_ms:.2f}ms (+{growth:.1f}%)"
            )

    if not missing and not regressions:
        print(
            f"Benchmark regression check passed for platform={args.platform}"
            f" (threshold={args.threshold_percent:.1f}%)."
        )
        return 0

    if args.mode == "warn":
        print("Benchmark regression check is advisory (mode=warn).", file=sys.stderr)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
