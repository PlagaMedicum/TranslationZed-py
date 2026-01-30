"""CLI / GUI entry-point for TranslationZed-Py."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from translationzed_py import __version__


def _configure_qt_env() -> None:
    if not getattr(sys, "frozen", False):
        return
    roots = []
    if hasattr(sys, "_MEIPASS"):
        roots.append(Path(sys._MEIPASS))
    roots.append(Path(sys.executable).resolve().parent / "_internal")
    plugin_path = None
    for root in roots:
        candidate = root / "PySide6" / "Qt" / "plugins"
        if candidate.is_dir():
            plugin_path = candidate
            break
    if plugin_path is None:
        tried = ", ".join(str(r / "PySide6/Qt/plugins") for r in roots)
        print(
            f"TranslationZed: Qt plugin path not found in bundle (tried: {tried})",
            file=sys.stderr,
        )
        if os.environ.get("TZP_DEBUG_QT", "") == "1":
            os.environ.setdefault("QT_DEBUG_PLUGINS", "1")
        return
    os.environ.setdefault("QT_QPA_PLATFORM_PLUGIN_PATH", str(plugin_path))
    os.environ.setdefault("QT_PLUGIN_PATH", str(plugin_path))
    if (
        os.environ.get("QT_ACCESSIBILITY", "") == ""
        and os.environ.get("TZP_ALLOW_A11Y", "") != "1"
    ):
        os.environ["QT_ACCESSIBILITY"] = "0"
    if sys.platform.startswith("linux") and "QT_IM_MODULE" not in os.environ:
        os.environ["QT_IM_MODULE"] = "compose"
        if os.environ.get("TZP_DEBUG_QT", "") == "1":
            print("TranslationZed: QT_IM_MODULE=compose", file=sys.stderr)
    wayland_plugins = list(plugin_path.glob("platforms/libqwayland*.so*"))
    if not wayland_plugins and "QT_QPA_PLATFORM" not in os.environ:
        os.environ["QT_QPA_PLATFORM"] = "xcb"
        print(
            "TranslationZed: wayland plugin not bundled; forcing QT_QPA_PLATFORM=xcb",
            file=sys.stderr,
        )
    if os.environ.get("TZP_DEBUG_QT", "") == "1":
        os.environ.setdefault("QT_DEBUG_PLUGINS", "1")
        print(f"TranslationZed: QT_PLUGIN_PATH={plugin_path}", file=sys.stderr)
        print(
            "TranslationZed: QT_QPA_PLATFORM="
            f"{os.environ.get('QT_QPA_PLATFORM', '<auto>')}",
            file=sys.stderr,
        )
        print(
            "TranslationZed: QT_ACCESSIBILITY="
            f"{os.environ.get('QT_ACCESSIBILITY', '<auto>')}",
            file=sys.stderr,
        )


def main(argv: list[str] | None = None) -> None:
    _configure_qt_env()
    from translationzed_py.gui import launch

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
        version=f"%(prog)s {__version__}",
    )

    args = parser.parse_args(argv)
    launch(str(args.project) if args.project else None)


if __name__ == "__main__":
    main()
