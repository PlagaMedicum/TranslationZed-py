#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

source "$SCRIPT_DIR/_common.sh"
ensure_venv
cd "$ROOT_DIR"

if ! "$VENV_PY" -c "import PyInstaller" >/dev/null 2>&1; then
  echo 'PyInstaller is required; install the project with the "packaging" extra first.' >&2
  exit 2
fi

sep=":"
case "${OSTYPE:-}" in
  msys*|cygwin*|win32*) sep=";" ;;
esac

UPX_ARGS=()
if command -v upx >/dev/null 2>&1; then
  UPX_ARGS+=(--upx-dir "$(dirname "$(command -v upx)")")
fi

STRIP_ARGS=()
case "${OSTYPE:-}" in
  darwin*) STRIP_ARGS+=(--strip) ;;
  *) if [[ "${TZP_STRIP:-}" == "1" ]]; then STRIP_ARGS+=(--strip); fi ;;
esac

EXCLUDE_ARGS=()
while IFS= read -r module || [ -n "$module" ]; do
  case "$module" in
    ""|\#*) continue ;;
  esac
  EXCLUDE_ARGS+=(--exclude-module "$module")
done < "$ROOT_DIR/packaging/pyinstaller_excludes.txt"

"$VENV_PY" -m PyInstaller \
  --clean \
  --noconsole \
  --name TranslationZed-Py \
  --add-data "LICENSE${sep}." \
  --add-data "README.md${sep}." \
  "${STRIP_ARGS[@]}" \
  "${UPX_ARGS[@]}" \
  "${EXCLUDE_ARGS[@]}" \
  translationzed_py/__main__.py

bash "$SCRIPT_DIR/prune_bundle.sh" "$SCRIPT_DIR/../dist/TranslationZed-Py"
