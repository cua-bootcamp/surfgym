#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

AUGMENTATION_RUN="$ROOT_DIR/scripts/augmentation_run.bash"
DATA_DIR="$ROOT_DIR/packages/surfgym-task/src/surfgym_task/data"
SPREADSHEET_DIR="$DATA_DIR/spreadsheet"
WORD_DIR="$DATA_DIR/word"
OUT_DIR="$DATA_DIR/out"
INTEGRATED_JSONL="$OUT_DIR/integrated.jsonl"

run_augmentation() {
  local name="$1"
  local seed_dir="$2"
  local website="$3"

  printf 'Augmenting %s tasks\n' "$name"
  WEBSITE="$website" bash "$AUGMENTATION_RUN" "$seed_dir"
}

run_augmentation "spreadsheet" "$SPREADSHEET_DIR" "http://localhost:3000/spreadsheet"
run_augmentation "word" "$WORD_DIR" "http://localhost:3000/word"

mkdir -p "$OUT_DIR"

cat \
  "$SPREADSHEET_DIR/out/augmented.jsonl" \
  "$WORD_DIR/out/augmented.jsonl" \
  > "$INTEGRATED_JSONL"

printf '\nWrote integrated tasks: %s\n' "$INTEGRATED_JSONL"
wc -l "$INTEGRATED_JSONL"
