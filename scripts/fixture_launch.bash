#!/usr/bin/env bash
set -euo pipefail

source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/setting.sh"

cd "$FIXTURE_DIR/website" || exit 1

printf 'Executing "pnpm run preview -- --host 127.0.0.1 --port %s --strictPort"\n\n' \
    "$FIXTURE_WEBSITE_PORT"

exec pnpm run preview -- --host 127.0.0.1 --port "$FIXTURE_WEBSITE_PORT" --strictPort
