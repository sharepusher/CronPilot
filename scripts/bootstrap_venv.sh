#!/bin/bash
# 创建/更新 venv 并安装 requirements-core.txt（Ubuntu/macOS 通用）
set -e
cd "$(dirname "$0")/.."
# shellcheck source=lib/python.sh
source "$(dirname "$0")/lib/python.sh"

cronpilot_load_runtime
PY="$CRONPILOT_PY"
VENV="$CRONPILOT_VENV"
echo "Python: $PY ($("$PY" --version 2>&1))"
echo "Venv:   $VENV"
"$VENV/bin/pip" install -q --upgrade 'pip<25'
"$VENV/bin/pip" install -q -r requirements-core.txt
echo "核心依赖已安装。"
echo "  开发: bash scripts/start_local.sh"
echo "  生产: bash scripts/install_production_deps.sh && bash scripts/run_production.sh"
