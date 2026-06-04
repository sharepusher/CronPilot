#!/bin/bash
# Ubuntu / Linux 生产启动（Gunicorn + gevent，0.0.0.0:5860）
set -e
cd "$(dirname "$0")/.."
# shellcheck source=lib/python.sh
source "$(dirname "$0")/lib/python.sh"

if [ ! -f conf.ini ]; then
  echo "缺少 conf.ini，请先: cp conf.ini.example conf.ini 并编辑" >&2
  exit 1
fi

cronpilot_load_runtime
VENV="$CRONPILOT_VENV"
export FLASK_CONFIG="${FLASK_CONFIG:-production}"

if ! "$VENV/bin/python" -c "import gevent" 2>/dev/null; then
  echo "未安装 gevent，请运行: bash scripts/install_production_deps.sh" >&2
  exit 1
fi

mkdir -p datas/logs
echo "CronPilot 生产模式 FLASK_CONFIG=$FLASK_CONFIG"
echo "管理端: http://0.0.0.0:5860/  文档: http://0.0.0.0:5860/docs/"
exec "$VENV/bin/gunicorn" -c gun.py manage:app
