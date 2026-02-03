#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIXTURE_ROOT="$ROOT_DIR/tests/fixtures"
# Preserve committed fixture caches to keep make verify non-destructive.

while IFS= read -r cache_dir; do
  case "$cache_dir" in
    "$FIXTURE_ROOT"/*)
      continue
      ;;
  esac
  rm -rf "$cache_dir"
done < <(find "$ROOT_DIR" -type d -name ".tzp-cache" -prune)
