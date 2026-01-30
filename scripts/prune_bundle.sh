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

os_name="$(uname -s)"
skip_qt_prune=false
if [[ "$os_name" == "Linux" ]]; then
  # Linux bundles have been unstable after aggressive pruning.
  # Keep Qt files intact here to prioritize a working executable.
  skip_qt_prune=true
fi
pyside_dir="$(find "$bundle" -type d -name PySide6 -prune -print -quit || true)"
if [[ -z "${pyside_dir:-}" ]]; then
  echo "PySide6 not found under $bundle; skipping prune." >&2
  exit 0
fi

qt_dir="$pyside_dir/Qt"
if [[ -d "$qt_dir" && "$skip_qt_prune" == "false" ]]; then
  rm -rf "$qt_dir/qml" "$qt_dir/translations"
  plugins="$qt_dir/plugins"
  if [[ -d "$plugins" ]]; then
    platforms="$plugins/platforms"
    if [[ -d "$platforms" ]]; then
      keep_prefixes=()
      case "$os_name" in
        Darwin) keep_prefixes=("libqcocoa") ;;
        Linux) keep_prefixes=("libqxcb" "libqwayland-egl" "libqwayland-generic") ;;
      esac
      if (( ${#keep_prefixes[@]} > 0 )); then
        for entry in "$platforms"/*; do
          base="$(basename "$entry")"
          keep=false
          for prefix in "${keep_prefixes[@]}"; do
            if [[ "$base" == "$prefix"* ]]; then
              keep=true
              break
            fi
          done
          if [[ "$keep" == "false" ]]; then
            rm -rf "$entry"
          fi
        done
      fi
    fi
    imageformats="$plugins/imageformats"
    if [[ -d "$imageformats" ]]; then
      keep_image=()
      case "$os_name" in
        Darwin) keep_image=("libqpng" "libqsvg" "libqjpeg" "libqicns") ;;
        Linux) keep_image=("libqpng" "libqsvg" "libqjpeg") ;;
      esac
      if (( ${#keep_image[@]} > 0 )); then
        for entry in "$imageformats"/*; do
          base="$(basename "$entry")"
          keep=false
          for prefix in "${keep_image[@]}"; do
            if [[ "$base" == "$prefix"* ]]; then
              keep=true
              break
            fi
          done
          if [[ "$keep" == "false" ]]; then
            rm -rf "$entry"
          fi
        done
      fi
    fi

    iconengines="$plugins/iconengines"
    if [[ -d "$iconengines" ]]; then
      for entry in "$iconengines"/*; do
        base="$(basename "$entry")"
        if [[ "$base" != libqsvgicon* ]]; then
          rm -rf "$entry"
        fi
      done
    fi
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

  if [[ "$os_name" != "Linux" ]]; then
    for lib in \
      Qt63DAnimation \
      Qt63DCore \
      Qt63DExtras \
      Qt63DInput \
      Qt63DLogic \
      Qt63DRender \
      Qt6Charts \
      Qt6DataVisualization \
      Qt6Multimedia \
      Qt6MultimediaWidgets \
      Qt6NetworkAuth \
      Qt6Pdf \
      Qt6PdfWidgets \
      Qt6Positioning \
      Qt6Quick \
      Qt6Quick3D \
      Qt6QuickControls2 \
      Qt6QuickWidgets \
      Qt6Qml \
      Qt6Sensors \
      Qt6SerialPort \
      Qt6Sql \
      Qt6Test \
      Qt6TextToSpeech \
      Qt6WebChannel \
      Qt6WebEngineCore \
      Qt6WebEngineWidgets \
      Qt6WebEngine \
      Qt6WebSockets; do
      rm -f "$qt_dir/lib/lib${lib}.so"* "$qt_dir/lib/lib${lib}.dylib"* 2>/dev/null || true
      rm -rf "$qt_dir/lib/${lib}.framework" 2>/dev/null || true
      rm -f "$qt_dir/bin/${lib}.dll" 2>/dev/null || true
    done
  fi
fi

find "$bundle" -type d \( -name "*.dist-info" -o -name "*.egg-info" \) -prune -exec rm -rf {} + || true
find "$bundle" -type d -name "__pycache__" -prune -exec rm -rf {} + || true

strip_tool="$(command -v strip || true)"
if [[ -n "$strip_tool" ]]; then
  if [[ "$os_name" == "Darwin" ]]; then
    find "$bundle" -type f \( -name "*.dylib" -o -name "*.so" -o -name "*.so.*" \) -print0 \
      | xargs -0 -n1 strip -x 2>/dev/null || true
  elif [[ "${TZP_EXTRA_STRIP:-}" == "1" ]]; then
    find "$bundle" -type f \( -name "*.so" -o -name "*.so.*" \) -print0 \
      | xargs -0 -n1 strip --strip-unneeded 2>/dev/null || true
  fi
fi
