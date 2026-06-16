#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

SEED_DIR_PATH="${1:-$ROOT_DIR/packages/surfgym-task/src/surfgym_task/data/spreadsheet}"
GRANULARITY="${GRANULARITY:-COARSE}"
ACCUMULATION="${ACCUMULATION:-CUMULATIVE}"
WEBSITE="${WEBSITE:-http://localhost:3000/spreadsheet}"

cd "$ROOT_DIR"

printf 'Running surfgym_task.main\n'
printf '  seed dir: %s\n' "$SEED_DIR_PATH"
printf '  granularity: %s\n' "$GRANULARITY"
printf '  accumulation: %s\n' "$ACCUMULATION"
printf '  website: %s\n\n' "$WEBSITE"

exec uv run python -m surfgym_task.main \
  --seed-dir-path "$SEED_DIR_PATH" \
  --granularity "$GRANULARITY" \
  --accumulation "$ACCUMULATION" \
  --website "$WEBSITE"