#!/bin/bash
# 端到端验证安装流程：Python 探测 → venv → 依赖 → 启动脚本（无需 root / yum / apt）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PASS=0
FAIL=0

ok() { echo "PASS $1"; PASS=$((PASS+1)); }
bad() { echo "FAIL $1"; FAIL=$((FAIL+1)); }

echo "=== A. Python / venv 解析 ==="
# shellcheck source=lib/python.sh
source "$ROOT/scripts/lib/python.sh"
cronpilot_load_runtime
[ -n "$CRONPILOT_PY" ] && [ -x "$CRONPILOT_PY" ] && ok "CRONPILOT_PY=$CRONPILOT_PY" || bad "CRONPILOT_PY"
[ -n "$CRONPILOT_VENV" ] && ok "CRONPILOT_VENV=$CRONPILOT_VENV" || bad "CRONPILOT_VENV"
[ -d "$CRONPILOT_VENV" ] && [ -x "$CRONPILOT_VENV/bin/python" ] && ok "venv exists" || bad "venv missing"

echo ""
echo "=== B. bootstrap_venv.sh（幂等）==="
bash scripts/bootstrap_venv.sh >/tmp/bootstrap.log 2>&1 && ok "bootstrap_venv" || { bad "bootstrap_venv"; tail -3 /tmp/bootstrap.log; }
"$CRONPILOT_VENV/bin/python" -c "import flask, pymysql" 2>/dev/null && ok "core deps flask+pymysql" || bad "core deps"

echo ""
echo "=== C. install_common 链路（source 检查）==="
grep -q 'bootstrap_venv.sh' scripts/install_common.sh && ok "install_common -> bootstrap" || bad "install_common bootstrap"
grep -q 'install_production_deps.sh' scripts/install_common.sh && ok "install_common -> production deps" || bad "install_common prod"
grep -q 'check_python_all.sh' scripts/install_common.sh && ok "install_common -> check_python_all" || bad "install_common check"

echo ""
echo "=== D. 生产依赖与启动脚本 ==="
if "$CRONPILOT_VENV/bin/python" -c "import gevent" 2>/dev/null; then
  ok "gevent in venv"
else
  echo "SKIP gevent (macOS 常未装，Linux 上 install_production_deps.sh 会装)"
fi
[ -x "$CRONPILOT_VENV/bin/gunicorn" ] 2>/dev/null && ok "gunicorn in venv" || echo "SKIP gunicorn (需 install_production_deps.sh)"
bash -n scripts/run_production.sh && ok "run_production syntax" || bad "run_production"
grep -q 'CRONPILOT_VENV' scripts/run_production.sh && ok "run_production uses venv" || bad "run_production venv"

echo ""
echo "=== E. install_linux / ubuntu / centos 调用链 ==="
grep -q 'install_ubuntu.sh' scripts/install_linux.sh && ok "linux->ubuntu" || bad "linux->ubuntu"
grep -q 'install_centos.sh' scripts/install_linux.sh && ok "linux->centos" || bad "linux->centos"
grep -q 'install_common.sh' scripts/install_centos.sh && ok "centos->install_common" || bad "centos->common"
grep -q 'bootstrap_venv.sh' scripts/install_ubuntu.sh && ok "ubuntu->bootstrap" || bad "ubuntu->bootstrap"

echo ""
echo "=== F. SQLite 配置逻辑（dry-run）==="
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
cp conf.ini.example "$TMP/conf.ini"
"$CRONPILOT_VENV/bin/python" - <<PY
from configparser import ConfigParser
from pathlib import Path
root = Path("$TMP")
cron = f"sqlite:////{root}/datas/cron.sqlite"
log = f"sqlite:////{root}/datas/job_log.sqlite"
cp = ConfigParser()
cp.read(root / "conf.ini", encoding="utf-8")
cp.set("default", "is_single", "1")
cp.set("default", "cron_db_url", cron)
cp.set("default", "cron_job_log_db_url", log)
with open(root / "conf.ini", "w", encoding="utf-8") as f:
    cp.write(f)
text = (root / "conf.ini").read_text()
assert "sqlite" in text and "is_single" in text
print("sqlite conf OK")
PY
ok "sqlite conf.ini generation"

echo ""
echo "=== G. cronpilot.sh 入口 ==="
bash scripts/cronpilot.sh python | grep -q 'Venv:' && ok "cronpilot.sh python" || bad "cronpilot.sh python"
bash scripts/cronpilot.sh test >/tmp/test.log 2>&1 && ok "cronpilot.sh test" || { bad "cronpilot.sh test"; tail -3 /tmp/test.log; }

echo ""
echo "=============================================="
echo " 通过: $PASS  失败: $FAIL"
echo "=============================================="
[ "$FAIL" -eq 0 ]
