#!/usr/bin/env bash
set -euo pipefail

source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/setting.sh"

cd "$ROOT_DIR"

printf 'Launching omnibox: python -m src.omnibox.deploy %s\n\n' "$WEBGYM_RL_CONFIG"

exec env PYTHONUNBUFFERED=1 python -m src.omnibox.deploy "$WEBGYM_RL_CONFIG"
