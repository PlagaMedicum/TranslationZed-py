#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from translationzed_py.core.architecture_guard import check_rules


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verify GUI/core import boundaries and main-window size guardrails."
        )
    )
    parser.add_argument(
        "--root",
        default=None,
        help="Repository root to check (defaults to this script's repo root).",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    root = (
        Path(args.root).resolve() if args.root else Path(__file__).resolve().parents[1]
    )
    violations = check_rules(root)
    if violations:
        print("Architecture guard violations:")
        for item in violations:
            print(f"- {item}")
        return 1
    print("Architecture guards passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
