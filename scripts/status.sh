#!/bin/bash
# 查看 CronPilot 本地 / 生产进程状态
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# shellcheck source=process.sh
source "$ROOT/scripts/process.sh"

LOCAL_PORT="${LOCAL_PORT:-5001}"
PROD_PORT="${PROD_PORT:-5860}"
local_ok=0 prod_ok=0

cronpilot_status_port "$LOCAL_PORT" "local dev" && local_ok=1 || true
cronpilot_status_port "$PROD_PORT" "production" && prod_ok=1 || true

if [ "$local_ok" -eq 0 ] && [ "$prod_ok" -eq 0 ]; then
  exit 1
fi
