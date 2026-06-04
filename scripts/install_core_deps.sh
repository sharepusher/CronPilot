#!/bin/bash
# 自动匹配 Python 3.8–3.11 并安装核心依赖
set -e
cd "$(dirname "$0")/.."
# shellcheck source=lib/python.sh
source "$(dirname "$0")/lib/python.sh"

cronpilot_load_runtime
PY="$CRONPILOT_PY"
VENV="$CRONPILOT_VENV"
echo "Python: $PY ($("$PY" --version 2>&1))"
echo "Venv:   $VENV"
echo "Done. Activate: source $VENV/bin/activate"
