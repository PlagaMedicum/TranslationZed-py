#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
ensure_venv

"$ROOT_DIR/$VENV/bin/pre-commit" install
