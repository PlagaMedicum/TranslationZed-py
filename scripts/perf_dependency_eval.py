#!/usr/bin/env python3
"""Offline trust/speed evaluator for optional performance dependencies."""

from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import json
import random
import statistics
import time
from collections.abc import Callable
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

_ALLOWED_LICENSE_HINTS = (
    "mit",
    "bsd",
    "apache",
    "psf",
)


@dataclass(frozen=True, slots=True)
class GateResult:
    """One trust gate result."""

    name: str
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class PerfSummary:
    """Microbenchmark summary."""

    baseline_median_ms: float
    candidate_median_ms: float
    speed_gain_percent: float
    speed_gain_ci95_low: float
    speed_gain_ci95_high: float
    equivalent: bool


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate optional perf dependency against trust and speed gates."
    )
    parser.add_argument("--candidate", default="rapidfuzz", help="Dependency name.")
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--pairs", type=int, default=800)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--min-gain-percent", type=float, default=15.0)
    parser.add_argument("--out-json", type=Path)
    return parser


def _build_pairs(count: int, seed: int) -> list[tuple[str, str]]:
    rng = random.Random(seed)
    pairs: list[tuple[str, str]] = []
    for idx in range(max(10, count)):
        base = f"token-{idx:05d}-alpha-beta"
        if idx % 5 == 0:
            candidate = base.replace("alpha", "alhpa")
        elif idx % 7 == 0:
            candidate = base + "-extra"
        elif idx % 11 == 0:
            candidate = base[:-3]
        else:
            candidate = base
        salt = rng.randint(0, 999)
        pairs.append((base + f"-{salt}", candidate + f"-{salt}"))
    return pairs


def _baseline_ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b, autojunk=False).ratio()


def _candidate_ratio(candidate: str) -> Callable[[str, str], float] | None:
    try:
        module = importlib.import_module(candidate)
    except ModuleNotFoundError:
        return None

    if candidate == "rapidfuzz":
        fuzz = getattr(module, "fuzz", None)
        if fuzz is None:
            return None
        ratio_fn = getattr(fuzz, "ratio", None)
        if ratio_fn is None:
            return None
        return lambda a, b: float(ratio_fn(a, b)) / 100.0

    ratio_fn = getattr(module, "ratio", None)
    if callable(ratio_fn):
        return lambda a, b: float(ratio_fn(a, b))
    return None


def _measure_ms(repeats: int, fn: Callable[[], object]) -> tuple[list[float], float]:
    values: list[float] = []
    for _ in range(max(1, repeats)):
        start = time.perf_counter()
        fn()
        values.append((time.perf_counter() - start) * 1000.0)
    return values, float(statistics.median(values))


def _bootstrap_speed_gain_ci(
    baseline_samples: list[float],
    candidate_samples: list[float],
    *,
    seed: int,
    iterations: int = 500,
) -> tuple[float, float]:
    rng = random.Random(seed)
    gains: list[float] = []
    size = min(len(baseline_samples), len(candidate_samples))
    if size <= 0:
        return (0.0, 0.0)
    for _ in range(iterations):
        base_draw = [baseline_samples[rng.randrange(size)] for _ in range(size)]
        cand_draw = [candidate_samples[rng.randrange(size)] for _ in range(size)]
        base_median = statistics.median(base_draw)
        cand_median = statistics.median(cand_draw)
        gain = (
            0.0
            if base_median <= 0.0
            else ((base_median - cand_median) / base_median) * 100.0
        )
        gains.append(float(gain))
    gains.sort()
    low_idx = int(round(0.025 * (len(gains) - 1)))
    high_idx = int(round(0.975 * (len(gains) - 1)))
    return gains[low_idx], gains[high_idx]


def _eval_perf(
    candidate: str,
    ratio_fn: Callable[[str, str], float],
    *,
    repeats: int,
    pairs: list[tuple[str, str]],
    seed: int,
) -> PerfSummary:
    baseline_result = [_baseline_ratio(a, b) for a, b in pairs]
    candidate_result = [ratio_fn(a, b) for a, b in pairs]
    equivalent = candidate_result == baseline_result

    def _run_baseline() -> float:
        return sum(_baseline_ratio(a, b) for a, b in pairs)

    def _run_candidate() -> float:
        return sum(ratio_fn(a, b) for a, b in pairs)

    baseline_samples, baseline_median_ms = _measure_ms(repeats, _run_baseline)
    candidate_samples, candidate_median_ms = _measure_ms(repeats, _run_candidate)
    speed_gain_percent = (
        ((baseline_median_ms - candidate_median_ms) / baseline_median_ms) * 100.0
        if baseline_median_ms > 0.0
        else 0.0
    )
    ci_low, ci_high = _bootstrap_speed_gain_ci(
        baseline_samples,
        candidate_samples,
        seed=seed + 997,
    )
    return PerfSummary(
        baseline_median_ms=baseline_median_ms,
        candidate_median_ms=candidate_median_ms,
        speed_gain_percent=float(speed_gain_percent),
        speed_gain_ci95_low=float(ci_low),
        speed_gain_ci95_high=float(ci_high),
        equivalent=equivalent,
    )


def _license_gate(candidate: str) -> GateResult:
    try:
        metadata = importlib.metadata.metadata(candidate)
    except importlib.metadata.PackageNotFoundError:
        return GateResult("license", False, "package not installed")
    license_text = (metadata.get("License") or "").strip().lower()
    if not license_text:
        return GateResult("license", False, "missing license metadata")
    if any(hint in license_text for hint in _ALLOWED_LICENSE_HINTS):
        return GateResult("license", True, license_text)
    return GateResult("license", False, license_text)


def _runtime_side_effect_gate(candidate: str) -> GateResult:
    if candidate == "rapidfuzz":
        return GateResult("runtime_side_effects", True, "pure compute library")
    return GateResult(
        "runtime_side_effects",
        False,
        "unknown runtime side-effect profile; manual review required",
    )


def _compat_gate(candidate: str) -> GateResult:
    try:
        metadata = importlib.metadata.metadata(candidate)
    except importlib.metadata.PackageNotFoundError:
        return GateResult("py310_cross_platform", False, "package not installed")
    requires_python = (metadata.get("Requires-Python") or "").strip()
    if not requires_python:
        return GateResult("py310_cross_platform", False, "missing Requires-Python")
    # Conservative gate: accept when upper/lower bounds do not obviously exclude 3.10.
    if "3.10" in requires_python or ">=3" in requires_python:
        return GateResult("py310_cross_platform", True, requires_python)
    return GateResult("py310_cross_platform", False, requires_python)


def main() -> int:
    """Execute trust/speed gates for a candidate perf dependency."""
    args = _build_parser().parse_args()
    candidate = args.candidate.strip()
    pairs = _build_pairs(args.pairs, args.seed)

    ratio_fn = _candidate_ratio(candidate)
    gates: list[GateResult] = [
        _license_gate(candidate),
        _runtime_side_effect_gate(candidate),
        _compat_gate(candidate),
    ]

    perf_summary: PerfSummary | None = None
    if ratio_fn is None:
        gates.append(
            GateResult(
                "measurement",
                False,
                "candidate backend unavailable or missing ratio API",
            )
        )
    else:
        perf_summary = _eval_perf(
            candidate,
            ratio_fn,
            repeats=max(1, args.repeats),
            pairs=pairs,
            seed=args.seed,
        )
        gates.append(
            GateResult(
                "gain_gt_15_percent",
                perf_summary.speed_gain_percent > args.min_gain_percent,
                (
                    f"gain={perf_summary.speed_gain_percent:.2f}% "
                    f"threshold={args.min_gain_percent:.2f}%"
                ),
            )
        )
        gates.append(
            GateResult(
                "bit_stable_equivalence",
                perf_summary.equivalent,
                (
                    "candidate ratios exactly match baseline"
                    if perf_summary.equivalent
                    else "ratio drift"
                ),
            )
        )

    passed = all(item.passed for item in gates)
    payload: dict[str, object] = {
        "candidate": candidate,
        "passed": passed,
        "gates": [
            {"name": item.name, "passed": item.passed, "detail": item.detail}
            for item in gates
        ],
    }
    if perf_summary is not None:
        payload["perf"] = {
            "baseline_median_ms": perf_summary.baseline_median_ms,
            "candidate_median_ms": perf_summary.candidate_median_ms,
            "speed_gain_percent": perf_summary.speed_gain_percent,
            "speed_gain_ci95_low": perf_summary.speed_gain_ci95_low,
            "speed_gain_ci95_high": perf_summary.speed_gain_ci95_high,
            "equivalent": perf_summary.equivalent,
        }

    status = "PASS" if passed else "REJECT"
    print(f"dependency gate: {status} [{candidate}]")
    for gate in gates:
        mark = "ok" if gate.passed else "fail"
        print(f"  - {gate.name}: {mark} ({gate.detail})")

    if args.out_json:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        args.out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"wrote report: {args.out_json}")

    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
