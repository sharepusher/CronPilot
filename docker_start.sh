#!/bin/bash
# 兼容旧 Supervisor 入口；新镜像请直接使用 scripts/run_production.sh
set -e
cd "$(dirname "$0")"
exec bash scripts/run_production.sh
