#!/usr/bin/env bash

surfgym_root_dir() {
    local root
    root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

    if [[ "${OSTYPE:-}" == msys* || "${OSTYPE:-}" == cygwin* ]]; then
        root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -W)"
    fi

    printf '%s\n' "$root"
}

readonly ROOT_DIR="$(surfgym_root_dir)"
readonly TEST_DIR="$ROOT_DIR/tests"
readonly FIXTURE_DIR="$TEST_DIR/fixtures"

# =============================================================================
# User-defined settings
# Modify only the values below for testing.
# 
# * Use the appropriate SURFGYM_CONFIG for the target test
# * Make sure to set WITH_FIXTURE_WEBSITE=true when using fixture websites
# =============================================================================

readonly SURFGYM_CONFIG="$FIXTURE_DIR/config/config-single.json"
readonly FIXTURE_MAIN_PORT=3000
readonly FIXTURE_PROZILLA_PORT=3100

# =============================================================================

json_get() {
    python - "$SURFGYM_CONFIG" "$1" <<'PY'
import json
import sys

path = sys.argv[1]
query = sys.argv[2]

with open(path, encoding="utf-8") as fh:
    value = json.load(fh)

for part in query.strip(".").split("."):
    value = value[part]

if isinstance(value, bool):
    print(str(value).lower())
else:
    print(value)
PY
}

readonly GATEWAY_HOST="$(json_get '.gateway.host')"
readonly GATEWAY_PORT="$(json_get '.gateway.port')"

readonly WAVEPOOL_HOST="$(json_get '.wavepool.host')"
readonly WAVEPOOL_MASTER_PORT="$(json_get '.wavepool.master_port')"
readonly WAVEPOOL_INSTANCE_START_PORT="$(json_get '.wavepool.instance_start_port')"
readonly WAVEPOOL_INSTANCE="$(json_get '.wavepool.instances')"
readonly WAVEPOOL_MASTER_WORKERS="$(json_get '.wavepool.master_workers')"