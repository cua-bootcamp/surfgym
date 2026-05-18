#!/usr/bin/env bash
set -euo pipefail

source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/setting.sh"
PIDS=()

terminate_pid() {
  local pid="$1"
  local i

  if ! kill -0 "$pid" 2>/dev/null; then
    return 0
  fi

  pkill -TERM -P "$pid" 2>/dev/null || true
  kill -TERM "$pid" 2>/dev/null || true

  for ((i = 0; i < 100; i++)); do
    if ! kill -0 "$pid" 2>/dev/null; then
      wait "$pid" 2>/dev/null || true
      return 0
    fi
    sleep 0.1
  done

  pkill -KILL -P "$pid" 2>/dev/null || true
  kill -KILL "$pid" 2>/dev/null || true
  wait "$pid" 2>/dev/null || true
}

cleanup() {
  local idx
  trap - EXIT INT TERM
  for ((idx=${#PIDS[@]}-1; idx>=0; idx--)); do
    terminate_pid "${PIDS[idx]}"
  done
}



wait_for_http() {
  local name="$1"
  local command="$2"
  local attempts="${3:-60}"
  local sleep_seconds="${4:-1}"
  local i

  for ((i = 1; i <= attempts; i++)); do
    if eval "$command" >/dev/null 2>&1; then
      echo "$name is ready"
      return 0
    fi
    sleep "$sleep_seconds"
  done

  echo "timed out waiting for $name" >&2
  return 1
}

trap cleanup EXIT INT TERM

printf '##########################################\n'
printf '#        Launching Gateway Server        #\n'
printf '##########################################\n'
(
  cd "$ROOT_DIR" || exit 1
  printf 'Executing "python -m src.main %s"\n\n' \
    "$SURFGYM_CONFIG"ㅔ
  exec python -m src.main "$SURFGYM_CONFIG"
) &
PIDS+=("$!")
wait_for_http \
  "gateway" \
  "curl -fsS http://${GATEWAY_HOST}:${GATEWAY_PORT}/health"



printf '###########################################\n'
printf '#        Launching Wavepool Server        #\n'
printf '###########################################\n'
(
  cd "$ROOT_DIR" || exit 1
  printf 'Executing "python -m src.wavepool.deploy %s"\n\n' \
    "$SURFGYM_CONFIG"
  exec python -m src.wavepool.deploy "$SURFGYM_CONFIG"
) &
PIDS+=("$!")

wait_for_http \
  "wavepool" \
  "curl -fsS http://${WAVEPOOL_HOST}:${WAVEPOOL_MASTER_PORT}/health"



printf '##########################################\n'
printf '#        Launching Fixture Server        #\n'
printf '##########################################\n'
(
  cd "$FIXTURE_DIR/websites" || exit 1

  printf 'MAIN_PORT=%s PROZILLA_PORT=%s pnpm run serve\n' "$FIXTURE_MAIN_PORT" "$FIXTURE_PROZILLA_PORT"

  exec env \
    MAIN_PORT="$FIXTURE_MAIN_PORT" \
    PROZILLA_PORT="$FIXTURE_PROZILLA_PORT" \
    pnpm run serve
) &
PIDS+=("$!")

wait_for_http \
  "fixture website" \
  "curl -fsS http://127.0.0.1:${FIXTURE_MAIN_PORT}/index.html"

wait_for_http \
  "fixture website" \
  "curl -fsS http://127.0.0.1:${FIXTURE_PROZILLA_PORT}/index.html"



printf '##########################################\n'
printf '#             Executing Test             #\n'
printf '##########################################\n'
(
  cd "$ROOT_DIR"
  python -m tests.runners.manual.run --config-path "$SURFGYM_CONFIG"
)