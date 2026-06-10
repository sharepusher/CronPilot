#!/bin/bash
# CronPilot — Ubuntu 20.04 / 22.04 / 24.04 一键安装（非 Docker）
# 用法: sudo bash scripts/install_ubuntu.sh [--production] [--sqlite]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PRODUCTION=0
USE_SQLITE=0
APP_USER="${SUDO_USER:-$USER}"
APP_HOME="$(eval echo "~$APP_USER")"

for arg in "$@"; do
  case "$arg" in
    --production) PRODUCTION=1 ;;
    --sqlite) USE_SQLITE=1 ;;
    -h|--help)
      echo "用法: sudo bash scripts/install_ubuntu.sh [--production] [--sqlite]"
      echo "  --production  安装 requirements.txt（Gunicorn+gevent）"
      echo "  --sqlite      conf.ini 使用 SQLite（无需 MySQL，适合试用）"
      exit 0
      ;;
  esac
done

if [ "$(id -u)" -ne 0 ]; then
  echo "请使用 root 安装系统包: sudo bash scripts/install_ubuntu.sh" >&2
  exit 1
fi

if [ ! -f /etc/os-release ] || ! grep -qi ubuntu /etc/os-release; then
  echo "警告: 未检测到 Ubuntu，仍尝试继续…" >&2
fi

echo "==> 安装系统依赖…"
export DEBIAN_FRONTEND=noninteractive

# 修复半安装 dpkg（常见：redis-server 未 configure 导致后续 apt 异常）
echo "==> 检查 apt/dpkg 状态…"
dpkg --configure -a 2>/dev/null || true
apt-get install -y -f -qq 2>/dev/null || true

UBUNTU_VER=""
if [ -f /etc/os-release ]; then
  # shellcheck disable=SC1091
  . /etc/os-release
  UBUNTU_VER="${VERSION_ID:-}"
fi
if [ "$UBUNTU_VER" = "18.04" ]; then
  echo "提示: Ubuntu 18.04 已 EOL，建议 20.04+；将尝试通过 deadsnakes 安装 Python 3.8/3.9…" >&2
fi

apt-get update -qq
apt-get install -y -qq software-properties-common
add-apt-repository -y ppa:deadsnakes/ppa 2>/dev/null || true
apt-get update -qq 2>/dev/null || true

# 核心编译依赖（必须成功）
apt-get install -y -qq \
  git curl \
  build-essential \
  libffi-dev libev-dev \
  python3-venv python3-dev python3-pip

# 多版本 Python（按发行版可用性安装，须带 *-venv 否则无法建虚拟环境）
for pkg in \
  python3.11 python3.11-venv python3.11-dev \
  python3.10 python3.10-venv python3.10-dev \
  python3.9 python3.9-venv python3.9-dev \
  python3.8 python3.8-venv python3.8-dev; do
  apt-get install -y -qq "$pkg" 2>/dev/null || true
done

# 若系统 redis 包损坏，不阻塞 CronPilot（单机 is_single=1 可不装 Redis）
if dpkg -l redis-server 2>/dev/null | grep -q '^..r'; then
  echo "警告: redis-server 处于异常状态，尝试修复（CronPilot 单机试用可不依赖 Redis）…" >&2
  apt-get install -y -f -qq 2>/dev/null || true
fi

# 以部署用户执行 Python 部分（避免 root 创建 venv）
echo "==> 安装 Python 依赖（用户: $APP_USER）…"
sudo -u "$APP_USER" bash <<EOSU
set -e
cd "$ROOT"
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export PY="${CRONPILOT_PY_OVERRIDE:-${PY:-}}"
bash scripts/check_python_all.sh 2>/dev/null || bash scripts/check_python.sh || true
bash scripts/bootstrap_venv.sh
EOSU

if [ "$PRODUCTION" -eq 1 ]; then
  echo "==> 安装生产依赖（gevent + gunicorn）…"
  sudo -u "$APP_USER" bash -c "cd '$ROOT' && bash scripts/install_production_deps.sh"
fi

if [ ! -f "$ROOT/conf.ini" ]; then
  echo "==> 生成 conf.ini …"
  cp "$ROOT/conf.ini.example" "$ROOT/conf.ini"
  chown "$APP_USER:$APP_USER" "$ROOT/conf.ini"
fi

if [ "$USE_SQLITE" -eq 1 ]; then
  echo "==> 配置 SQLite（单机试用）…"
  DATA_DIR="$ROOT/datas"
  mkdir -p "$DATA_DIR/logs"
  chown -R "$APP_USER:$APP_USER" "$DATA_DIR"
  sudo -u "$APP_USER" bash <<EOSQL
set -e
cd "$ROOT"
# shellcheck source=lib/python.sh
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

echo ""
echo "=============================================="
echo " CronPilot Ubuntu 安装完成"
echo "=============================================="
echo " 目录: $ROOT"
echo " 用户: $APP_USER"
echo ""
echo "下一步（以 $APP_USER 执行）:"
echo "  开发: bash scripts/cronpilot.sh start"
if [ "$PRODUCTION" -eq 1 ]; then
  echo "  生产: bash scripts/run_production.sh"
  echo "  或:   sudo cp scripts/systemd/cronpilot.service.example /etc/systemd/system/cronpilot.service"
  echo "        sudo systemctl enable --now cronpilot"
else
  echo "  生产依赖: sudo bash scripts/install_ubuntu.sh --production --sqlite"
fi
echo "  测试:   bash scripts/cronpilot.sh test"
echo "=============================================="
