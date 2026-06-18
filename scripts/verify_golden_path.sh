#!/usr/bin/env bash
# 黄金路径验收：隔离 SQLite 配置 → 双次 restart → 登录 → cron_list 无 system err
# 用法: bash scripts/verify_golden_path.sh [--keep-conf]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# shellcheck source=smoke_http.sh
source "$ROOT/scripts/smoke_http.sh"
# shellcheck source=process.sh
source "$ROOT/scripts/process.sh"

KEEP_CONF=0
for arg in "$@"; do
  case "$arg" in
    --keep-conf) KEEP_CONF=1 ;;
    -h|--help)
      echo "用法: bash scripts/verify_golden_path.sh [--keep-conf]"
      exit 0
      ;;
    *)
      echo "未知参数: $arg" >&2
      exit 1
      ;;
  esac
done

LOCAL_PORT="${LOCAL_PORT:-5001}"
LOCAL_BASE="http://127.0.0.1:${LOCAL_PORT}"
LOGIN_PWD="verify-golden-test"
VERIFY_DATAS="$(mktemp -d /tmp/cronpilot-golden-datas.XXXXXX)"
CONF_BACKUP=""
CONF_WAS_MISSING=0

cleanup() {
  bash "$ROOT/scripts/stop_local.sh" 2>/dev/null || true
  if [[ "$KEEP_CONF" -eq 0 && -n "$CONF_BACKUP" ]]; then
    if [[ "$CONF_WAS_MISSING" -eq 1 ]]; then
      rm -f "$ROOT/conf.ini"
    else
      cp -f "$CONF_BACKUP" "$ROOT/conf.ini"
    fi
    rm -f "$CONF_BACKUP"
  fi
  rm -rf "$VERIFY_DATAS"
}
trap cleanup EXIT

if [[ -f conf.ini ]]; then
  CONF_BACKUP="$(mktemp /tmp/cronpilot-conf-backup.XXXXXX)"
  cp conf.ini "$CONF_BACKUP"
else
  CONF_WAS_MISSING=1
  CONF_BACKUP="$(mktemp /tmp/cronpilot-conf-backup.XXXXXX)"
fi

# shellcheck source=lib/python.sh
source "$ROOT/scripts/lib/python.sh"
cronpilot_load_runtime

"$CRONPILOT_VENV/bin/python" "$ROOT/scripts/write_sqlite_conf.py" \
  --out "$ROOT/conf.ini" \
  --datas-dir "$VERIFY_DATAS" \
  --login-pwd "$LOGIN_PWD" \
  --template "$ROOT/conf.local.sqlite.example"

export FLASK_CONFIG=development
bash "$ROOT/scripts/ensure_sqlite_tables.sh"

echo "=== golden: double restart ==="
bash "$ROOT/scripts/restart_local.sh" --daemon
sleep 2
bash "$ROOT/scripts/restart_local.sh" --daemon
sleep 2

if ! cronpilot_listen_pids "$LOCAL_PORT" | grep -q .; then
  echo "FAIL: local server not listening on $LOCAL_PORT" >&2
  tail -20 "$ROOT/datas/logs/local-server.log" 2>/dev/null || true
  exit 1
fi

echo "=== golden: login → cron_list ==="
fail=0
smoke_http_suite "$LOCAL_BASE" "$LOGIN_PWD" || fail=$?

count=$("$CRONPILOT_VENV/bin/python" -c "
from app import create_app
from datas.model.cron_infos import CronInfos
app = create_app('development')
with app.app_context():
    print(CronInfos.query.count())
" 2>/dev/null || echo "ERR")
if [[ "$count" != "0" ]]; then
  echo "FAIL: expected 0 cron_infos in isolated DB, got $count" >&2
  fail=$((fail + 1))
else
  echo "PASS isolated DB empty (cron_infos=0)"
fi

if [[ "$fail" -ne 0 ]]; then
  echo "GOLDEN_PATH: FAIL" >&2
  exit 1
fi
echo "GOLDEN_PATH: OK"
echo "  URL:      $LOCAL_BASE"
echo "  password: $LOGIN_PWD (isolated verify only)"
