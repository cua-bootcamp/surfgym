#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
source "$SCRIPT_DIR/process_identity.sh"

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

declare -a owned_pids=()
declare -a owned_tokens=()
identity_failure=0

load_owned_records() {
    local name pid token log_file
    local line_number=0

    [[ -n "$PID_FILE" && -f "$PID_FILE" ]] || return 0
    while read -r name pid token log_file; do
        line_number=$((line_number + 1))
        [[ -n "$name$pid$token$log_file" ]] || continue
        if [[ ! "$pid" =~ ^[0-9]+$ || -z "$token" ]]; then
            printf 'Refusing malformed PID record at %s:%s.\n' "$PID_FILE" "$line_number" >&2
            identity_failure=1
            continue
        fi
        if ! is_live_pid "$pid"; then
            continue
        fi
        if ! process_identity_matches "$pid" "$token"; then
            printf 'Refusing to signal PID %s: its identity does not match %s:%s.\n' \
                "$pid" "$PID_FILE" "$line_number" >&2
            identity_failure=1
            continue
        fi
        owned_pids+=("$pid")
        owned_tokens+=("$token")
    done < "$PID_FILE"
}

collect_remaining_owned() {
    remaining_pids=()
    remaining_tokens=()
    local index pid token
    for ((index = 0; index < ${#owned_pids[@]}; index++)); do
        pid="${owned_pids[$index]}"
        token="${owned_tokens[$index]}"
        if ! is_live_pid "$pid"; then
            continue
        fi
        if ! process_identity_matches "$pid" "$token"; then
            printf 'Refusing to signal reused PID %s after the grace period.\n' "$pid" >&2
            identity_failure=1
            continue
        fi
        remaining_pids+=("$pid")
        remaining_tokens+=("$token")
    done
}

printf 'Stopping surfgym servers\n'
if [[ -n "$PID_FILE" ]]; then
    printf 'PID file: %s\n' "$PID_FILE"
else
    printf 'PID file: none found\n'
fi

load_owned_records

if ((${#owned_pids[@]} > 0)); then
    stop_pids TERM "${owned_pids[@]}"
    wait_for_exit "${owned_pids[@]}" || true
else
    printf 'No live processes recorded in the PID file. Nothing was stopped.\n'
fi

declare -a remaining_pids=()
declare -a remaining_tokens=()
collect_remaining_owned

if ((${#remaining_pids[@]} > 0)); then
    stop_pids KILL "${remaining_pids[@]}"
    wait_for_exit "${remaining_pids[@]}" || true
fi

collect_remaining_owned

if ((${#remaining_pids[@]} > 0)); then
    printf 'Warning: some surfgym processes are still alive: %s\n' "${remaining_pids[*]}" >&2
    exit 1
fi

if ((identity_failure != 0)); then
    printf 'PID file was retained because one or more process identities could not be proven.\n' >&2
    exit 1
fi

if [[ -n "$PID_FILE" && -f "$PID_FILE" ]]; then
    rm -f -- "$PID_FILE"
fi

printf 'surfgym servers stopped\n'
