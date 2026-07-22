#!/usr/bin/env bash
set -euo pipefail

source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/setting.sh"

TASK_PATH="${1:-$TASK_FILE_PATH}"
GATEWAY_URL="${2:-http://127.0.0.1:18000}"
MAX_PARALLEL="${3:-3}"

cd "$ROOT_DIR"

printf 'Generating snapshots\n'
printf '  gateway: %s\n' "$GATEWAY_URL"
printf '  task path: %s\n' "$TASK_PATH"
printf '  max parallel: %s\n' "$MAX_PARALLEL"

exec python -m snapshots.generate.run \
  --gateway-url "$GATEWAY_URL" \
  --task-path "$TASK_PATH" \
  --max-parallel "$MAX_PARALLEL"
