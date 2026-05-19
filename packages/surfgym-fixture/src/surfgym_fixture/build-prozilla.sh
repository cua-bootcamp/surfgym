#!/usr/bin/env bash
set -euo pipefail

PROZILLA_DIR="prozilla-os"
DIST_DIR="$PROZILLA_DIR/demo/dist"

pnpm --dir "$PROZILLA_DIR" install --frozen-lockfile
pnpm --dir "$PROZILLA_DIR" run packages:build
pnpm --dir "$PROZILLA_DIR" run demo:build

find "$DIST_DIR/assets" -type f \( -name '*.js' -o -name '*.css' \) -exec gzip -kf -9 {} \;

if command -v zstd >/dev/null; then
  find "$DIST_DIR/assets" -type f \( -name '*.js' -o -name '*.css' \) -exec zstd -k -f -19 {} \;
fi

find "$DIST_DIR" -type f -print0 | xargs -0 cat > /dev/null
