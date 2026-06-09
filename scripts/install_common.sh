# CronPilot 安装收尾（Ubuntu / CentOS 共用，由 install_*.sh source）

cronpilot_install_app_python() {
  local extra_path="${1:-}"
  echo "==> 安装 Python 依赖（用户: $APP_USER）…"
  sudo -u "$APP_USER" bash <<EOSU
set -e
cd "$ROOT"
export PATH="${extra_path}:/opt/rh/rh-python38/root/usr/bin:/opt/rh/rh-python39/root/usr/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export PY="${CRONPILOT_PY_OVERRIDE:-}"
bash scripts/check_python_all.sh 2>/dev/null || bash scripts/check_python.sh || true
bash scripts/bootstrap_venv.sh
EOSU

  if [ "$PRODUCTION" -eq 1 ]; then
    echo "==> 安装生产依赖（gevent + gunicorn）…"
    sudo -u "$APP_USER" env PATH="${extra_path}:$PATH" bash -c "cd '$ROOT' && bash scripts/install_production_deps.sh"
  fi
}

cronpilot_install_conf_and_data() {
  if [ ! -f "$ROOT/conf.ini" ]; then
    echo "==> 生成 conf.ini …"
    cp "$ROOT/conf.ini.example" "$ROOT/conf.ini"
    chown "$APP_USER:$APP_USER" "$ROOT/conf.ini"
  fi

  if [ "$USE_SQLITE" -eq 1 ]; then
    echo "==> 配置 SQLite（单机试用）…"
    mkdir -p "$ROOT/datas/logs"
    chown -R "$APP_USER:$APP_USER" "$ROOT/datas"
    sudo -u "$APP_USER" bash <<EOSQL
set -e
cd "$ROOT"
source scripts/lib/python.sh
cronpilot_load_runtime
"\$CRONPILOT_VENV/bin/python" - <<'PY'
from configparser import ConfigParser
from pathlib import Path
root = Path("$ROOT")
cron = f"sqlite:////{root}/datas/cron.sqlite"
log = f"sqlite:////{root}/datas/job_log.sqlite"
cp = ConfigParser()
cp.read(root / "conf.ini", encoding="utf-8")
cp.set("default", "is_single", "1")
cp.set("default", "cron_db_url", cron)
cp.set("default", "cron_job_log_db_url", log)
cp.set("default", "login_pwd", "changeme")
with open(root / "conf.ini", "w", encoding="utf-8") as f:
    cp.write(f)
print("SQLite:", cron)
PY
EOSQL
  fi

  mkdir -p "$ROOT/datas/logs"
  chown -R "$APP_USER:$APP_USER" "$ROOT/datas" 2>/dev/null || true
}

cronpilot_install_print_footer() {
  local os_hint="${1:-}"
  echo ""
  echo "=============================================="
  echo " CronPilot 安装完成 ($INSTALL_LABEL)"
  echo "=============================================="
  echo " 目录: $ROOT"
  echo " 用户: $APP_USER"
  [ -n "$os_hint" ] && echo " 提示: $os_hint"
  echo ""
  echo "下一步（以 $APP_USER 执行）:"
  echo "  开发: bash scripts/start_local.sh"
  if [ "$PRODUCTION" -eq 1 ]; then
    echo "  生产: bash scripts/run_production.sh"
    echo "  systemd: sudo cp scripts/systemd/cronpilot.service.example /etc/systemd/system/cronpilot.service"
  else
    echo "  生产: sudo bash scripts/install_linux.sh --production --sqlite"
  fi
  echo "  测试: bash scripts/cronpilot.sh test"
  echo "=============================================="
}
