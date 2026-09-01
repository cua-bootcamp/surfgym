#!/usr/bin/env bash
set -euo pipefail

source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/setting.sh"

: "${SURFGYM_FIXTURE_CADDYFILE:?SURFGYM_FIXTURE_CADDYFILE is required}"
[[ -f "$SURFGYM_FIXTURE_CADDYFILE" ]] || {
    printf 'Generated fixture Caddyfile is missing: %s\n' "$SURFGYM_FIXTURE_CADDYFILE" >&2
    exit 2
}

printf 'Executing Caddy with generated local static host config: %s\n\n' \
    "$SURFGYM_FIXTURE_CADDYFILE"

exec caddy run --config "$SURFGYM_FIXTURE_CADDYFILE" --adapter caddyfile
