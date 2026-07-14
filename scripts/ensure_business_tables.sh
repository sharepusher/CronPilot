#!/bin/bash
# 确保业务库表/缺列（SQLite 与 MySQL）
set -e
cd "$(dirname "$0")/.."
# shellcheck source=lib/python.sh
source "$(dirname "$0")/lib/python.sh"
cronpilot_load_runtime
mkdir -p datas/logs
export FLASK_CONFIG="${FLASK_CONFIG:-development}"
"$CRONPILOT_VENV/bin/python" scripts/ensure_business_tables.py
