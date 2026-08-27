#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/setting.sh"
source "$SCRIPT_DIR/process_identity.sh"

NOHUP_LOG_DIR="$ROOT_DIR/logs/nohup"
LAUNCH_TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
PID_FILE="${SURFGYM_PID_FILE:-$NOHUP_LOG_DIR/all_launch_${LAUNCH_TIMESTAMP}.pids}"
LAUNCH_COMPLETE=0

mkdir -p "$NOHUP_LOG_DIR"
mkdir -p "$(dirname -- "$PID_FILE")"
if [[ -s "$PID_FILE" ]]; then
    printf 'Error: refusing to overwrite an existing PID record: %s\n' "$PID_FILE" >&2
    exit 2
fi
: > "$PID_FILE"

rollback_partial_launch() {
    local status="$?"
    if ((LAUNCH_COMPLETE == 0)) && [[ -s "$PID_FILE" ]]; then
        printf 'Launch failed; stopping only processes recorded in %s\n' "$PID_FILE" >&2
        bash "$SCRIPT_DIR/all_stop.bash" "$PID_FILE" || true
    fi
    exit "$status"
}

trap rollback_partial_launch EXIT

launch_with_nohup() {
    local name="$1"
    local script_path="$2"
    local log_file="$NOHUP_LOG_DIR/${name}_${LAUNCH_TIMESTAMP}.log"

    printf 'Launching %s with nohup\n' "$name"
    printf '  script: %s\n' "$script_path"
    printf '  log:    %s\n' "$log_file"

    nohup bash "$script_path" > "$log_file" 2>&1 &

    local pid="$!"
    local identity
    if ! identity="$(capture_process_identity_after_exec "$pid")"; then
        printf 'Error: could not capture process identity for %s (PID %s).\n' "$name" "$pid" >&2
        kill -TERM "$pid" 2>/dev/null || true
        return 1
    fi
    printf '  pid:    %s\n\n' "$pid"
    printf '%s %s %s %s\n' "$name" "$pid" "$identity" "$log_file" >> "$PID_FILE"
}

launch_with_nohup "gateway" "$SCRIPT_DIR/gateway_launch.bash"
launch_with_nohup "wavepool" "$SCRIPT_DIR/wavepool_launch.bash"
launch_with_nohup "fixture" "$SCRIPT_DIR/fixture_launch.bash"

LAUNCH_COMPLETE=1
trap - EXIT
printf 'Launch commands submitted.\n'
printf 'PID file: %s\n' "$PID_FILE"
printf 'Health check: bash %s/health_check.bash\n' "$SCRIPT_DIR"
