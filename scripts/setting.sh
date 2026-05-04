#!/usr/bin/env bash

readonly ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SURFGYM_CONFIG="$ROOT_DIR/config.json"

json_get() {
  jq -r "$1" "$SURFGYM_CONFIG"
}

readonly GATEWAY_HOST="$(jq -r '.gateway.host' "$SURFGYM_CONFIG")"
readonly GATEWAY_PORT="$(jq -r '.gateway.port' "$SURFGYM_CONFIG")"

readonly OMNIBOX_HOST="$(jq -r '.omnibox.host' "$SURFGYM_CONFIG")"
readonly OMNIBOX_MASTER_PORT="$(jq -r '.omnibox.master_port' "$SURFGYM_CONFIG")"
readonly OMNIBOX_INSTANCE_START_PORT="$(jq -r '.omnibox.instance_start_port' "$SURFGYM_CONFIG")"

readonly OMNIBOX_INSTANCE="$(jq -r '.omnibox.instances' "$SURFGYM_CONFIG")"
readonly OMNIBOX_MASTER_WORKERS="$(jq -r '.omnibox.master_workers' "$SURFGYM_CONFIG")"