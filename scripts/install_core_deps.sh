#!/bin/bash
# 按当前 Python 3.8–3.11 创建虚拟环境并安装核心依赖
set -e
cd "$(dirname "$0")/.."
# shellcheck source=lib/python.sh
source "$(dirname "$0")/lib/python.sh"

PY=$(cronpilot_pick_python)
VENV=$(cronpilot_venv_dir "$PY")
echo "Python: $PY ($("$PY" --version 2>&1))"
echo "Venv:   $VENV"

if [ ! -d "$VENV" ]; then
  "$PY" -m venv "$VENV"
fi
"$VENV/bin/pip" install -q --upgrade pip
"$VENV/bin/pip" install -q -r requirements-core.txt
echo "Done. Activate: source $VENV/bin/activate"
