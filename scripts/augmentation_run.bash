#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

SEED_DIR="$ROOT_DIR/packages/surfgym-task/src/surfgym_task/data/spreadsheet"
GRANULARITY="COARSE"
PROFILE="SNAPSHOT"

cd "$ROOT_DIR"

COMMAND=(
  python -m surfgym_task.main
  "$SEED_DIR"
  -g "$GRANULARITY"
  -p "$PROFILE"
)

printf 'Executing:'
printf ' %q' "${COMMAND[@]}"
printf '\n'

exec "${COMMAND[@]}"