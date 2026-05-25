#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

TASK_PATH="${1:-$ROOT_DIR/packages/surfgym-task/src/surfgym_task/data/seed/spreadsheet/out/augmented.jsonc}"
GATEWAY_URL="${GATEWAY_URL:-http://127.0.0.1:18000}"

cd "$ROOT_DIR"

printf 'Generating snapshots\n'
printf '  gateway: %s\n' "$GATEWAY_URL"
printf '  task path: %s\n' "$TASK_PATH"
printf '  max parallel: %s\n\n' "16"

exec uv run python -m snapshots.generate.run \
  --gateway-url "$GATEWAY_URL" \
  --task-path "$TASK_PATH" \
  --max-parallel 16