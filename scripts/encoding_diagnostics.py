#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from translationzed_py.core.encoding_diagnostics import format_encoding_report
from translationzed_py.core.encoding_diagnostics import scan_encoding_issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="encoding_diagnostics",
        description=(
            "Scan locale files and report encoding conflicts using language.txt charset."
        ),
    )
    parser.add_argument(
        "project_root",
        nargs="?",
        default=".",
        help="Project root to scan (default: current working directory).",
    )
    parser.add_argument(
        "--warn-only",
        action="store_true",
        help="Always exit 0, even if conflicts are detected.",
    )
    args = parser.parse_args(argv)

    root = Path(args.project_root).resolve()
    language_errors, issues = scan_encoding_issues(root)
    print(
        format_encoding_report(root=root, language_errors=language_errors, issues=issues)
    )
    if args.warn_only:
        return 0
    return 1 if language_errors or issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
