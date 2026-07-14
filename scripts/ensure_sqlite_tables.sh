#!/bin/bash
# 业务库建表/补列：SQLite 与 MySQL（mysql+pymysql）均由 ensure_sqlite_tables.py 处理
set -e
cd "$(dirname "$0")/.."
# shellcheck source=lib/python.sh
source "$(dirname "$0")/lib/python.sh"
cronpilot_load_runtime
mkdir -p datas/logs
export FLASK_CONFIG="${FLASK_CONFIG:-development}"
"$CRONPILOT_VENV/bin/python" scripts/ensure_sqlite_tables.py
