#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"$SCRIPT_DIR/fmt_check.sh"
"$SCRIPT_DIR/lint_check.sh"
"$SCRIPT_DIR/typecheck.sh"
"$SCRIPT_DIR/test.sh"
