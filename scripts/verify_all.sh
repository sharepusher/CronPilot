#!/usr/bin/env bash
# CronPilot 全量验收：本地（单测 + 安装链 + HTTP）+ Docker（镜像 + HTTP + flask db）
# 用法:
#   bash scripts/verify_all.sh              # 本地 + Docker
#   bash scripts/verify_all.sh --local-only
#   bash scripts/verify_all.sh --docker-only
#   bash scripts/verify_all.sh --with-compose   # 额外跑 docker compose（较慢）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# shellcheck source=smoke_http.sh
source "$ROOT/scripts/smoke_http.sh"

RUN_LOCAL=1
RUN_DOCKER=1
RUN_COMPOSE=0
for arg in "$@"; do
  case "$arg" in
    --local-only) RUN_DOCKER=0 ;;
    --docker-only) RUN_LOCAL=0 ;;
    --with-compose) RUN_COMPOSE=1 ;;
    -h|--help)
      sed -n '2,8p' "$0"
      exit 0
      ;;
    *)
      echo "未知参数: $arg" >&2
      exit 1
      ;;
  esac
done

PASS=0
FAIL=0
ok() { echo "PASS $1"; PASS=$((PASS + 1)); }
bad() { echo "FAIL $1"; FAIL=$((FAIL + 1)); }

section() {
  echo ""
  echo "=============================================="
  echo " $1"
  echo "=============================================="
}

if [[ "$RUN_LOCAL" -eq 1 ]]; then
  section "1. 本地单元测试"
  if bash scripts/cronpilot.sh test >/tmp/cronpilot_verify_test.log 2>&1; then
    ok "cronpilot.sh test (14 cases)"
  else
    bad "cronpilot.sh test"
    tail -5 /tmp/cronpilot_verify_test.log >&2
  fi

  section "2. 安装链路（verify_install_flow）"
  if bash scripts/verify_install_flow.sh >/tmp/cronpilot_verify_install.log 2>&1; then
    ok "verify_install_flow.sh"
  else
    bad "verify_install_flow.sh"
    tail -8 /tmp/cronpilot_verify_install.log >&2
  fi

  section "3. Tier 0 · flask db CLI"
  # shellcheck source=lib/python.sh
  source "$ROOT/scripts/lib/python.sh"
  cronpilot_load_runtime
  cp -f conf.ci.ini conf.ini
  export FLASK_CONFIG=development FLASK_APP=manage:app
  if "$CRONPILOT_VENV/bin/flask" db --help >/tmp/flask_db_help.log 2>&1; then
    ok "flask db --help"
  else
    bad "flask db --help"
    tail -3 /tmp/flask_db_help.log >&2
  fi

  section "4. 本地 HTTP 冒烟 (:5001)"
  LOCAL_PORT="${LOCAL_PORT:-5001}"
  LOCAL_BASE="http://127.0.0.1:${LOCAL_PORT}"
  export FLASK_CONFIG=development
  "$CRONPILOT_VENV/bin/python" -c "
from app import create_app
app = create_app('development')
app.run(host='127.0.0.1', port=${LOCAL_PORT}, debug=False, use_reloader=False)
" >/tmp/cronpilot_local_server.log 2>&1 &
  LOCAL_PID=$!
  sleep 6
  http_fail=0
  smoke_http_suite "$LOCAL_BASE" "ci-test-password" || http_fail=$?
  kill "$LOCAL_PID" 2>/dev/null || true
  wait "$LOCAL_PID" 2>/dev/null || true
  if [[ "$http_fail" -eq 0 ]]; then
    ok "local HTTP smoke (8 checks)"
  else
    bad "local HTTP smoke ($http_fail failed)"
    tail -20 /tmp/cronpilot_local_server.log >&2 || true
  fi
fi

if [[ "$RUN_DOCKER" -eq 1 ]]; then
  export PATH="/Applications/Docker.app/Contents/Resources/bin:${PATH:-/usr/bin:/bin}"
  if ! docker info >/dev/null 2>&1; then
    bad "docker daemon not reachable"
    echo "提示: 启动 Docker Desktop 后重试，或使用 --local-only" >&2
  else
    section "5. Docker 镜像构建与基础 HTTP"
    export SMOKE_LEVEL=full
    if bash "$ROOT/scripts/verify_cronpilot_docker_mac.sh" >/tmp/cronpilot_docker_verify.log 2>&1; then
      ok "verify_cronpilot_docker_mac.sh"
    else
      bad "verify_cronpilot_docker_mac.sh"
      tail -20 /tmp/cronpilot_docker_verify.log >&2
    fi
  fi
fi

if [[ "$RUN_COMPOSE" -eq 1 ]]; then
  section "6. docker compose（可选）"
  export PATH="/Applications/Docker.app/Contents/Resources/bin:${PATH:-/usr/bin:/bin}"
  if ! docker info >/dev/null 2>&1; then
    bad "docker compose (daemon unavailable)"
  else
    CRONPILOT_ROOT="$ROOT" VERIFY_CONF="$(mktemp /tmp/cronpilot-compose-verify.XXXXXX.ini)" python3 - <<'PY'
from configparser import ConfigParser
import os
from pathlib import Path
root = Path(os.environ["CRONPILOT_ROOT"])
out = Path(os.environ["VERIFY_CONF"])
cp = ConfigParser()
cp.read(root / "conf.ini.example", encoding="utf-8")
cp.set("default", "is_single", "1")
cp.set("default", "cron_db_url", "sqlite:////opt/cronpilot/datas/cron.sqlite")
cp.set("default", "cron_job_log_db_url", "sqlite:////opt/cronpilot/datas/job_log.sqlite")
cp.set("default", "login_pwd", "changeme")
with open(out, "w", encoding="utf-8") as f:
    cp.write(f)
with open(root / "conf.ini", "w", encoding="utf-8") as f:
    cp.write(f)
PY
    docker compose down 2>/dev/null || true
    if docker compose up -d --build >/tmp/cronpilot_compose.log 2>&1; then
      sleep 15
      docs_code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 http://127.0.0.1:5860/docs/ 2>/dev/null || echo "000")
      home_code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 -L http://127.0.0.1:5860/ 2>/dev/null || echo "000")
      docker compose down >/dev/null 2>&1 || true
      if [[ "$docs_code" == "200" && "$home_code" =~ ^(200|302)$ ]]; then
        ok "docker compose (docs=${docs_code}, home=${home_code})"
      else
        bad "docker compose (docs=${docs_code}, home=${home_code})"
      fi
    else
      bad "docker compose up"
      tail -15 /tmp/cronpilot_compose.log >&2
    fi
    cp -f conf.ci.ini conf.ini 2>/dev/null || true
  fi
fi

section "汇总"
echo " 通过: $PASS  失败: $FAIL"
if [[ "$FAIL" -eq 0 ]]; then
  echo "全部验收通过。"
  exit 0
fi
echo "存在失败项，请查看上方日志。" >&2
exit 1
