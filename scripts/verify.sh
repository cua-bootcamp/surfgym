#!/usr/bin/env bash
set -euo pipefail

export PATH="${BASH%/*}:$PATH"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VERIFY_PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/Scripts/python.exe}"
VERIFY_RUN_ID="${VERIFY_RUN_ID:-$(date +%Y%m%dt%H%M%S)-$$}"
VERIFY_OUTPUT_ROOT="${VERIFY_OUTPUT_ROOT:-$ROOT_DIR/output/verification/verify}"
VERIFY_BASETEMP="${VERIFY_BASETEMP:-$ROOT_DIR/.test-tmp/verify/$VERIFY_RUN_ID}"
RUN_ROOT="$VERIFY_OUTPUT_ROOT/$VERIFY_RUN_ID"
JUNIT_DIR="$RUN_ROOT/junit"
LOG_DIR="$RUN_ROOT/logs"

cd "$ROOT_DIR"
unset PYTHON_BIN
export PYTHONPATH="$ROOT_DIR/packages/surfgym-contracts/src:$ROOT_DIR/packages/surfgym-fixture/src:$ROOT_DIR/packages/surfgym-runtime/src:$ROOT_DIR/packages/surfgym-task/src${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p "$JUNIT_DIR" "$LOG_DIR" "$VERIFY_BASETEMP"

run_suite() {
    local name="$1"
    local target="$2"
    "$VERIFY_PYTHON_BIN" -m pytest -p no:cacheprovider \
        --basetemp="$VERIFY_BASETEMP/$name" \
        --junitxml="$JUNIT_DIR/$name.xml" \
        --log-file="$LOG_DIR/$name.log" \
        "$target" -q 2>&1 | tee -a "$LOG_DIR/console.log"
}

run_suite contracts "$ROOT_DIR/packages/surfgym-contracts/tests"
run_suite fixture "$ROOT_DIR/packages/surfgym-fixture/tests"
run_suite runtime "$ROOT_DIR/packages/surfgym-runtime/tests"
run_suite task "$ROOT_DIR/packages/surfgym-task/tests"
run_suite snapshots-chrome-cua "$ROOT_DIR/snapshots/generate/test_chrome_cua.py"
