#!/bin/bash
# 停止本地开发服务（默认 127.0.0.1:5001）
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# shellcheck source=process.sh
source "$ROOT/scripts/process.sh"

LOCAL_PORT="${LOCAL_PORT:-5001}"
cronpilot_stop_listen_port "$LOCAL_PORT" "CronPilot local (${LOCAL_HOST:-127.0.0.1}:${LOCAL_PORT})"
cronpilot_cleanup_local_pid_file "$ROOT"
