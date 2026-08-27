#!/usr/bin/env bash

# Print a stable token for one live process. A caller must store this token with
# the PID and compare both before sending a signal. Unsupported platforms fail
# closed instead of treating a live PID as owned.
process_identity_token() {
    local pid="$1"
    local stat rest start_ticks boot_id win_pid start_time

    [[ "$pid" =~ ^[0-9]+$ ]] || return 1
    kill -0 "$pid" 2>/dev/null || return 1

    if [[ -r "/proc/$pid/stat" && -r /proc/sys/kernel/random/boot_id ]]; then
        stat="$(<"/proc/$pid/stat")" || return 1
        rest="${stat##*) }"
        set -- $rest
        start_ticks="${20:-}"
        boot_id="$(</proc/sys/kernel/random/boot_id)" || return 1
        [[ -n "$start_ticks" && -n "$boot_id" ]] || return 1
        printf 'linux:%s:%s\n' "$boot_id" "$start_ticks"
        return 0
    fi

    # MSYS ps exposes the native Windows PID in its fourth column. PowerShell
    # supplies a creation timestamp that does not change during process life.
    if command -v powershell.exe >/dev/null 2>&1; then
        win_pid="$(ps -p "$pid" 2>/dev/null | awk 'NR == 2 {print $4}')"
        [[ "$win_pid" =~ ^[0-9]+$ ]] || return 1
        start_time="$(powershell.exe -NoProfile -NonInteractive -Command \
            "(Get-Process -Id $win_pid -ErrorAction Stop).StartTime.ToUniversalTime().Ticks" \
            2>/dev/null | tr -d '\r\n')" || return 1
        [[ "$start_time" =~ ^[0-9]+$ ]] || return 1
        printf 'windows:%s:%s\n' "$win_pid" "$start_time"
        return 0
    fi

    return 1
}

process_identity_matches() {
    local pid="$1"
    local expected="$2"
    local actual

    actual="$(process_identity_token "$pid")" || return 1
    [[ "$actual" == "$expected" ]]
}

# A freshly spawned MSYS process can briefly change its native Windows PID
# while exec replaces the shell. Require two consecutive identical samples so
# the stored identity describes the final process, not the launch transition.
capture_process_identity() {
    local pid="$1"
    local previous=""
    local current
    local attempt

    for ((attempt = 0; attempt < 20; attempt++)); do
        if current="$(process_identity_token "$pid")"; then
            if [[ -n "$previous" && "$current" == "$previous" ]]; then
                printf '%s\n' "$current"
                return 0
            fi
            previous="$current"
        fi
        kill -0 "$pid" 2>/dev/null || return 1
        sleep 0.05
    done
    return 1
}

# Runtime launchers start as MSYS shell processes and then exec their long-lived
# native process. On Windows, wait until that shell transition is complete
# before recording the native PID identity. Linux retains the normal capture
# path because exec preserves its process identity there.
capture_process_identity_after_exec() {
    local pid="$1"
    local command_path command_name
    local deadline=$((SECONDS + 30))

    if [[ -r "/proc/$pid/stat" && -r /proc/sys/kernel/random/boot_id ]]; then
        capture_process_identity "$pid"
        return
    fi
    command -v powershell.exe >/dev/null 2>&1 || return 1

    while ((SECONDS < deadline)); do
        kill -0 "$pid" 2>/dev/null || return 1
        command_path="$(ps -p "$pid" 2>/dev/null | awk 'NR == 2 {print $8}')"
        command_name="${command_path##*/}"
        command_name="${command_name,,}"
        case "$command_name" in
            bash|bash.exe|sh|sh.exe|env|env.exe|nohup|nohup.exe|"")
                sleep 0.05
                continue
                ;;
        esac
        capture_process_identity "$pid"
        return
    done
    return 1
}
