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
readonly SURFGYM_CONFIG="$ROOT_DIR/scripts/config.json"
readonly FIXTURE_DIR="$ROOT_DIR/tests/fixtures"

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

readonly FIXTURE_MAIN_PORT=3000
readonly FIXTURE_PROZILLA_PORT=3100
