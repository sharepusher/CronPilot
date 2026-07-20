#!/usr/bin/env bash
# 黄金路径：docker compose + 宿主机 conf.ini volume → 登录 → cron_list 无 system error
# 用法: bash scripts/verify_docker_compose.sh [--rebuild] [--keep-running]
set -euo pipefail

export PATH="/Applications/Docker.app/Contents/Resources/bin:${PATH:-/usr/bin:/bin}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${CRONPILOT_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
cd "$ROOT"

# shellcheck source=smoke_http.sh
source "$SCRIPT_DIR/smoke_http.sh"

REBUILD=0
KEEP_RUNNING=0
WAIT_SECS="${WAIT_SECS:-120}"
BASE="${COMPOSE_BASE:-http://127.0.0.1:5860}"

for arg in "$@"; do
  case "$arg" in
    --rebuild) REBUILD=1 ;;
    --keep-running) KEEP_RUNNING=1 ;;
    -h|--help)
      echo "用法: bash scripts/verify_docker_compose.sh [--rebuild] [--keep-running]"
      exit 0
      ;;
    *)
      echo "未知参数: $arg" >&2
      exit 1
      ;;
esac
done

if ! docker info >/dev/null 2>&1; then
  # Docker Desktop on macOS often uses ~/.docker/run/docker.sock
  if [[ -S "${HOME}/.docker/run/docker.sock" ]]; then
    export DOCKER_HOST="unix://${HOME}/.docker/run/docker.sock"
  fi
fi
if ! docker info >/dev/null 2>&1; then
  echo "ERROR: Docker daemon not reachable" >&2
  echo "提示: 请先启动 Docker Desktop，然后重试本脚本。" >&2
  exit 1
fi

if [[ ! -f conf.ini ]]; then
  echo "=== conf.ini 不存在，生成 SQLite Docker 配置 ==="
  python3 "$ROOT/scripts/write_sqlite_conf.py" \
    --out "$ROOT/conf.ini" \
    --datas-dir "$ROOT/datas" \
    --container-paths \
    --template "$ROOT/conf.local.sqlite.example"
fi

if ! python3 "$ROOT/scripts/check_conf_production.py"; then
  echo "ERROR: 请先修正 conf.ini（勿使用 conf.ci.ini 的 :memory:）" >&2
  exit 1
fi

LOGIN_PWD="$(python3 - <<'PY'
import configparser
cp = configparser.ConfigParser()
cp.read('conf.ini', encoding='utf-8')
print(cp.get('default', 'login_pwd', fallback='changeme'))
PY
)"

mkdir -p datas/logs

echo "=== docker compose up ==="
if [[ "$REBUILD" -eq 1 ]]; then
  docker compose up --build -d
else
  docker compose up -d
fi

echo "=== wait for HTTP (up to ${WAIT_SECS}s) ==="
deadline=$((SECONDS + WAIT_SECS))
while (( SECONDS < deadline )); do
  docs_code=$(curl -sf -o /dev/null -w "%{http_code}" --connect-timeout 3 "$BASE/docs/" 2>/dev/null || echo "000")
  if [[ "$docs_code" == "200" ]]; then
    break
  fi
  sleep 2
done

if [[ "$docs_code" != "200" ]]; then
  echo "FAIL: /docs/ not ready (code=$docs_code)" >&2
  docker compose logs --tail 40
  [[ "$KEEP_RUNNING" -eq 0 ]] && docker compose down
  exit 1
fi

echo "=== ensure SQLite tables (container) ==="
docker compose exec -T cronpilot bash -c 'cd /opt/cronpilot && export FLASK_CONFIG=production && bash scripts/ensure_business_tables.sh'

echo "=== HTTP smoke (login + cron_list) ==="
ext_fail=0
smoke_http_suite "$BASE" "$LOGIN_PWD" || ext_fail=$?

echo "=== Framework Generation pins (Phase D3) ==="
  docker compose exec -T cronpilot bash -c \
    'cd /opt/cronpilot && source scripts/lib/python.sh && cronpilot_load_runtime && \
     "$CRONPILOT_VENV/bin/python" scripts/assert_framework_pins.py \
       --python "$CRONPILOT_VENV/bin/python" \
       --requirements /opt/cronpilot/requirements.txt' \
    || ext_fail=$((ext_fail + 1))

echo "=== gevent / gunicorn (container) ==="
  docker compose exec -T cronpilot bash -c 'cd /opt/cronpilot && source scripts/lib/python.sh && cronpilot_load_runtime && "$CRONPILOT_VENV/bin/python" -c "import gevent, gunicorn, apscheduler; print(gevent.__version__, gunicorn.__version__, apscheduler.__version__)"' || ext_fail=$((ext_fail + 1))

if [[ "$ext_fail" -ne 0 ]]; then
  echo "COMPOSE_VERIFY: FAIL ($ext_fail checks)" >&2
  docker compose logs --tail 50
  [[ "$KEEP_RUNNING" -eq 0 ]] && docker compose down
  exit 1
fi

echo "COMPOSE_VERIFY: OK"

if [[ "$KEEP_RUNNING" -eq 0 ]]; then
  docker compose down
  echo "CLEANUP: docker compose down"
else
  echo "KEEP: container still running at $BASE (password from conf.ini login_pwd)"
fi
