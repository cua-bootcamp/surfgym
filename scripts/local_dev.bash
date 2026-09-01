#!/usr/bin/env bash
set -euo pipefail

# PowerShell can launch Git Bash with a Windows-only PATH. Restore the Unix
# tools shipped beside Bash before resolving repository paths.
export PATH="${BASH%/*}:$PATH"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
source "$SCRIPT_DIR/process_identity.sh"

usage() {
    cat <<'EOF'
Usage: bash scripts/local_dev.bash <check|up|down> [--config PATH] [--docker-repo PATH]

Commands:
  check  Validate the operator config and both generated runtime configs in memory.
  up     Regenerate both runtime configs, then start Docker and SurfGym components.
  down   Stop recorded local supervisors and the Docker Compose pool.

Path precedence:
  --config PATH       > SURFGYM_OPERATOR_CONFIG > <SurfGym>/config/runtime.toml
  --docker-repo PATH  > SURFGYM_DOCKER_REPO     > sibling surfgym-docker-dev

The local stack reads configuration only at startup. Restart it after changing
config/runtime.toml; hot reload is not supported.
EOF
}

fail() {
    printf 'Error: %s\n' "$*" >&2
    exit 2
}

resolve_python_bin() {
    local override="$1"
    local repository="$2"
    local variable_name="$3"
    local import_probe="$4"
    local candidate=""

    if [[ -n "$override" ]]; then
        candidate="$override"
    else
        for candidate in \
            "$repository/.venv/Scripts/python.exe" \
            "$repository/.venv/bin/python"; do
            [[ -x "$candidate" ]] && break
            candidate=""
        done
        if [[ -z "$candidate" ]]; then
            for candidate in python3 python; do
                if command -v "$candidate" >/dev/null 2>&1; then
                    candidate="$(command -v "$candidate")"
                    break
                fi
            done
        fi
    fi

    [[ -n "$candidate" ]] || fail \
        "No Python interpreter found for $variable_name. Set $variable_name to the repository environment."
    if ! "$candidate" -c "import $import_probe"; then
        fail \
            "$variable_name interpreter cannot import $import_probe: $candidate. Set $variable_name to the repository environment and install the declared dependencies."
    fi
    printf '%s\n' "$candidate"
}

COMMAND="${1:-}"
if [[ -z "$COMMAND" || "$COMMAND" == "-h" || "$COMMAND" == "--help" ]]; then
    usage
    [[ -n "$COMMAND" ]] && exit 0
    exit 2
fi
shift

OPERATOR_CONFIG="${SURFGYM_OPERATOR_CONFIG:-$ROOT_DIR/config/runtime.toml}"
DOCKER_REPO="${SURFGYM_DOCKER_REPO:-$(cd -- "$ROOT_DIR/.." && pwd)/surfgym-docker-dev}"
READY_TIMEOUT_SECONDS="${SURFGYM_LOCAL_READY_TIMEOUT_SECONDS:-360}"
READY_POLL_SECONDS="${SURFGYM_LOCAL_READY_POLL_SECONDS:-0.2}"

while (($# > 0)); do
    case "$1" in
        --config)
            (($# >= 2)) || fail "--config requires a path."
            OPERATOR_CONFIG="$2"
            shift 2
            ;;
        --docker-repo)
            (($# >= 2)) || fail "--docker-repo requires a path."
            DOCKER_REPO="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            fail "Unknown argument: $1"
            ;;
    esac
done

case "$COMMAND" in
    check|up|down) ;;
    *) fail "Unknown command: $COMMAND" ;;
esac

[[ -d "$DOCKER_REPO" ]] || fail "Docker repository not found: $DOCKER_REPO"
PYTHON_OVERRIDE="${PYTHON_BIN:-}"
DOCKER_PYTHON_OVERRIDE="${DOCKER_PYTHON_BIN:-$PYTHON_OVERRIDE}"
if [[ "$COMMAND" == "down" ]]; then
    # Cleanup must remain available when either environment is broken. The
    # individual cleanup actions use these fallback values only if needed.
    PYTHON_BIN="${PYTHON_OVERRIDE:-python}"
    DOCKER_PYTHON_BIN="${DOCKER_PYTHON_OVERRIDE:-${PYTHON_OVERRIDE:-python3}}"
else
    PYTHON_BIN="$(resolve_python_bin "$PYTHON_OVERRIDE" "$ROOT_DIR" "PYTHON_BIN" "surfgym_runtime")"
    DOCKER_PYTHON_BIN="$(resolve_python_bin "$DOCKER_PYTHON_OVERRIDE" "$DOCKER_REPO" "DOCKER_PYTHON_BIN" "aiohttp, pydantic")"
fi
if [[ "$COMMAND" != "down" ]]; then
    [[ -f "$OPERATOR_CONFIG" ]] || fail "Operator config not found: $OPERATOR_CONFIG"
    [[ -f "$DOCKER_REPO/config.json" ]] || fail "Docker capability template not found: $DOCKER_REPO/config.json"
fi

SURF_OUTPUT="$ROOT_DIR/.runtime/config/surfgym.json"
DOCKER_OUTPUT="$ROOT_DIR/.runtime/config/docker.json"
SURF_PID_FILE="$ROOT_DIR/logs/nohup/all_launch_local_dev.pids"
DOCKER_RUNTIME_DIR="$DOCKER_REPO/src/runtime"
DOCKER_PID_DIR="$DOCKER_RUNTIME_DIR/pids"
DOCKER_LOG_DIR="$DOCKER_RUNTIME_DIR/logs"

compile_config() {
    local extra_args=()
    if [[ "$COMMAND" == "check" ]]; then
        extra_args=(--check)
    fi

    printf 'Validating operator config: %s\n' "$OPERATOR_CONFIG"
    "$PYTHON_BIN" -m surfgym_runtime.support.operator_config \
        --config "$OPERATOR_CONFIG" \
        --surf-repo "$ROOT_DIR" \
        --docker-repo "$DOCKER_REPO" \
        --surf-output "$SURF_OUTPUT" \
        --docker-output "$DOCKER_OUTPUT" \
        --check-prerequisites \
        --check-host-ports \
        "${extra_args[@]}"
}

require_docker_script() {
    local name="$1"
    [[ -f "$DOCKER_REPO/scripts/$name" ]] || fail "Docker entrypoint not found: $DOCKER_REPO/scripts/$name"
}

launch_docker_supervisor() {
    local name="$1"
    local script_name="$2"
    local pid_file="$DOCKER_PID_DIR/integrated_${name}.pid"
    local log_file="$DOCKER_LOG_DIR/integrated_${name}.log"
    local pid identity

    mkdir -p "$DOCKER_PID_DIR" "$DOCKER_LOG_DIR"
    if [[ -s "$pid_file" ]]; then
        printf 'Error: refusing to overwrite an existing supervisor PID record: %s\n' "$pid_file" >&2
        return 1
    fi
    printf 'Launching Docker %s supervisor\n' "$name"
    printf '  config: %s\n' "$DOCKER_OUTPUT"
    printf '  log:    %s\n' "$log_file"

    nohup env \
        CONFIG_PATH="$DOCKER_OUTPUT" \
        PYTHON_BIN="$DOCKER_PYTHON_BIN" \
        SURFGYM_RUNTIME_DIR="$DOCKER_RUNTIME_DIR" \
        STACK_PID_DIR="$DOCKER_PID_DIR" \
        STACK_LOG_DIR="$DOCKER_LOG_DIR" \
        STACK_READY_TIMEOUT_SECONDS="$READY_TIMEOUT_SECONDS" \
        bash "$DOCKER_REPO/scripts/$script_name" >"$log_file" 2>&1 &

    pid="$!"
    if ! identity="$(capture_process_identity_after_exec "$pid")"; then
        printf 'Error: could not capture identity for Docker %s supervisor (PID %s).\n' \
            "$name" "$pid" >&2
        print_log_tail "$log_file"
        kill -TERM "$pid" 2>/dev/null || true
        return 1
    fi
    printf '%s %s\n' "$pid" "$identity" >"$pid_file"
    if [[ "$name" == "controls" ]]; then
        controls_started=1
    else
        gateway_started=1
    fi
    printf '  pid:    %s\n' "$pid"
}

wait_pid_exit() {
    local pid="$1"
    local deadline=$((SECONDS + 5))
    while ((SECONDS < deadline)); do
        kill -0 "$pid" 2>/dev/null || return 0
        sleep 0.1
    done
    return 1
}

stop_docker_supervisor() {
    local name="$1"
    local pid_file="$DOCKER_PID_DIR/integrated_${name}.pid"
    local pid identity extra

    if [[ ! -f "$pid_file" ]]; then
        printf 'No recorded Docker %s supervisor.\n' "$name"
        return 0
    fi

    read -r pid identity extra < "$pid_file" || true
    if [[ ! "$pid" =~ ^[0-9]+$ || -z "$identity" || -n "$extra" ]]; then
        printf 'Refusing invalid Docker %s supervisor PID record: %s\n' "$name" "$pid_file" >&2
        return 1
    fi
    if ! kill -0 "$pid" 2>/dev/null; then
        printf 'Removing stale Docker %s supervisor PID file: %s\n' "$name" "$pid_file"
        rm -f -- "$pid_file"
        return 0
    fi

    if ! process_identity_matches "$pid" "$identity"; then
        printf 'Refusing to stop Docker %s supervisor: PID %s identity mismatch.\n' \
            "$name" "$pid" >&2
        return 1
    fi

    printf 'Stopping recorded Docker %s supervisor: %s\n' "$name" "$pid"
    kill -TERM "$pid"
    if wait_pid_exit "$pid"; then
        rm -f -- "$pid_file"
        return 0
    fi

    if ! process_identity_matches "$pid" "$identity"; then
        printf 'Refusing to signal reused Docker %s supervisor PID %s.\n' "$name" "$pid" >&2
        return 1
    fi

    printf 'Recorded Docker %s supervisor did not stop; sending KILL: %s\n' "$name" "$pid" >&2
    kill -KILL "$pid" 2>/dev/null || true
    if ! wait_pid_exit "$pid"; then
        printf 'Docker %s supervisor is still alive: %s\n' "$name" "$pid" >&2
        return 1
    fi
    rm -f -- "$pid_file"
}

reconcile_docker_pid_records() {
    local script_path="$DOCKER_REPO/scripts/05_reconcile_runtime_pids.sh"

    if [[ ! -f "$script_path" ]]; then
        printf 'Error: Docker runtime PID reconciler not found: %s\n' "$script_path" >&2
        return 1
    fi
    printf 'Reconciling config-derived Docker runtime PID records.\n'
    env \
        CONFIG_PATH="$DOCKER_OUTPUT" \
        PYTHON_BIN="$DOCKER_PYTHON_BIN" \
        SURFGYM_RUNTIME_DIR="$DOCKER_RUNTIME_DIR" \
        STACK_PID_DIR="$DOCKER_PID_DIR" \
        bash "$script_path"
}

print_log_tail() {
    local log_file="$1"
    if [[ -f "$log_file" ]]; then
        printf '%s\n' '--- log tail ---' >&2
        tail -n 20 "$log_file" >&2 || true
    fi
}

wait_for_docker_supervisor() {
    local name="$1"
    local marker="$2"
    local pid_file="$DOCKER_PID_DIR/integrated_${name}.pid"
    local log_file="$DOCKER_LOG_DIR/integrated_${name}.log"
    local pid identity extra
    local deadline=$((SECONDS + READY_TIMEOUT_SECONDS))

    read -r pid identity extra < "$pid_file" || return 1
    while ((SECONDS < deadline)); do
        if ! process_identity_matches "$pid" "$identity"; then
            printf 'Docker %s supervisor exited before readiness.\n' "$name" >&2
            print_log_tail "$log_file"
            return 1
        fi
        if grep -Fq "$marker" "$log_file" 2>/dev/null; then
            printf 'Docker %s supervisor is ready.\n' "$name"
            return 0
        fi
        sleep "$READY_POLL_SECONDS"
    done

    printf 'Timed out waiting for Docker %s supervisor readiness.\n' "$name" >&2
    print_log_tail "$log_file"
    return 1
}

surf_processes_match() {
    local name pid identity log_file
    local count=0
    [[ -s "$SURF_PID_FILE" ]] || return 1
    while read -r name pid identity log_file; do
        [[ -n "$name$pid$identity$log_file" ]] || continue
        process_identity_matches "$pid" "$identity" || return 1
        count=$((count + 1))
    done < "$SURF_PID_FILE"
    [[ "$count" -eq 3 ]]
}

wait_for_surf_stack() {
    local deadline=$((SECONDS + READY_TIMEOUT_SECONDS))
    while ((SECONDS < deadline)); do
        if ! surf_processes_match; then
            printf 'A SurfGym component exited before readiness.\n' >&2
            return 1
        fi
        if env \
            SURFGYM_CONFIG="$SURF_OUTPUT" \
            bash "$SCRIPT_DIR/health_check.bash" >/dev/null 2>&1 \
            && curl -fsS "http://127.0.0.1:3000/" >/dev/null 2>&1; then
            printf 'SurfGym gateway, WavePool, and fixture endpoints are ready.\n'
            return 0
        fi
        sleep "$READY_POLL_SECONDS"
    done
    printf 'Timed out waiting for SurfGym gateway, WavePool, and fixture endpoints.\n' >&2
    return 1
}

stop_compose_pool() {
    local compose_file="$DOCKER_REPO/src/runtime/docker-compose.yml"
    local docker_bin="${DOCKER_BIN:-}"
    local compose_env_args=()
    local compose_project

    if [[ ! -f "$compose_file" ]]; then
        printf 'No rendered Docker Compose file.\n'
        return 0
    fi
    if ! compose_project="$("$PYTHON_BIN" - "$DOCKER_OUTPUT" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as stream:
    config = json.load(stream)

project = config["runtime"]["compose_project"]
if not isinstance(project, str) or not project:
    raise ValueError("runtime.compose_project must be a non-empty string")
print(project)
PY
)"; then
        printf 'Error: cannot prove the Compose project from generated config: %s\n' \
            "$DOCKER_OUTPUT" >&2
        return 1
    fi
    if [[ -z "$docker_bin" ]]; then
        docker_bin="$(command -v docker || true)"
    fi
    if [[ -z "$docker_bin" ]]; then
        printf 'Error: docker CLI not found. Set DOCKER_BIN to stop the Compose pool.\n' >&2
        return 1
    fi
    if [[ -f "$DOCKER_REPO/.env" ]]; then
        compose_env_args=(--env-file "$DOCKER_REPO/.env")
    fi

    printf 'Stopping Docker Compose pool: %s (project: %s)\n' "$compose_file" "$compose_project"
    (
        cd -- "$DOCKER_REPO"
        "$docker_bin" compose "${compose_env_args[@]}" \
            --project-name "$compose_project" \
            -f "$compose_file" \
            down --remove-orphans
    )
}

compose_attempted=0
controls_started=0
gateway_started=0
surf_started=0
up_complete=0

rollback_incomplete_up() {
    local status="$?"
    trap - EXIT INT TERM
    if [[ "$COMMAND" == "up" ]] && ((up_complete == 0)); then
        printf 'Local stack startup failed; rolling back recorded resources.\n' >&2
        set +e
        if ((surf_started != 0)); then
            bash "$SCRIPT_DIR/all_stop.bash" "$SURF_PID_FILE"
        fi
        if ((gateway_started != 0)); then
            stop_docker_supervisor "gateway"
        fi
        if ((controls_started != 0)); then
            stop_docker_supervisor "controls"
        fi
        reconcile_docker_pid_records
        if ((compose_attempted != 0)); then
            stop_compose_pool
        fi
        set -e
    fi
    exit "$status"
}

if [[ "$COMMAND" == "down" ]]; then
    down_status=0
    bash "$SCRIPT_DIR/all_stop.bash" "$SURF_PID_FILE" || down_status=1
    stop_docker_supervisor "gateway" || down_status=1
    stop_docker_supervisor "controls" || down_status=1
    reconcile_docker_pid_records || down_status=1
    stop_compose_pool || down_status=1
    if ((down_status != 0)); then
        printf 'Local stack shutdown completed with errors; review the messages above.\n' >&2
        exit 1
    fi
    printf 'Local stack stopped.\n'
    exit 0
fi

compile_config

if [[ "$COMMAND" == "check" ]]; then
    printf 'Configuration check passed. No runtime files were written.\n'
    exit 0
fi

for script_name in \
    01_render_compose_up.sh \
    02_launch_docker_control.sh \
    03_launch_gateway.sh \
    05_reconcile_runtime_pids.sh; do
    require_docker_script "$script_name"
done

for pid_file in \
    "$SURF_PID_FILE" \
    "$DOCKER_PID_DIR/integrated_controls.pid" \
    "$DOCKER_PID_DIR/integrated_gateway.pid"; do
    if [[ -s "$pid_file" ]]; then
        fail "Existing PID record blocks startup. Run local_dev.bash down first: $pid_file"
    fi
done

trap rollback_incomplete_up EXIT
trap 'exit 130' INT TERM

printf 'Starting the local Docker pool with generated config: %s\n' "$DOCKER_OUTPUT"
compose_attempted=1
env \
    CONFIG_PATH="$DOCKER_OUTPUT" \
    PYTHON_BIN="$DOCKER_PYTHON_BIN" \
    bash "$DOCKER_REPO/scripts/01_render_compose_up.sh"
launch_docker_supervisor "controls" "02_launch_docker_control.sh"
wait_for_docker_supervisor "controls" "docker_control supervisor is running"
launch_docker_supervisor "gateway" "03_launch_gateway.sh"
wait_for_docker_supervisor "gateway" "gateway supervisor is running"

printf 'Starting SurfGym components with generated config: %s\n' "$SURF_OUTPUT"
surf_started=1
env \
    SURFGYM_CONFIG="$SURF_OUTPUT" \
    SURFGYM_PID_FILE="$SURF_PID_FILE" \
    bash "$SCRIPT_DIR/all_launch.bash"
wait_for_surf_stack

up_complete=1
trap - EXIT INT TERM
printf 'Local stack is ready for local requests. Configuration changes require a restart.\n'
