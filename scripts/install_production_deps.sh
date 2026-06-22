#!/bin/bash
# 在已有 venv 上安装生产依赖（Gunicorn + gevent），Ubuntu 需先装编译依赖
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# shellcheck source=lib/python.sh
source "$(dirname "$0")/lib/python.sh"

cronpilot_load_runtime
VENV="$CRONPILOT_VENV"

echo "安装生产依赖到: $VENV"
"$VENV/bin/pip" install -q --upgrade 'pip<25'
# gevent 23.x 在多数平台有 wheel；无 wheel 时回退源码构建
"$VENV/bin/pip" install -q 'cython<3.0' 'setuptools<70' wheel
"$VENV/bin/pip" install -q -r "$ROOT/requirements.txt"
"$VENV/bin/pip" install -q 'setuptools<70'

echo "完成。启动: bash scripts/run_production.sh"
