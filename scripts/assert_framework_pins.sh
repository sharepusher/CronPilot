#!/usr/bin/env bash
# Phase D3：断言当前 CronPilot venv 的 Framework pin 与 requirements.txt 一致
# 用法: bash scripts/assert_framework_pins.sh
#       PY=python3.10 bash scripts/assert_framework_pins.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"
# shellcheck source=lib/python.sh
source "$SCRIPT_DIR/lib/python.sh"
cronpilot_load_runtime
exec "$CRONPILOT_VENV/bin/python" "$ROOT/scripts/assert_framework_pins.py" \
  --python "$CRONPILOT_VENV/bin/python" \
  --requirements "$ROOT/requirements.txt"
