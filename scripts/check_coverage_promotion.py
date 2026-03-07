#!/usr/bin/env python3
"""Check coverage summary artifacts for coverage-floor promotion readiness."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

EPSILON = 1e-9
EXIT_READY = 0
EXIT_NOT_READY = 1
EXIT_INVALID_INPUT = 2


@dataclass(frozen=True, slots=True)
class RunQualification:
    """Represent qualification details for one coverage summary artifact."""

    path: str
    qualifies: bool
    reasons: list[str]
    gate_passed: bool
    overall_percent: float
    core_percent: float
    overall_fail_under: float
    core_fail_under: float


@dataclass(frozen=True, slots=True)
class PromotionEvaluation:
    """Represent readiness verdict across an ordered summary series."""

    ready: bool
    required_consecutive: int
    min_overall: float
    min_core: float
    qualifying_tail_streak: int
    total_summaries: int
    results: list[RunQualification]


def _require_bool(value: Any, *, field: str) -> bool:
    """Return a validated boolean field value."""
    if not isinstance(value, bool):
        raise ValueError(f"Invalid '{field}': expected boolean.")
    return value


def _require_float(value: Any, *, field: str) -> float:
    """Return a validated numeric field value as float."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Invalid '{field}': expected numeric value.")
    return float(value)


def _load_summary(path: Path) -> dict[str, Any]:
    """Load one coverage summary payload from JSON."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Cannot read summary file '{path}': {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in summary file '{path}': {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid payload in '{path}': expected JSON object.")
    return payload


def _qualify_summary(
    *,
    path: Path,
    payload: dict[str, Any],
    min_overall: float,
    min_core: float,
) -> RunQualification:
    """Evaluate whether one coverage summary satisfies promotion criteria."""
    gate_passed = _require_bool(payload.get("gate_passed"), field="gate_passed")
    overall_percent = _require_float(
        payload.get("overall_percent"), field="overall_percent"
    )
    core_percent = _require_float(payload.get("core_percent"), field="core_percent")
    overall_fail_under = _require_float(
        payload.get("overall_fail_under"), field="overall_fail_under"
    )
    core_fail_under = _require_float(
        payload.get("core_fail_under"), field="core_fail_under"
    )

    reasons: list[str] = []
    if not gate_passed:
        reasons.append("gate_passed=false")
    if overall_percent + EPSILON < min_overall:
        reasons.append(f"overall_percent={overall_percent:.2f} < {min_overall:.2f}")
    if core_percent + EPSILON < min_core:
        reasons.append(f"core_percent={core_percent:.2f} < {min_core:.2f}")
    if overall_fail_under + EPSILON < min_overall:
        reasons.append(
            f"overall_fail_under={overall_fail_under:.2f} < {min_overall:.2f}"
        )
    if core_fail_under + EPSILON < min_core:
        reasons.append(f"core_fail_under={core_fail_under:.2f} < {min_core:.2f}")

    return RunQualification(
        path=str(path),
        qualifies=not reasons,
        reasons=reasons,
        gate_passed=gate_passed,
        overall_percent=overall_percent,
        core_percent=core_percent,
        overall_fail_under=overall_fail_under,
        core_fail_under=core_fail_under,
    )


def evaluate_promotion_readiness(
    *,
    summaries: list[Path],
    required_consecutive: int,
    min_overall: float,
    min_core: float,
) -> PromotionEvaluation:
    """Evaluate coverage-floor promotion readiness from ordered summary paths."""
    if required_consecutive < 1:
        raise ValueError("--required-consecutive must be >= 1.")
    if min_overall < 0 or min_core < 0:
        raise ValueError("--min-overall/--min-core must be >= 0.")

    results: list[RunQualification] = []
    for path in summaries:
        payload = _load_summary(path)
        results.append(
            _qualify_summary(
                path=path,
                payload=payload,
                min_overall=min_overall,
                min_core=min_core,
            )
        )

    tail_streak = 0
    for result in reversed(results):
        if result.qualifies:
            tail_streak += 1
            continue
        break

    return PromotionEvaluation(
        ready=tail_streak >= required_consecutive,
        required_consecutive=required_consecutive,
        min_overall=min_overall,
        min_core=min_core,
        qualifying_tail_streak=tail_streak,
        total_summaries=len(results),
        results=results,
    )


def _build_parser() -> argparse.ArgumentParser:
    """Build the coverage promotion checker CLI parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Check ordered coverage-summary artifacts and determine whether "
            "coverage-floor promotion readiness criteria are met."
        )
    )
    parser.add_argument(
        "--summaries",
        nargs="+",
        required=True,
        help="Ordered coverage-summary JSON paths (oldest to newest).",
    )
    parser.add_argument(
        "--required-consecutive",
        type=int,
        default=2,
        help="Required qualifying tail streak (default: 2).",
    )
    parser.add_argument(
        "--min-overall",
        type=float,
        default=92.0,
        help="Minimum required whole-package coverage percent (default: 92).",
    )
    parser.add_argument(
        "--min-core",
        type=float,
        default=97.0,
        help="Minimum required core coverage percent (default: 97).",
    )
    parser.add_argument(
        "--out-json",
        type=Path,
        default=None,
        help="Optional output path for machine-readable evaluation JSON.",
    )
    return parser


def _print_report(evaluation: PromotionEvaluation) -> None:
    """Print a concise promotion-readiness report to stdout."""
    print(
        "coverage promotion check: "
        f"ready={evaluation.ready} "
        f"tail_streak={evaluation.qualifying_tail_streak}/"
        f"{evaluation.required_consecutive} "
        f"min_overall={evaluation.min_overall:.2f} "
        f"min_core={evaluation.min_core:.2f}"
    )
    for result in evaluation.results:
        if result.qualifies:
            print(
                "OK "
                f"{result.path} "
                f"overall={result.overall_percent:.2f} "
                f"core={result.core_percent:.2f} "
                f"fail_under=({result.overall_fail_under:.2f},"
                f"{result.core_fail_under:.2f})"
            )
            continue
        print(f"FAIL {result.path}: {'; '.join(result.reasons)}")


def _write_json_report(path: Path, evaluation: PromotionEvaluation) -> None:
    """Write evaluation payload as UTF-8 JSON."""
    payload = asdict(evaluation)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    """Run the coverage promotion readiness checker."""
    args = _build_parser().parse_args()
    try:
        evaluation = evaluate_promotion_readiness(
            summaries=[Path(value).resolve() for value in args.summaries],
            required_consecutive=args.required_consecutive,
            min_overall=float(args.min_overall),
            min_core=float(args.min_core),
        )
    except ValueError as exc:
        print(f"coverage promotion check input error: {exc}", file=sys.stderr)
        return EXIT_INVALID_INPUT

    if args.out_json is not None:
        _write_json_report(args.out_json, evaluation)
    _print_report(evaluation)
    if evaluation.ready:
        return EXIT_READY
    return EXIT_NOT_READY


if __name__ == "__main__":
    raise SystemExit(main())
