#!/bin/bash
# 重启生产 Gunicorn
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
bash "$ROOT/scripts/stop_production.sh"
exec bash "$ROOT/scripts/run_production.sh"
