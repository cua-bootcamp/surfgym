#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
CALLER_CWD="$(pwd)"
DEFAULT_TASK_PATH="packages/surfgym-task/src/surfgym_task/data/chrome/verified/open_password_manager.json"

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  echo "Usage: $0 [TASK_JSON] [extra args...]"
  echo
  echo "Example:"
  echo "  $0 packages/surfgym-task/src/surfgym_task/data/chrome/tasks.jsonl --task-id chromium_enable_bookmarks_bar"
  echo
  echo "Default task: $DEFAULT_TASK_PATH"
  echo "Profile dir defaults to a unique /tmp/surfgym-<task-file-name>-profile-* directory."
  echo "Override with SURFGYM_CHROME_PROFILE_DIR=/tmp/my-profile when you want to reuse one."
  exit 0
fi

if [ "$#" -lt 1 ]; then
  TASK_PATH="$DEFAULT_TASK_PATH"
else
  TASK_PATH="$1"
  shift
fi

if [[ "$TASK_PATH" = /* ]]; then
  RESOLVED_TASK_PATH="$TASK_PATH"
elif [ -f "$CALLER_CWD/$TASK_PATH" ]; then
  RESOLVED_TASK_PATH="$CALLER_CWD/$TASK_PATH"
else
  RESOLVED_TASK_PATH="$ROOT_DIR/$TASK_PATH"
fi

TASK_FILE_NAME="$(basename -- "$RESOLVED_TASK_PATH")"
TASK_NAME="${TASK_FILE_NAME%.*}"
SAFE_TASK_NAME="$(printf "%s" "$TASK_NAME" | tr -c "A-Za-z0-9._-" "_")"
if [ -n "${SURFGYM_CHROME_PROFILE_DIR:-}" ]; then
  PROFILE_DIR="$SURFGYM_CHROME_PROFILE_DIR"
else
  PROFILE_DIR="$(mktemp -d "/tmp/surfgym-${SAFE_TASK_NAME}-profile-XXXXXX")"
fi

cd "$ROOT_DIR/packages/surfgym-runtime"

echo "Task: $RESOLVED_TASK_PATH"
echo "Profile: $PROFILE_DIR"

exec uv run python -m surfgym_runtime.tools.manual_chromium_eval \
  "$RESOLVED_TASK_PATH" \
  --profile-dir "$PROFILE_DIR" \
  --keep-profile \
  --fail-on-zero \
  "$@"
