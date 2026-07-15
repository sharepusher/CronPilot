#!/bin/bash
# CronPilot 本地开发统一入口（stop / restart / status；不依赖 root 属主的 cronpilot.sh 补丁）
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

usage() {
  cat <<'EOF'
用法: bash scripts/cronpilot_dev.sh <命令>

命令:
  start [--daemon|-d]   启动本地开发 (127.0.0.1:5001)
  stop                  停止本地开发
  restart [--daemon|-d] 先停后启（推荐，默认 --force 避免端口占用留下旧进程）
  status                查看本地 / 生产端口

与 cronpilot.sh 共用: install | test | check | python | exec
  bash scripts/cronpilot.sh test
EOF
}

cmd="${1:-}"
shift || true

case "$cmd" in
  start)
    exec bash "$ROOT/scripts/start_local_full.sh" "$@"
    ;;
  stop)
    exec bash "$ROOT/scripts/stop_local.sh"
    ;;
  restart)
    exec bash "$ROOT/scripts/restart_local.sh" "$@"
    ;;
  status)
    exec bash "$ROOT/scripts/status.sh"
    ;;
  -h|--help|help|'')
    usage
    ;;
  *)
    echo "未知命令: $cmd" >&2
    usage
    exit 1
    ;;
esac
