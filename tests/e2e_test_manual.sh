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

logstep() {
  local msg=">>> $1"
  local width=72
  local border
  local content_width=$((width - 4))

  border="$(printf '%*s' "$content_width" '' | tr ' ' '=')"

  printf '\n'
  printf '# %s #\n' "$border"
  printf '# %-*s #\n' "$content_width" "$msg"
  printf '# %s #\n' "$border"
  printf '\n'
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

logstep "#1 launching webgym-rl server"
(
  cd "$ROOT_DIR" || exit 1
  printf 'Executing "python -m src.main %s"\n\n' \
    "$WEBGYM_RL_CONFIG"
  exec python -m src.main "$WEBGYM_RL_CONFIG"
) &
PIDS+=("$!")
wait_for_http \
  "gateway" \
  "curl -fsS http://${GATEWAY_HOST}:${GATEWAY_PORT}/health"

logstep "#2 launching omnibox"
(
  cd "$ROOT_DIR" || exit 1
  printf 'Executing "python -m src.omnibox.deploy %s"\n\n' \
    "$WEBGYM_RL_CONFIG"
  exec python -m src.omnibox.deploy "$WEBGYM_RL_CONFIG"
) &
PIDS+=("$!")

wait_for_http \
  "omnibox" \
  "curl -fsS http://${OMNIBOX_HOST}:${OMNIBOX_MASTER_PORT}/health"

if [[ "$WITH_FIXTURE_WEBSITE" == "true" ]]; then
  logstep "#3 launching fixture website"
  (
    cd "$ROOT_DIR" || exit 1
    printf 'Executing "python -m http.server %s --directory %s"\n\n' \
      "$FIXTURE_WEBSITE_PORT" \
      "$FIXTURE_DIR/website"
    exec python -m http.server "$FIXTURE_WEBSITE_PORT" --directory "$FIXTURE_DIR/website"
  ) &
  PIDS+=("$!")

  wait_for_http \
    "fixture website" \
    "curl -fsS http://127.0.0.1:${FIXTURE_WEBSITE_PORT}/index.html"
else
  logstep "#3 skipping fixture website"
fi


logstep "#4 e2e_test_manual"
(
  cd "$ROOT_DIR"
  python -m tests.e2e_test_manual.run --config-path "$WEBGYM_RL_CONFIG"
)