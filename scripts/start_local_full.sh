#!/bin/bash
# 本地开发：自动匹配 Python 3.8–3.11；启动前 ensure conf.ini / SQLite 表 / 端口
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# shellcheck source=lib/python.sh
source "$ROOT/scripts/lib/python.sh"
# shellcheck source=process.sh
source "$ROOT/scripts/process.sh"

DAEMON=0
FORCE=0
for arg in "$@"; do
  case "$arg" in
    --daemon|-d) DAEMON=1 ;;
    --force|-f) FORCE=1 ;;
    -h|--help)
      cat <<'EOF'
用法: bash scripts/start_local_full.sh [选项]

选项:
  --daemon, -d   后台运行，日志写入 datas/logs/local-server.log
  --force, -f    若端口被占用则先停止再启动
EOF
      exit 0
      ;;
    *)
      echo "未知参数: $arg（可用 --help）" >&2
      exit 1
      ;;
  esac
done

LOCAL_HOST="${LOCAL_HOST:-127.0.0.1}"
LOCAL_PORT="${LOCAL_PORT:-5001}"

cronpilot_load_runtime
PY="$CRONPILOT_PY"
VENV="$CRONPILOT_VENV"
echo "CronPilot 自动匹配: $PY ($("$PY" --version 2>&1))"
echo "虚拟环境: $VENV"

if [ ! -f conf.ini ]; then
  cp conf.ini.example conf.ini
  echo "已生成 conf.ini（试用请确认 SQLite 路径与 login_pwd）"
fi

export FLASK_CONFIG=development
export CRONPILOT_FORCE_NEW_UI=true
bash "$ROOT/scripts/ensure_business_tables.sh"

pids=$(cronpilot_listen_pids "$LOCAL_PORT")
if [ -n "${pids// }" ]; then
  if [ "$FORCE" -eq 1 ]; then
    cronpilot_stop_listen_port "$LOCAL_PORT" "CronPilot local (${LOCAL_HOST}:${LOCAL_PORT})"
    cronpilot_cleanup_local_pid_file "$ROOT"
  else
    echo "ERROR: ${LOCAL_HOST}:${LOCAL_PORT} 已被占用 (PID ${pids})" >&2
    echo "  先执行: bash scripts/stop_local.sh" >&2
    echo "  或:     bash scripts/restart_local.sh" >&2
    exit 1
  fi
fi

LOGIN_PWD=$(grep -E '^login_pwd\s*=' conf.ini 2>/dev/null | head -1 | sed 's/^login_pwd[[:space:]]*=[[:space:]]*//' || echo '见 conf.ini')
echo "管理端:     http://${LOCAL_HOST}:${LOCAL_PORT}/  (login_pwd=${LOGIN_PWD})"
echo "技术文档:   http://${LOCAL_HOST}:${LOCAL_PORT}/docs/"

if [ "$DAEMON" -eq 1 ]; then
  mkdir -p datas/logs
  LOG="$ROOT/datas/logs/local-server.log"
  PID_FILE="$(cronpilot_local_pid_file "$ROOT")"
  nohup "$VENV/bin/python" -c "
from app import create_app
app = create_app('development')
app.run(host='${LOCAL_HOST}', port=${LOCAL_PORT}, debug=False, use_reloader=False)
" >>"$LOG" 2>&1 &
  echo $! >"$PID_FILE"
  sleep 2
  if ! cronpilot_listen_pids "$LOCAL_PORT" | grep -q .; then
    echo "ERROR: 后台启动失败，查看 $LOG" >&2
    tail -20 "$LOG" >&2 || true
    exit 1
  fi
  echo "后台已启动 PID $(cat "$PID_FILE")，日志: $LOG"
  exit 0
fi

exec "$VENV/bin/python" -c "
from app import create_app
app = create_app('development')
app.run(host='${LOCAL_HOST}', port=${LOCAL_PORT}, debug=False, use_reloader=False)
"
