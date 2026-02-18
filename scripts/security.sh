#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
ensure_venv

ARTIFACTS_DIR="$ROOT_DIR/${ARTIFACTS:-artifacts}/security"
mkdir -p "$ARTIFACTS_DIR"

# Report all findings to artifact output.
"$VENV_PY" -m bandit -q -r translationzed_py tests scripts --exit-zero \
  -f json -o "$ARTIFACTS_DIR/bandit.json"

# Gate on medium/high severity and confidence in production + shipped scripts.
"$VENV_PY" -m bandit -q -r translationzed_py scripts -ll -ii -s B608
