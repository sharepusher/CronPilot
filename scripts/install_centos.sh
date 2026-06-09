#!/bin/bash
# CronPilot — CentOS 7 / 8（及 RHEL、Rocky、Alma 兼容）一键安装
# 用法: sudo bash scripts/install_centos.sh [--production] [--sqlite]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PRODUCTION=0
USE_SQLITE=0
APP_USER="${SUDO_USER:-$USER}"
INSTALL_LABEL="CentOS/RHEL"
EXTRA_PATH=""

# shellcheck source=install_common.sh
source "$(dirname "$0")/install_common.sh"
# shellcheck source=os_detect.sh
source "$(dirname "$0")/os_detect.sh"

for arg in "$@"; do
  case "$arg" in
    --production) PRODUCTION=1 ;;
    --sqlite) USE_SQLITE=1 ;;
    -h|--help)
      echo "用法: sudo bash scripts/install_centos.sh [--production] [--sqlite]"
      echo "  支持 CentOS 7/8、RHEL 7/8、Rocky、AlmaLinux"
      echo "  --production  安装 requirements.txt（Gunicorn+gevent）"
      echo "  --sqlite      conf.ini 使用 SQLite（试用）"
      exit 0
      ;;
  esac
done

if [ "$(id -u)" -ne 0 ]; then
  echo "请使用 root: sudo bash scripts/install_centos.sh" >&2
  exit 1
fi

if ! cronpilot_is_rhel_family; then
  echo "警告: 未检测到 RHEL/CentOS 系，仍尝试 yum/dnf…" >&2
fi

install_centos7() {
  echo "==> CentOS 7：安装系统依赖（SCL Python 3.8）…"
  yum install -y epel-release
  yum install -y centos-release-scl || true
  yum install -y git gcc make libffi-devel openssl-devel
  yum install -y libev libev-devel || yum install -y libev-devel
  yum install -y rh-python38 rh-python38-python-devel rh-python38-python-pip
  EXTRA_PATH="/opt/rh/rh-python38/root/usr/bin"
  INSTALL_LABEL="CentOS 7"
}

install_centos8() {
  echo "==> CentOS 8 / Rocky / Alma：安装系统依赖（Python 3.9）…"
  if command -v dnf >/dev/null 2>&1; then
    PKG=dnf
  else
    PKG=yum
  fi
  $PKG install -y epel-release || true
  $PKG install -y git gcc make libffi-devel openssl-devel libev-devel
  # python39 在 AppStream；若无则尝试 python3.9 / python311
  $PKG install -y python39 python39-devel python39-pip 2>/dev/null \
    || $PKG install -y python3.9 python3.9-devel 2>/dev/null \
    || $PKG install -y python3 python3-devel
  INSTALL_LABEL="CentOS 8 / RHEL 8+"
}

if cronpilot_is_centos7; then
  install_centos7
  export CRONPILOT_PY_OVERRIDE=/opt/rh/rh-python38/root/usr/bin/python3.8
elif cronpilot_is_centos8; then
  install_centos8
  if command -v python3.9 >/dev/null 2>&1; then
    export CRONPILOT_PY_OVERRIDE=python3.9
  fi
else
  echo "==> RHEL 系（通用）：安装编译依赖与 Python…"
  if command -v dnf >/dev/null 2>&1; then
    dnf install -y git gcc make libffi-devel openssl-devel libev-devel python3 python3-devel python39 python39-devel 2>/dev/null || true
  else
    yum install -y epel-release git gcc make libffi-devel openssl-devel libev-devel
    yum install -y rh-python38 rh-python38-python-devel 2>/dev/null || yum install -y python3 python3-devel
    EXTRA_PATH="/opt/rh/rh-python38/root/usr/bin:${EXTRA_PATH}"
  fi
  INSTALL_LABEL="$(cronpilot_os_id) $(cronpilot_os_version)"
fi

cronpilot_install_app_python "$EXTRA_PATH"
cronpilot_install_conf_and_data

OS_HINT=""
if cronpilot_is_centos7; then
  OS_HINT="CentOS7 使用 SCL Python3.8；若命令找不到 python3.8，执行: scl enable rh-python38 bash"
elif cronpilot_is_rhel_family; then
  OS_HINT="防火墙: firewall-cmd --permanent --add-port=5860/tcp && firewall-cmd --reload；SELinux 异常时可查 audit.log"
fi

cronpilot_install_print_footer "$OS_HINT"
