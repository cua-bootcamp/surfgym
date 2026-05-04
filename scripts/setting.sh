#!/usr/bin/env bash

readonly ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
readonly SURFGYM_CONFIG="$ROOT_DIR/scripts/config.json"
readonly FIXTURE_DIR="$ROOT_DIR/tests/fixtures"

json_get() {
  jq -r "$1" "$SURFGYM_CONFIG"
}

readonly GATEWAY_HOST="$(jq -r '.gateway.host' "$SURFGYM_CONFIG")"
readonly GATEWAY_PORT="$(jq -r '.gateway.port' "$SURFGYM_CONFIG")"

readonly WAVEPOOL_HOST="$(jq -r '.wavepool.host' "$SURFGYM_CONFIG")"
readonly WAVEPOOL_MASTER_PORT="$(jq -r '.wavepool.master_port' "$SURFGYM_CONFIG")"
readonly WAVEPOOL_INSTANCE_START_PORT="$(jq -r '.wavepool.instance_start_port' "$SURFGYM_CONFIG")"

readonly WAVEPOOL_INSTANCE="$(jq -r '.wavepool.instances' "$SURFGYM_CONFIG")"
readonly WAVEPOOL_MASTER_WORKERS="$(jq -r '.wavepool.master_workers' "$SURFGYM_CONFIG")"

readonly FIXTURE_WEBSITE_PORT=8123