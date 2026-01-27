#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

rm -rf "$ROOT_DIR/build" "$ROOT_DIR/dist" "$ROOT_DIR"/*.egg-info
find "$ROOT_DIR" -type d \( -name "__pycache__" -o -name ".mypy_cache" -o -name ".ruff_cache" -o -name ".pytest_cache" \) -prune -exec rm -rf {} +
