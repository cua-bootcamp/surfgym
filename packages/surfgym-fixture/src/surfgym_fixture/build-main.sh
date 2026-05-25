#!/usr/bin/env bash
set -euo pipefail

pnpm run build:vite

find dist/assets -type f \( -name '*.js' -o -name '*.css' \) -exec gzip -kf -9 {} \;

if command -v zstd >/dev/null; then
  find dist/assets -type f \( -name '*.js' -o -name '*.css' \) -exec zstd -k -f -19 {} \;
else
  echo "zstd not found; skipping .zst precompression"
fi

find dist -type f -print0 | xargs -0 cat > /dev/null
