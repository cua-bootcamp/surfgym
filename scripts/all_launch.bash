#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/setting.sh"

NOHUP_LOG_DIR="$ROOT_DIR/logs/nohup"
LAUNCH_TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
PID_FILE="$NOHUP_LOG_DIR/all_launch_${LAUNCH_TIMESTAMP}.pids"

mkdir -p "$NOHUP_LOG_DIR"
: > "$PID_FILE"

launch_with_nohup() {
    local name="$1"
    local script_path="$2"
    local log_file="$NOHUP_LOG_DIR/${name}_${LAUNCH_TIMESTAMP}.log"

    printf 'Launching %s with nohup\n' "$name"
    printf '  script: %s\n' "$script_path"
    printf '  log:    %s\n' "$log_file"

    nohup bash "$script_path" > "$log_file" 2>&1 &

    local pid="$!"
    printf '  pid:    %s\n\n' "$pid"
    printf '%s %s %s\n' "$name" "$pid" "$log_file" >> "$PID_FILE"
}

launch_with_nohup "gateway" "$SCRIPT_DIR/gateway_launch.bash"
launch_with_nohup "wavepool" "$SCRIPT_DIR/wavepool_launch.bash"
launch_with_nohup "fixture" "$SCRIPT_DIR/fixture_launch.bash"

printf 'Launch commands submitted.\n'
printf 'PID file: %s\n' "$PID_FILE"
printf 'Health check: bash %s/health_check.bash\n' "$SCRIPT_DIR"
