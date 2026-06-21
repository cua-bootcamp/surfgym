#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/setting.sh"

NOHUP_LOG_DIR="$ROOT_DIR/logs/nohup"
GRACE_SECONDS="${SURFGYM_STOP_GRACE_SECONDS:-5}"
PID_FILE="${1:-}"

if [[ -z "$PID_FILE" ]]; then
    PID_FILE="$(ls -t "$NOHUP_LOG_DIR"/all_launch_*.pids 2>/dev/null | head -1 || true)"
fi

is_live_pid() {
    local pid="$1"
    [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null
}

print_pids() {
    local pid
    for pid in "$@"; do
        if is_live_pid "$pid"; then
            printf '%s\n' "$pid"
        fi
    done
}

pid_file_pids() {
    if [[ -n "$PID_FILE" && -f "$PID_FILE" ]]; then
        awk '{print $2}' "$PID_FILE"
    fi
}

matching_launch_pids() {
    pgrep -f "surfgym_runtime.gateway.launch $SURFGYM_CONFIG" || true
    pgrep -f "surfgym_runtime.wavepool.launch $SURFGYM_CONFIG" || true
}

port_pids() {
    command -v lsof >/dev/null 2>&1 || return 0

    lsof -ti "tcp:$GATEWAY_PORT" 2>/dev/null || true
    lsof -ti "tcp:$WAVEPOOL_MASTER_PORT" 2>/dev/null || true
    lsof -ti "tcp:$FIXTURE_MAIN_PORT" 2>/dev/null || true
    lsof -ti "tcp:$FIXTURE_PROZILLA_PORT" 2>/dev/null || true

    local offset port
    for ((offset = 0; offset < WAVEPOOL_INSTANCE; offset++)); do
        port=$((WAVEPOOL_INSTANCE_START_PORT + offset))
        lsof -ti "tcp:$port" 2>/dev/null || true
    done
}

dedupe_live_pids() {
    awk '!seen[$0]++' | while read -r pid; do
        if is_live_pid "$pid"; then
            printf '%s\n' "$pid"
        fi
    done
}

wait_for_exit() {
    local deadline pid
    deadline=$((SECONDS + GRACE_SECONDS))

    while ((SECONDS < deadline)); do
        local alive=0
        for pid in "$@"; do
            if is_live_pid "$pid"; then
                alive=1
                break
            fi
        done

        if ((alive == 0)); then
            return 0
        fi

        sleep 0.2
    done

    return 1
}

stop_pids() {
    local signal="$1"
    shift

    local pids=("$@")
    if ((${#pids[@]} == 0)); then
        return 0
    fi

    printf 'Sending %s to: %s\n' "$signal" "${pids[*]}"
    kill "-$signal" "${pids[@]}" 2>/dev/null || true
}

printf 'Stopping surfgym servers\n'
if [[ -n "$PID_FILE" ]]; then
    printf 'PID file: %s\n' "$PID_FILE"
else
    printf 'PID file: none found\n'
fi

mapfile -t primary_pids < <(
    {
        pid_file_pids
        matching_launch_pids
    } | dedupe_live_pids
)

if ((${#primary_pids[@]} > 0)); then
    stop_pids TERM "${primary_pids[@]}"
    wait_for_exit "${primary_pids[@]}" || true
fi

mapfile -t remaining_pids < <(port_pids | dedupe_live_pids)

if ((${#remaining_pids[@]} > 0)); then
    stop_pids TERM "${remaining_pids[@]}"
    wait_for_exit "${remaining_pids[@]}" || true
fi

mapfile -t remaining_pids < <(
    {
        matching_launch_pids
        port_pids
    } | dedupe_live_pids
)

if ((${#remaining_pids[@]} > 0)); then
    stop_pids KILL "${remaining_pids[@]}"
    wait_for_exit "${remaining_pids[@]}" || true
fi

mapfile -t remaining_pids < <(
    {
        matching_launch_pids
        port_pids
    } | dedupe_live_pids
)

if ((${#remaining_pids[@]} > 0)); then
    printf 'Warning: some surfgym processes are still alive: %s\n' "${remaining_pids[*]}" >&2
    exit 1
fi

printf 'surfgym servers stopped\n'
