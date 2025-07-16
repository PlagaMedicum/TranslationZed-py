"""CLI / GUI entry-point for TranslationZed-Py."""
from __future__ import annotations

import argparse
import sys
from importlib import metadata
from pathlib import Path

from translationzed_py.gui import launch


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="translationzed-py",
        description="Open the TranslationZed GUI, optionally pointing at a project root.",
    )
    parser.add_argument(
        "project",
        nargs="?",
        type=Path,
        help="project root folder (defaults to current directory)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {metadata.version('translationzed_py')}",
    )

    args = parser.parse_args(argv)
    launch(str(args.project) if args.project else None)


if __name__ == "__main__":
    main()
