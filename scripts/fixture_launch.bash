#!/usr/bin/env bash
set -euo pipefail

source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/setting.sh"

cd "$ROOT_DIR/packages/surfgym-fixture/src/surfgym_fixture"

printf 'Executing "MAIN_PORT=%s PROZILLA_PORT=%s pnpm run serve"\n\n' \
    "$FIXTURE_MAIN_PORT" \
    "$FIXTURE_PROZILLA_PORT"

exec env MAIN_PORT="$FIXTURE_MAIN_PORT" PROZILLA_PORT="$FIXTURE_PROZILLA_PORT" pnpm run serve
