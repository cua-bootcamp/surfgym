#!/usr/bin/env bash
set -euo pipefail

source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/setting.sh"

cd "$ROOT_DIR"

printf 'Launching wavepool: uv run python -m surfgym_runtime.wavepool.launch %s\n\n' "$SURFGYM_CONFIG"

exec env PYTHONUNBUFFERED=1 uv run python -m surfgym_runtime.wavepool.launch "$SURFGYM_CONFIG"