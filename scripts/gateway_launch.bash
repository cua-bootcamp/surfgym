#!/usr/bin/env bash
set -euo pipefail

source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/setting.sh"

cd "$ROOT_DIR"

printf 'Launching gateway: python -m surfgym_runtime.gateway.launch %s\n\n' "$SURFGYM_CONFIG"

exec env PYTHONUNBUFFERED=1 python -m surfgym_runtime.gateway.launch "$SURFGYM_CONFIG"
