#!/bin/bash
# CronPilot 统一入口：自动匹配 Python 3.8–3.11，无需手动指定 PY
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# shellcheck source=lib/python.sh
source "$(dirname "$0")/lib/python.sh"

usage() {
  cat <<'USAGE'
用法: bash scripts/cronpilot.sh <命令>

命令（均自动选择 Python 3.8–3.11，无需 export PY）:
  start [--daemon|-d]   启动本地开发服务 (127.0.0.1:5001)
  stop                  停止本地开发服务
  restart [--daemon|-d] 先停后启（默认强制释放端口，解决旧进程占口）
  status                查看本地 / 生产端口占用
  install               创建/更新虚拟环境并安装核心依赖
  test                  运行 P0 单元测试
  check                 列出本机可用 Python 版本
  python                打印将使用的 Python 与 venv 路径
  exec <args...>        用项目 venv 执行命令

生产 Gunicorn (:5860):
  bash scripts/run_production.sh
  bash scripts/stop_production.sh
  bash scripts/restart_production.sh

仅当自动检测不符合预期时，可临时覆盖: PY=python3.9 bash scripts/cronpilot.sh start
USAGE
}

cmd="${1:-}"
shift || true

case "$cmd" in
  start)
    exec bash "$ROOT/scripts/start_local_full.sh" "$@"
    ;;
  stop)
    exec bash "$ROOT/scripts/stop_local.sh"
    ;;
  restart)
    exec bash "$ROOT/scripts/restart_local.sh" "$@"
    ;;
  status)
    exec bash "$ROOT/scripts/status.sh"
    ;;
  install)
    exec bash "$ROOT/scripts/install_core_deps.sh"
    ;;
  test)
    cronpilot_load_runtime
    export FLASK_CONFIG=development
    cp -n conf.ini.example conf.ini 2>/dev/null || true
    # 防护：测试前检查禁止 from manage import
    if grep -r "from manage import" "$ROOT/tests/" 2>/dev/null; then
      echo "FATAL: tests/ 中存在 'from manage import'，会破坏开发数据库。请改用 sqlite:///:memory:" >&2
      exit 1
    fi
    bash "$ROOT/scripts/check_pending_sync.sh"
    "$CRONPILOT_VENV/bin/python" -m unittest tests.test_p0_phase_a tests.test_cronpilot_sign tests.test_job_log_display tests.test_job_log_outcome tests.test_job_log_id tests.test_job_health tests.test_job_log_outcome_filter tests.test_check_conf_production tests.test_secret_key tests.test_single_task_lock tests.test_csrf tests.test_ensure_business_tables tests.test_rbac_phase tests.test_rbac_scope tests.test_ajax_form_guard tests.test_orm_legacy_guard tests.test_repositories_phase_b tests.test_mapped_model_guard tests.test_operation_log tests.test_cron_edit_status tests.test_cron_schedule_display tests.test_cron_run_now tests.test_scheduler_db tests.test_pagination tests.test_b1_execution_status tests.test_b2_timeout_config tests.test_api_scope_min tests.test_api_scope_s6 tests.test_form_name_guard tests.test_api_path_guard tests.test_registration tests.test_task_groups -v
    ;;
  check)
    exec bash "$ROOT/scripts/check_python.sh"
    ;;
  python)
    cronpilot_load_runtime
    echo "Python: $CRONPILOT_PY ($("$CRONPILOT_PY" --version 2>&1))"
    echo "Venv:   $CRONPILOT_VENV"
    ;;
  exec)
    if [ $# -eq 0 ]; then
      echo "cronpilot.sh exec: 缺少命令" >&2
      exit 1
    fi
    cronpilot_load_runtime
    exec "$CRONPILOT_VENV/bin/python" "$@"
    ;;
  -h|--help|help|'')
    usage
    ;;
  *)
    echo "未知命令: $cmd" >&2
    usage
    exit 1
    ;;
esac
