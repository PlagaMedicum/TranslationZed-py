#!/usr/bin/env bash
set -euo pipefail

bundle="${1:-}"
if [[ -z "$bundle" ]]; then
  echo "Usage: prune_bundle.sh <bundle-dir>" >&2
  exit 1
fi

if [[ ! -d "$bundle" && -d "${bundle}.app" ]]; then
  bundle="${bundle}.app"
fi

if [[ ! -d "$bundle" ]]; then
  echo "Bundle not found: $bundle" >&2
  exit 1
fi

pyside_dir="$(find "$bundle" -type d -name PySide6 -prune -print -quit || true)"
if [[ -z "${pyside_dir:-}" ]]; then
  echo "PySide6 not found under $bundle; skipping prune." >&2
  exit 0
fi

qt_dir="$pyside_dir/Qt"
if [[ -d "$qt_dir" ]]; then
  rm -rf "$qt_dir/qml" "$qt_dir/translations"
  plugins="$qt_dir/plugins"
  if [[ -d "$plugins" ]]; then
    for name in \
      assetimporters \
      bearer \
      egldeviceintegrations \
      gamepads \
      geometryloaders \
      geoservices \
      mediaservice \
      multimedia \
      networkinformation \
      position \
      renderers \
      renderplugins \
      sceneparsers \
      sensorgestures \
      sensors \
      sqldrivers \
      texttospeech \
      tls \
      webview \
      windowdecorations \
      designer \
      qmltooling; do
      rm -rf "$plugins/$name"
    done
  fi
fi

find "$bundle" -type d \( -name "*.dist-info" -o -name "*.egg-info" \) -prune -exec rm -rf {} + || true
find "$bundle" -type d -name "__pycache__" -prune -exec rm -rf {} + || true
