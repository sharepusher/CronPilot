#!/usr/bin/env bash
# Codex 沙盒专用入口：只管理自身 PID，默认离线检查。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
source "$ROOT/scripts/lib/python.sh"

HOST="${LOCAL_HOST:-127.0.0.1}"
PORT="${LOCAL_PORT:-5001}"
PID_FILE="$ROOT/datas/cronpilot-codex.pid"
LOG_FILE="$ROOT/datas/logs/codex-server.log"

pid_alive() { [ -n "${1:-}" ] && kill -0 "$1" 2>/dev/null; }
port_http() { curl -fsS --max-time 2 "http://${HOST}:${PORT}/rbac/login" >/dev/null 2>&1; }

owned_pid() {
  local pid="${1:-}" cmd=""
  [ -n "$pid" ] || return 1
  if [ -r "/proc/$pid/cmdline" ]; then
    cmd=$(tr '\0' ' ' <"/proc/$pid/cmdline")
  elif command -v ps >/dev/null 2>&1; then
    cmd=$(ps -p "$pid" -o command= 2>/dev/null || true)
  else
    return 1
  fi
  [[ "$cmd" == *"$ROOT"* && "$cmd" == *"$ROOT/.venv"* ]]
}

start() {
  if port_http; then
    echo "ERROR: ${HOST}:${PORT} 已有 HTTP 服务；Codex 脚本不会终止外部进程" >&2
    return 3
  fi
  cronpilot_load_runtime
  mkdir -p "$ROOT/datas/logs"
  export FLASK_CONFIG=development
  nohup "$CRONPILOT_VENV/bin/python" -c "from app import create_app; app=create_app('development'); app.run(host='${HOST}', port=${PORT}, debug=False, use_reloader=False)" >>"$LOG_FILE" 2>&1 &
  echo $! >"$PID_FILE"
  sleep 2
  if ! port_http; then
    echo "ERROR: 启动失败，日志：$LOG_FILE" >&2
    kill "$(cat "$PID_FILE")" 2>/dev/null || true
    rm -f "$PID_FILE"
    return 1
  fi
  echo "Codex 服务已启动：PID $(cat "$PID_FILE")，URL http://${HOST}:${PORT}"
}

stop() {
  local pid=""
  [ -f "$PID_FILE" ] && pid=$(cat "$PID_FILE")
  if ! pid_alive "$pid"; then
    rm -f "$PID_FILE"
    echo "Codex 服务未运行"
    return 0
  fi
  if ! owned_pid "$pid"; then
    echo "ERROR: PID $pid 无法证明属于 Codex 服务，拒绝终止；请在宿主环境处理" >&2
    return 3
  fi
  kill "$pid" 2>/dev/null || true
  for _ in 1 2 3 4 5; do pid_alive "$pid" || break; sleep 1; done
  if pid_alive "$pid"; then
    echo "ERROR: PID $pid 未退出；请在宿主环境处理" >&2
    return 3
  fi
  rm -f "$PID_FILE"
  echo "Codex 服务已停止"
}

status() {
  local pid=""
  [ -f "$PID_FILE" ] && pid=$(cat "$PID_FILE")
  if pid_alive "$pid" && port_http; then
    echo "运行中 PID=$pid URL=http://${HOST}:${PORT}"
    return 0
  fi
  echo "未运行 URL=http://${HOST}:${PORT}"
  return 1
}

check() {
  local online=0
  [ "${1:-}" = "--online" ] && online=1
  cronpilot_load_runtime
  "$CRONPILOT_VENV/bin/python" -c 'import flask, pymysql; print("offline dependencies: OK")'
  if [ "$online" -eq 1 ]; then
    "$CRONPILOT_VENV/bin/python" -m pip check
    "$CRONPILOT_VENV/bin/python" -m pip install --dry-run 'pip<25' >/dev/null
  else
    echo "offline validation: skipped PyPI/pip pin check"
  fi
}

case "${1:-}" in
  start) start ;;
  stop) stop ;;
  status) status ;;
  check) shift; check "$@" ;;
  *) echo "用法: $0 {start|stop|status|check [--online]}" >&2; exit 2 ;;
esac
