# CronPilot 进程 / 端口管理（供 start/stop/restart 脚本 source）
# shellcheck shell=bash

cronpilot_listen_pids() {
  local port="$1"
  lsof -nP -iTCP:"${port}" -sTCP:LISTEN -t 2>/dev/null | tr '\n' ' ' || true
}

cronpilot_stop_listen_port() {
  local port="$1"
  local label="${2:-port ${port}}"
  local pids pid
  pids=$(cronpilot_listen_pids "$port")
  if [ -z "${pids// }" ]; then
    echo "未运行 (${label})"
    return 0
  fi
  echo "停止 ${label} (PID: ${pids})..."
  # shellcheck disable=SC2086
  kill ${pids} 2>/dev/null || true
  sleep 1
  pids=$(cronpilot_listen_pids "$port")
  if [ -n "${pids// }" ]; then
    # shellcheck disable=SC2086
    kill -9 ${pids} 2>/dev/null || true
    sleep 1
  fi
  pids=$(cronpilot_listen_pids "$port")
  if [ -n "${pids// }" ]; then
    echo "ERROR: 无法释放 ${label}，仍被 PID ${pids} 占用" >&2
    return 1
  fi
  echo "已停止 (${label})"
}

cronpilot_local_pid_file() {
  echo "${1:-.}/datas/cronpilot-local.pid"
}

cronpilot_cleanup_local_pid_file() {
  local root="${1:-.}"
  rm -f "$(cronpilot_local_pid_file "$root")"
}

cronpilot_status_port() {
  local port="$1" label="$2"
  local pids
  pids=$(cronpilot_listen_pids "$port")
  if [ -n "${pids// }" ]; then
    echo "运行中  ${label}  端口 ${port}  PID ${pids}"
    return 0
  fi
  echo "未运行  ${label}  端口 ${port}"
  return 1
}
