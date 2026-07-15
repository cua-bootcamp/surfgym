#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

TARGET_DIR="${1:-$ROOT_DIR/packages/surfgym-task/src/surfgym_task/data/smoke_fixture}"
GRANULARITY="${2:-COARSE}"

cd "$ROOT_DIR"

printf 'Running surfgym_task.main\n'
printf '  seed dir: %s\n' "$TARGET_DIR"
printf '  granularity: %s\n' "$GRANULARITY"

exec python -m surfgym_task.main \
  --target-dir "$TARGET_DIR" \
  --granularity "$GRANULARITY"