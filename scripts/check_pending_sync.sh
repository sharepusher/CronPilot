#!/usr/bin/env bash
# 校验 doc/_pending_sync：目录说明与根 README 待合并副本不得混淆，禁止孤立陈旧副本入库。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
exec python3 "$ROOT/scripts/check_pending_sync.py"
