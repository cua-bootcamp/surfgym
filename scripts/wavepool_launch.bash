#!/usr/bin/env bash
set -euo pipefail

source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/setting.sh"

cd "$ROOT_DIR"

printf 'Launching wavepool: python -m src.wavepool.deploy %s\n\n' "$SURFGYM_CONFIG"

exec env PYTHONUNBUFFERED=1 python -m src.wavepool.deploy "$SURFGYM_CONFIG"
