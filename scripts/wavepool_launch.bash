#!/usr/bin/env bash
set -euo pipefail

source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/setting.sh"

cd "$ROOT_DIR"

printf 'Launching wavepool: %s -m surfgym_runtime.wavepool.launch %s\n\n' \
    "$RUNTIME_PYTHON" \
    "$SURFGYM_CONFIG"

exec env PYTHONUNBUFFERED=1 "$RUNTIME_PYTHON" -m surfgym_runtime.wavepool.launch "$SURFGYM_CONFIG"
