#!/usr/bin/env bash
set -euo pipefail

source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/setting.sh"

TRAVELHUB_DIR="$ROOT_DIR/packages/surfgym-travel-ad-hub/src/surfgym_travel_ad_hub"
BUILD_ID="$TRAVELHUB_DIR/.next/BUILD_ID"
NEXT_BIN="$TRAVELHUB_DIR/node_modules/next/dist/bin/next"
NODE_BIN="${NODE_BIN:-node}"

[[ -f "$BUILD_ID" ]] || {
    printf 'TravelHub production build is missing: %s\n' "$BUILD_ID" >&2
    printf 'Build it with npm ci and npm run build in %s\n' "$TRAVELHUB_DIR" >&2
    exit 2
}
[[ -f "$NEXT_BIN" ]] || {
    printf 'TravelHub Next.js CLI is missing: %s\n' "$NEXT_BIN" >&2
    exit 2
}
command -v "$NODE_BIN" >/dev/null 2>&1 || {
    printf 'TravelHub launcher cannot find Node.js: %s\n' "$NODE_BIN" >&2
    exit 2
}

cd -- "$TRAVELHUB_DIR"
printf 'Executing TravelHub on fixed port %s.\n\n' "$TRAVELHUB_PORT"
exec "$NODE_BIN" "$NEXT_BIN" start -p "$TRAVELHUB_PORT"
