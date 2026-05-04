#!/usr/bin/env bash

readonly ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly TEST_DIR="$ROOT_DIR/tests"
readonly FIXTURE_DIR="$TEST_DIR/fixtures"

# =============================================================================================
# User-defined settings
# Modify only the values below for testing.
# 
# * Use the appropriate SURFGYM_CONFIG for the target test
# * Make sure to set WITH_FIXTURE_WEBSITE=true when using fixture websites
# =============================================================================================

readonly SURFGYM_CONFIG="$FIXTURE_DIR/config/config-single.json"

readonly WITH_FIXTURE_WEBSITE=true
readonly FIXTURE_WEBSITE_PORT=8123

# =============================================================================================

json_get(){
    jq -r "$1" "$SURFGYM_CONFIG"
}

readonly GATEWAY_HOST="$(jq -r '.gateway.host' "$SURFGYM_CONFIG")"
readonly GATEWAY_PORT="$(jq -r '.gateway.port' "$SURFGYM_CONFIG")"

readonly WAVEPOOL_HOST="$(jq -r '.wavepool.host' "$SURFGYM_CONFIG")"
readonly WAVEPOOL_MASTER_PORT="$(jq -r '.wavepool.master_port' "$SURFGYM_CONFIG")"
readonly WAVEPOOL_INSTANCE_START_PORT="$(jq -r '.wavepool.instance_start_port' "$SURFGYM_CONFIG")"
readonly WAVEPOOL_INSTANCE="$(jq -r '.wavepool.instances' "$SURFGYM_CONFIG")"
readonly WAVEPOOL_MASTER_WORKERS="$(jq -r '.wavepool.master_workers' "$SURFGYM_CONFIG")"