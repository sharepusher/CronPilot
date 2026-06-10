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
# gevent 20.9 源码构建：须 Cython 0.29.x，且禁用 build isolation
"$VENV/bin/pip" install -q 'cython<3.0' 'setuptools<70' wheel

if "$VENV/bin/python" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
  # greenlet 0.4.17 无 py3.10+ wheel；须先装 greenlet 1.1.x 再装 gevent，避免 ABI 不一致 segfault
  echo "Python 3.10+：使用 greenlet 1.1.3 + gevent 20.9"
  "$VENV/bin/pip" install -q 'greenlet==1.1.3'
  "$VENV/bin/pip" install -q --no-build-isolation 'gevent==20.9.0'
  REQ_FILE="$(mktemp)"
  grep -v -E '^(gevent|greenlet)==' "$ROOT/requirements.txt" > "$REQ_FILE"
  "$VENV/bin/pip" install -q --no-build-isolation -r "$REQ_FILE"
  rm -f "$REQ_FILE"
else
  "$VENV/bin/pip" install -q --no-build-isolation -r "$ROOT/requirements.txt"
fi

echo "完成。启动: bash scripts/run_production.sh"
