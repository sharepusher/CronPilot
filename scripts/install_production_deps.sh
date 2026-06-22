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

if "$VENV/bin/python" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)'; then
  # gevent/greenlet 与 requirements 一并解析时，新版 pip 易与 SQLAlchemy 1.4 冲突；先装 greenlet 再装 gevent
  echo "Python 3.9+：使用 greenlet 1.1.3 + gevent 20.9（分步安装）"
  "$VENV/bin/pip" install -q 'greenlet==1.1.3'
  "$VENV/bin/pip" install -q 'zope.interface==5.1.0' 'zope.event==4.5.0'
  "$VENV/bin/pip" install -q --no-build-isolation 'gevent==20.9.0'
  REQ_FILE="$(mktemp)"
  grep -v -E '^(gevent|greenlet|zope\.(interface|event))==' "$ROOT/requirements.txt" > "$REQ_FILE"
  "$VENV/bin/pip" install -q -r "$REQ_FILE"
  rm -f "$REQ_FILE"
else
  "$VENV/bin/pip" install -q --no-build-isolation -r "$ROOT/requirements.txt"
fi

"$VENV/bin/pip" install -q 'setuptools<70'

echo "完成。启动: bash scripts/run_production.sh"
