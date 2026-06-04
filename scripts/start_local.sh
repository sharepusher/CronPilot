#!/bin/bash
# 本地冒烟：自动选用 Python 3.8 / 3.9 / 3.10 / 3.11（可用 PY= 指定）
set -e
cd "$(dirname "$0")/.."
# shellcheck source=lib/python.sh
source "$(dirname "$0")/lib/python.sh"

PY=$(cronpilot_pick_python)
VENV=$(cronpilot_venv_dir "$PY")
echo "CronPilot 使用: $PY ($("$PY" --version 2>&1))"
echo "虚拟环境: $VENV"

if [ ! -d "$VENV" ]; then
  "$PY" -m venv "$VENV"
  "$VENV/bin/pip" install -q --upgrade pip
  "$VENV/bin/pip" install -q -r requirements-core.txt
fi

export FLASK_CONFIG=development
echo "管理端:     http://127.0.0.1:5001/  (密码见 conf.ini login_pwd)"
echo "技术文档:   http://127.0.0.1:5001/docs/"
"$VENV/bin/python" -c "
from app import create_app
app = create_app('development')
app.run(host='127.0.0.1', port=5001, debug=False, use_reloader=False)
"
