#!/usr/bin/env bash
set -euo pipefail

source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/setting.sh"

cd "$ROOT_DIR"
    
printf 'Executing "python -m http.server %s --directory %s"\n\n' \
    "$FIXTURE_WEBSITE_PORT" \
    "$FIXTURE_DIR/website"

exec python -m http.server "$FIXTURE_WEBSITE_PORT" --directory "$FIXTURE_DIR/website"