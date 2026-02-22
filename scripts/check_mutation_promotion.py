#!/usr/bin/env python3
"""Check mutation summary artifacts for stage-promotion readiness."""

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
    """Represent qualification details for one mutation summary artifact."""

    path: str
    qualifies: bool
    reasons: list[str]
    mode: str
    passed: bool
    warned: bool
    actionable_total: int
    killed_percent: float


@dataclass(frozen=True, slots=True)
class PromotionEvaluation:
    """Represent readiness verdict across an ordered summary series."""

    ready: bool
    required_consecutive: int
    min_killed_percent: float
    require_mode: str
    qualifying_tail_streak: int
    total_summaries: int
    results: list[RunQualification]


def _require_int(value: Any, *, field: str) -> int:
    """Return a validated integer field value."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"Invalid '{field}': expected integer.")
    return value


def _require_float(value: Any, *, field: str) -> float:
    """Return a validated numeric field value as float."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Invalid '{field}': expected numeric value.")
    return float(value)


def _require_bool(value: Any, *, field: str) -> bool:
    """Return a validated boolean field value."""
    if not isinstance(value, bool):
        raise ValueError(f"Invalid '{field}': expected boolean.")
    return value


def _load_summary(path: Path) -> dict[str, Any]:
    """Load one mutation summary payload from JSON."""
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
    require_mode: str,
    min_killed_percent: float,
) -> RunQualification:
    """Evaluate whether one summary satisfies strict promotion criteria."""
    mode = payload.get("mode")
    if not isinstance(mode, str):
        raise ValueError(f"Invalid 'mode' in '{path}': expected string.")
    passed = _require_bool(payload.get("passed"), field="passed")
    warned = _require_bool(payload.get("warned"), field="warned")
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        raise ValueError(f"Invalid 'summary' in '{path}': expected object.")
    actionable_total = _require_int(
        summary.get("actionable_total"), field="summary.actionable_total"
    )
    killed_percent = _require_float(
        summary.get("killed_percent"), field="summary.killed_percent"
    )

    reasons: list[str] = []
    if mode != require_mode:
        reasons.append(f"mode={mode!r} != {require_mode!r}")
    if not passed:
        reasons.append("passed=false")
    if warned:
        reasons.append("warned=true")
    if actionable_total <= 0:
        reasons.append("actionable_total<=0")
    if killed_percent + EPSILON < min_killed_percent:
        reasons.append(
            f"killed_percent={killed_percent:.2f} < {min_killed_percent:.2f}"
        )

    return RunQualification(
        path=str(path),
        qualifies=not reasons,
        reasons=reasons,
        mode=mode,
        passed=passed,
        warned=warned,
        actionable_total=actionable_total,
        killed_percent=killed_percent,
    )


def evaluate_promotion_readiness(
    *,
    summaries: list[Path],
    required_consecutive: int,
    min_killed_percent: float,
    require_mode: str,
) -> PromotionEvaluation:
    """Evaluate promotion readiness from ordered summary artifact paths."""
    if required_consecutive < 1:
        raise ValueError("--required-consecutive must be >= 1.")
    if min_killed_percent < 0:
        raise ValueError("--min-killed-percent must be >= 0.")

    results: list[RunQualification] = []
    for path in summaries:
        payload = _load_summary(path)
        results.append(
            _qualify_summary(
                path=path,
                payload=payload,
                require_mode=require_mode,
                min_killed_percent=min_killed_percent,
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
        min_killed_percent=min_killed_percent,
        require_mode=require_mode,
        qualifying_tail_streak=tail_streak,
        total_summaries=len(results),
        results=results,
    )


def _build_parser() -> argparse.ArgumentParser:
    """Build the mutation promotion checker CLI parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Check ordered mutation summary artifacts and determine whether "
            "default stage promotion readiness criteria are met."
        )
    )
    parser.add_argument(
        "--summaries",
        nargs="+",
        required=True,
        help="Ordered summary.json paths (oldest to newest).",
    )
    parser.add_argument(
        "--required-consecutive",
        type=int,
        default=2,
        help="Required qualifying tail streak (default: 2).",
    )
    parser.add_argument(
        "--min-killed-percent",
        type=float,
        default=25.0,
        help="Minimum required killed-percent per qualifying run (default: 25).",
    )
    parser.add_argument(
        "--require-mode",
        choices=("warn", "fail", "off"),
        default="fail",
        help="Required summary gate mode for a qualifying run (default: fail).",
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
        "mutation promotion check: "
        f"ready={evaluation.ready} "
        f"tail_streak={evaluation.qualifying_tail_streak}/"
        f"{evaluation.required_consecutive} "
        f"required_mode={evaluation.require_mode} "
        f"min_killed_percent={evaluation.min_killed_percent:.2f}"
    )
    for result in evaluation.results:
        if result.qualifies:
            print(
                "OK "
                f"{result.path} "
                f"mode={result.mode} "
                f"killed_percent={result.killed_percent:.2f} "
                f"actionable_total={result.actionable_total}"
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
    """Run the mutation promotion readiness checker."""
    args = _build_parser().parse_args()
    try:
        evaluation = evaluate_promotion_readiness(
            summaries=[Path(value).resolve() for value in args.summaries],
            required_consecutive=args.required_consecutive,
            min_killed_percent=float(args.min_killed_percent),
            require_mode=str(args.require_mode),
        )
    except ValueError as exc:
        print(f"mutation promotion check input error: {exc}", file=sys.stderr)
        return EXIT_INVALID_INPUT

    if args.out_json is not None:
        _write_json_report(args.out_json, evaluation)
    _print_report(evaluation)
    if evaluation.ready:
        return EXIT_READY
    return EXIT_NOT_READY


if __name__ == "__main__":
    raise SystemExit(main())
