#!/bin/bash
# Ubuntu / Linux 生产启动（Gunicorn + gevent，0.0.0.0:5860）
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# shellcheck source=lib/python.sh
source "$ROOT/scripts/lib/python.sh"
# shellcheck source=process.sh
source "$ROOT/scripts/process.sh"

FORCE=0
for arg in "$@"; do
  case "$arg" in
    --force|-f) FORCE=1 ;;
  esac
done

if [ ! -f conf.ini ]; then
  echo "缺少 conf.ini，请先: cp conf.ini.example conf.ini 并编辑" >&2
  exit 1
fi

cronpilot_load_runtime
VENV="$CRONPILOT_VENV"
export FLASK_CONFIG="${FLASK_CONFIG:-production}"
PROD_PORT="${PROD_PORT:-5860}"

if [ "$FLASK_CONFIG" = "production" ]; then
  if ! "$VENV/bin/python" "$ROOT/scripts/check_conf_production.py"; then
    exit 1
  fi
fi

if ! "$VENV/bin/python" -c "import gevent" 2>/dev/null; then
  echo "未安装 gevent，请运行: bash scripts/install_production_deps.sh" >&2
  exit 1
fi

mkdir -p datas/logs
bash "$ROOT/scripts/ensure_business_tables.sh"

pids=$(cronpilot_listen_pids "$PROD_PORT")
if [ -n "${pids// }" ]; then
  if [ "$FORCE" -eq 1 ]; then
    cronpilot_stop_listen_port "$PROD_PORT" "CronPilot production (0.0.0.0:${PROD_PORT})"
  else
    echo "ERROR: 0.0.0.0:${PROD_PORT} 已被占用 (PID ${pids})" >&2
    echo "  先执行: bash scripts/stop_production.sh" >&2
    echo "  或:     bash scripts/restart_production.sh" >&2
    exit 1
  fi
fi

echo "CronPilot 生产模式 FLASK_CONFIG=$FLASK_CONFIG"
echo "管理端: http://0.0.0.0:${PROD_PORT}/  文档: http://0.0.0.0:${PROD_PORT}/docs/"
exec "$VENV/bin/gunicorn" -c gun.py manage:app
