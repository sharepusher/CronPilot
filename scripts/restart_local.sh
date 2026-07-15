#!/bin/bash
# 重启本地开发服务：先停后启（默认 --force，避免端口占用导致仍跑旧进程）
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
bash "$ROOT/scripts/stop_local.sh" || true
# 保证 start 在残留占用时仍能杀旧进程再起（本轮反复踩坑：端口占着旧代码，刷新无效）
has_force=0
has_daemon=0
args=()
for arg in "$@"; do
  case "$arg" in
    --force|-f) has_force=1 ;;
    --daemon|-d) has_daemon=1 ;;
  esac
  args+=("$arg")
done
[ "$has_force" -eq 1 ] || args+=(--force)
exec bash "$ROOT/scripts/start_local_full.sh" "${args[@]}"
