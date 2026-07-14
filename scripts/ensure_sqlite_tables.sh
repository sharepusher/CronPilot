#!/bin/bash
# 兼容旧入口：转发到 ensure_business_tables.sh
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
echo "NOTE: ensure_sqlite_tables.sh → ensure_business_tables.sh（旧名仍可用）" >&2
exec bash "$ROOT/scripts/ensure_business_tables.sh" "$@"
