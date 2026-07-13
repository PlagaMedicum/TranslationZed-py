"""Run mutmut with a Python 3.14-safe multiprocessing start-method guard."""

from __future__ import annotations

import importlib
import multiprocessing as mp
import sys


def _install_set_start_method_guard() -> None:
    original = mp.set_start_method

    def _guarded(method: str | None = None, force: bool = False) -> None:
        try:
            original(method, force=force)
        except RuntimeError as exc:
            if "context has already been set" not in str(exc):
                raise

    mp.set_start_method = _guarded  # type: ignore[assignment]


def main(argv: list[str] | None = None) -> int:
    """Execute mutmut's CLI after guarding set_start_method."""
    _install_set_start_method_guard()
    args = list(sys.argv[1:] if argv is None else argv)
    module = importlib.import_module("mutmut.__main__")
    try:
        result = module.cli.main(args=args, prog_name="mutmut")
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        if isinstance(code, int):
            return code
        return 1
    if result is None:
        return 0
    return int(result)


if __name__ == "__main__":
    raise SystemExit(main())
