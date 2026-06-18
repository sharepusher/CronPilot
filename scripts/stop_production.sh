#!/bin/bash
# 停止生产 Gunicorn（默认 0.0.0.0:5860）
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# shellcheck source=process.sh
source "$ROOT/scripts/process.sh"

PROD_PORT="${PROD_PORT:-5860}"
cronpilot_stop_listen_port "$PROD_PORT" "CronPilot production (0.0.0.0:${PROD_PORT})"
