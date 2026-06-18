#!/bin/bash
# 本地 SQLite 试用：自动创建 cron_infos / job_log / job_log_items 表
set -e
cd "$(dirname "$0")/.."
# shellcheck source=lib/python.sh
source "$(dirname "$0")/lib/python.sh"
cronpilot_load_runtime
mkdir -p datas/logs
export FLASK_CONFIG="${FLASK_CONFIG:-development}"
"$CRONPILOT_VENV/bin/python" scripts/ensure_sqlite_tables.py
