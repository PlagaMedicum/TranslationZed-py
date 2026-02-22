#!/usr/bin/env python3
"""Resolve mutation stage profiles into concrete score-gate settings."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class MutationStageResolution:
    """Represent resolved mutation gate settings for a stage profile."""

    mode: str
    min_killed_percent: float


def resolve_mutation_stage(
    *,
    stage: str,
    min_killed_percent: float,
) -> MutationStageResolution:
    """Resolve a stage profile into concrete mode and threshold values."""
    normalized = stage.strip().lower()
    if normalized == "report":
        return MutationStageResolution(mode="warn", min_killed_percent=0.0)
    if normalized == "soft":
        return MutationStageResolution(
            mode="warn",
            min_killed_percent=float(min_killed_percent),
        )
    if normalized == "strict":
        return MutationStageResolution(
            mode="fail",
            min_killed_percent=float(min_killed_percent),
        )
    raise ValueError("stage must be one of: report, soft, strict")


def _format_threshold(value: float) -> str:
    """Format threshold value for env-file output."""
    rounded = round(value)
    if abs(value - rounded) < 1e-9:
        return str(int(rounded))
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _build_argument_parser() -> argparse.ArgumentParser:
    """Build CLI parser."""
    parser = argparse.ArgumentParser(
        description="Resolve mutation stage profile to mode/threshold settings."
    )
    parser.add_argument(
        "--stage",
        required=True,
        choices=("report", "soft", "strict"),
    )
    parser.add_argument(
        "--min-killed-percent",
        type=float,
        default=25.0,
    )
    parser.add_argument(
        "--out-env",
        type=Path,
        required=True,
        help="File path to append KEY=VALUE lines (for example $GITHUB_ENV).",
    )
    return parser


def main() -> int:
    """Resolve mutation stage and append results to env output file."""
    parser = _build_argument_parser()
    args = parser.parse_args()
    resolution = resolve_mutation_stage(
        stage=args.stage,
        min_killed_percent=float(args.min_killed_percent),
    )

    args.out_env.parent.mkdir(parents=True, exist_ok=True)
    with args.out_env.open("a", encoding="utf-8") as env_file:
        env_file.write(f"MUTATION_EFFECTIVE_MODE={resolution.mode}\n")
        env_file.write(
            "MUTATION_EFFECTIVE_MIN_KILLED_PERCENT="
            f"{_format_threshold(resolution.min_killed_percent)}\n"
        )

    print(
        "mutation stage resolved: "
        f"stage={args.stage} mode={resolution.mode} "
        f"min_killed_percent={_format_threshold(resolution.min_killed_percent)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
