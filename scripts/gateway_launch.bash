#!/usr/bin/env bash
set -euo pipefail

source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/setting.sh"

cd "$ROOT_DIR"

printf 'Launching gateway: %s -m surfgym_runtime.gateway.launch %s\n\n' \
    "$RUNTIME_PYTHON" \
    "$SURFGYM_CONFIG"

exec env PYTHONUNBUFFERED=1 "$RUNTIME_PYTHON" -m surfgym_runtime.gateway.launch "$SURFGYM_CONFIG"
