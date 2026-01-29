#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

source "$SCRIPT_DIR/_common.sh"
ensure_venv

"$VENV_PY" -m pip install --upgrade pyinstaller

sep=":"
case "${OSTYPE:-}" in
  msys*|cygwin*|win32*) sep=";" ;;
esac

"$VENV_PY" -m PyInstaller \
  --clean \
  --noconsole \
  --name TranslationZed-Py \
  --add-data "LICENSE${sep}LICENSE" \
  --add-data "README.md${sep}README.md" \
  --collect-all PySide6 \
  translationzed_py/__main__.py
