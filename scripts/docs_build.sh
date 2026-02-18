#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
ensure_venv

SITE_DIR="$ROOT_DIR/${ARTIFACTS:-artifacts}/docs/site"
mkdir -p "$(dirname "$SITE_DIR")"

"$VENV_PY" -m mkdocs build --strict --site-dir "$SITE_DIR"
