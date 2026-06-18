#!/usr/bin/env bash
# CronPilot 全量验收：单测 + 黄金路径 + Docker（可选全新空库）
# 用法:
#   bash scripts/verify_all.sh                    # 本地 + Docker
#   bash scripts/verify_all.sh --local-only
#   bash scripts/verify_all.sh --docker-only
#   bash scripts/verify_all.sh --with-compose       # docker compose 冒烟
#   bash scripts/verify_all.sh --docker-fresh      # compose + 空 datas 断言
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# shellcheck source=smoke_http.sh
source "$ROOT/scripts/smoke_http.sh"

RUN_LOCAL=1
RUN_DOCKER=1
RUN_COMPOSE=0
RUN_DOCKER_FRESH=0
CONF_BACKUP=""
DATAS_BACKUP=""
RESTORE_CONF=0
RESTORE_DATAS=0

for arg in "$@"; do
  case "$arg" in
    --local-only) RUN_DOCKER=0 ;;
    --docker-only) RUN_LOCAL=0 ;;
    --with-compose) RUN_COMPOSE=1 ;;
    --docker-fresh) RUN_COMPOSE=1; RUN_DOCKER_FRESH=1 ;;
    -h|--help)
      sed -n '2,10p' "$0"
      exit 0
      ;;
    *)
      echo "未知参数: $arg" >&2
      exit 1
      ;;
  esac
done

verify_all_cleanup() {
  bash "$ROOT/scripts/stop_local.sh" 2>/dev/null || true
  if [[ "$RESTORE_CONF" -eq 1 && -n "$CONF_BACKUP" && -f "$CONF_BACKUP" ]]; then
    cp -f "$CONF_BACKUP" "$ROOT/conf.ini"
  fi
  if [[ "$RESTORE_DATAS" -eq 1 && -n "$DATAS_BACKUP" && -d "$DATAS_BACKUP" ]]; then
    rm -rf "$ROOT/datas"
    mv "$DATAS_BACKUP" "$ROOT/datas"
  fi
  docker compose down 2>/dev/null || true
}
trap verify_all_cleanup EXIT

if [[ -f conf.ini ]]; then
  CONF_BACKUP="$(mktemp /tmp/cronpilot-verify-conf.XXXXXX)"
  cp conf.ini "$CONF_BACKUP"
  RESTORE_CONF=1
fi

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
  export FLASK_CONFIG=development FLASK_APP=manage:app
  if "$CRONPILOT_VENV/bin/flask" db --help >/tmp/flask_db_help.log 2>&1; then
    ok "flask db --help"
  else
    bad "flask db --help"
    tail -3 /tmp/flask_db_help.log >&2
  fi

  section "4. 黄金路径（restart ×2 + 登录 + cron_list）"
  if bash "$ROOT/scripts/verify_golden_path.sh" >/tmp/cronpilot_golden.log 2>&1; then
    ok "verify_golden_path.sh"
    grep -E '^  URL:|^  password:' /tmp/cronpilot_golden.log || true
  else
    bad "verify_golden_path.sh"
    tail -25 /tmp/cronpilot_golden.log >&2
  fi
fi

if [[ "$RUN_DOCKER" -eq 1 ]]; then
  export PATH="/Applications/Docker.app/Contents/Resources/bin:${PATH:-/usr/bin:/bin}"
  if ! docker info >/dev/null 2>&1; then
    bad "docker daemon not reachable"
    echo "提示: 启动 Docker Desktop 后重试，或使用 --local-only" >&2
  else
    section "5. Docker 镜像构建与扩展 HTTP"
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
  section "6. docker compose"
  export PATH="/Applications/Docker.app/Contents/Resources/bin:${PATH:-/usr/bin:/bin}"
  if ! docker info >/dev/null 2>&1; then
    bad "docker compose (daemon unavailable)"
  else
    if [[ "$RUN_DOCKER_FRESH" -eq 1 && -d datas ]]; then
      DATAS_BACKUP="${ROOT}/datas.bak.verify.$$"
      mv datas "$DATAS_BACKUP"
      RESTORE_DATAS=1
      mkdir -p datas/logs
    fi

    # shellcheck source=lib/python.sh
    source "$ROOT/scripts/lib/python.sh"
    cronpilot_load_runtime
    "$CRONPILOT_VENV/bin/python" "$ROOT/scripts/write_sqlite_conf.py" \
      --out "$ROOT/conf.ini" \
      --datas-dir "$ROOT/datas" \
      --login-pwd changeme \
      --template "$ROOT/conf.local.sqlite.example"
    RESTORE_CONF=1
    bash "$ROOT/scripts/ensure_sqlite_tables.sh"

    docker compose down 2>/dev/null || true
    if docker compose up -d --build >/tmp/cronpilot_compose.log 2>&1; then
      sleep 15
      docs_code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 http://127.0.0.1:5860/docs/ 2>/dev/null || echo "000")
      home_code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 -L http://127.0.0.1:5860/ 2>/dev/null || echo "000")
      compose_fail=0
      if [[ "$docs_code" == "200" && "$home_code" =~ ^(200|302)$ ]]; then
        echo "PASS compose HTTP (docs=${docs_code}, home=${home_code})"
      else
        bad "docker compose HTTP (docs=${docs_code}, home=${home_code})"
        compose_fail=1
      fi

      if [[ "$RUN_DOCKER_FRESH" -eq 1 ]]; then
        count=$(sqlite3 "$ROOT/datas/job_log.sqlite" "SELECT COUNT(*) FROM cron_infos;" 2>/dev/null || echo "ERR")
        if [[ "$count" == "0" ]]; then
          echo "PASS docker-fresh empty DB (cron_infos=0)"
        else
          bad "docker-fresh expected cron_infos=0, got $count"
          compose_fail=1
        fi
        fail_smoke=0
        smoke_http_suite "http://127.0.0.1:5860" "changeme" || fail_smoke=$?
        if [[ "$fail_smoke" -eq 0 ]]; then
          echo "PASS docker-fresh login smoke"
        else
          bad "docker-fresh login smoke"
          compose_fail=1
        fi
      fi

      if [[ "$compose_fail" -eq 0 ]]; then
        ok "docker compose"
        echo "  Docker URL:      http://127.0.0.1:5860/"
        echo "  Docker password: changeme"
      fi
    else
      bad "docker compose up"
      tail -15 /tmp/cronpilot_compose.log >&2
    fi
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
