#!/bin/bash
# 本地冒烟：自动匹配 Python 3.8–3.11，无需手动指定版本
set -e
cd "$(dirname "$0")/.."
# shellcheck source=lib/python.sh
source "$(dirname "$0")/lib/python.sh"

cronpilot_load_runtime
PY="$CRONPILOT_PY"
VENV="$CRONPILOT_VENV"
echo "CronPilot 自动匹配: $PY ($("$PY" --version 2>&1))"
echo "虚拟环境: $VENV"

export FLASK_CONFIG=development
echo "管理端:     http://127.0.0.1:5001/  (密码见 conf.ini login_pwd)"
echo "技术文档:   http://127.0.0.1:5001/docs/"
"$VENV/bin/python" -c "
from app import create_app
app = create_app('development')
app.run(host='127.0.0.1', port=5001, debug=False, use_reloader=False)
"
