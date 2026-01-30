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

UPX_ARGS=()
if command -v upx >/dev/null 2>&1; then
  UPX_ARGS+=(--upx-dir "$(dirname "$(command -v upx)")")
fi

EXCLUDES=(
  PySide6.Qt3DAnimation
  PySide6.Qt3DCore
  PySide6.Qt3DExtras
  PySide6.Qt3DInput
  PySide6.Qt3DLogic
  PySide6.Qt3DRender
  PySide6.QtCharts
  PySide6.QtDataVisualization
  PySide6.QtMultimedia
  PySide6.QtMultimediaWidgets
  PySide6.QtNetworkAuth
  PySide6.QtPdf
  PySide6.QtPdfWidgets
  PySide6.QtPositioning
  PySide6.QtQuick
  PySide6.QtQuick3D
  PySide6.QtQuickControls2
  PySide6.QtQuickWidgets
  PySide6.QtQml
  PySide6.QtSensors
  PySide6.QtSerialPort
  PySide6.QtSql
  PySide6.QtTest
  PySide6.QtWebChannel
  PySide6.QtWebEngine
  PySide6.QtWebEngineCore
  PySide6.QtWebEngineWidgets
  PySide6.QtWebSockets
)

EXCLUDE_ARGS=()
for module in "${EXCLUDES[@]}"; do
  EXCLUDE_ARGS+=(--exclude-module "$module")
done

"$VENV_PY" -m PyInstaller \
  --clean \
  --noconsole \
  --name TranslationZed-Py \
  --add-data "LICENSE${sep}." \
  --add-data "README.md${sep}." \
  --strip \
  "${UPX_ARGS[@]}" \
  "${EXCLUDE_ARGS[@]}" \
  translationzed_py/__main__.py
