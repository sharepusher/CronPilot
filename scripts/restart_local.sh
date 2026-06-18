#!/bin/bash
# 重启本地开发服务：先停后启，自动 ensure SQLite 表
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
bash "$ROOT/scripts/stop_local.sh"
exec bash "$ROOT/scripts/start_local_full.sh" "$@"
