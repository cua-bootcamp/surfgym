#!/usr/bin/env bash
set -euo pipefail

source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/setting.sh"

if [[ -z "${SURFGYM_FIXTURE_CADDYFILE:-}" ]]; then
    cd "$ROOT_DIR/packages/surfgym-fixture/src/surfgym_fixture"
    printf 'No generated static-host config supplied; serving the legacy fixture root on %s.\n\n' \
        "$FIXTURE_MAIN_PORT"
    exec env MAIN_PORT="$FIXTURE_MAIN_PORT" pnpm run serve
fi

[[ -f "$SURFGYM_FIXTURE_CADDYFILE" ]] || {
    printf 'Generated fixture Caddyfile is missing: %s\n' "$SURFGYM_FIXTURE_CADDYFILE" >&2
    exit 2
}
printf 'Executing Caddy with generated local static host config: %s\n\n' \
    "$SURFGYM_FIXTURE_CADDYFILE"

exec caddy run --config "$SURFGYM_FIXTURE_CADDYFILE" --adapter caddyfile
