#!/bin/bash
# 在已有 venv 上安装生产依赖（Gunicorn + gevent），Ubuntu 需先装编译依赖
set -e
cd "$(dirname "$0")/.."
# shellcheck source=lib/python.sh
source "$(dirname "$0")/lib/python.sh"

cronpilot_load_runtime
VENV="$CRONPILOT_VENV"

echo "安装生产依赖到: $VENV"
"$VENV/bin/pip" install -q --upgrade 'pip<25'
"$VENV/bin/pip" install -q -r requirements.txt
echo "完成。启动: bash scripts/run_production.sh"
