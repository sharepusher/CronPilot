#!/bin/bash
# CronPilot — 自动识别 Ubuntu / CentOS 7·8 并安装
# 用法: sudo bash scripts/install_linux.sh [--production] [--sqlite]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=os_detect.sh
source "$(dirname "$0")/os_detect.sh"

ARGS=("$@")
if [ ${#ARGS[@]} -eq 0 ]; then
  ARGS=()
fi

if cronpilot_is_ubuntu; then
  echo "检测到 Ubuntu/Debian → install_ubuntu.sh"
  exec bash "$ROOT/scripts/install_ubuntu.sh" "${ARGS[@]}"
fi

if cronpilot_is_rhel_family; then
  echo "检测到 CentOS/RHEL 系 → install_centos.sh"
  exec bash "$ROOT/scripts/install_centos.sh" "${ARGS[@]}"
fi

echo "未识别的 Linux 发行版。请手动执行:" >&2
echo "  Ubuntu: bash scripts/install_ubuntu.sh" >&2
echo "  CentOS: bash scripts/install_centos.sh" >&2
echo "  或分步: bash scripts/bootstrap_venv.sh" >&2
exit 1
