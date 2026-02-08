#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIXTURES_DIR="$ROOT_DIR/tests/fixtures"
# Non-destructive by design: only fixture configs are reset.

if [ -d "$FIXTURES_DIR" ]; then
  find "$FIXTURES_DIR" -type d \( -path "*/.tzp/config" -o -name ".tzp-config" \) -prune -exec rm -rf {} +
fi
