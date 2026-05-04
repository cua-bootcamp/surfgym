#!/usr/bin/env bash
set -euo pipefail

source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/setting.sh"

echo "[1/2] checking gateway"
curl -fsS "http://${GATEWAY_HOST}:${GATEWAY_PORT}/health" > /dev/null

echo "[2/2] checking wavepool"
curl -fsS "http://${WAVEPOOL_HOST}:${WAVEPOOL_MASTER_PORT}/health" > /dev/null

echo "ok"
