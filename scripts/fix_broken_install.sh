#!/bin/bash
# 修复安装中断：dpkg/redis 异常 + 不完整 .venv-py*
# 用法: sudo bash scripts/fix_broken_install.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
APP_USER="${SUDO_USER:-${USER:-admin}}"

echo "==> 1. 修复 apt/dpkg（redis-server 等半安装包）"
export DEBIAN_FRONTEND=noninteractive
dpkg --configure -a || true
apt-get install -y -f

echo "==> 2. 安装 Python venv 支持包"
apt-get install -y python3-venv python3-pip \
  python3.9-venv python3.8-venv 2>/dev/null || true

echo "==> 3. 删除不完整虚拟环境并重建"
for d in .venv-py39 .venv-py38 .venv-py310 .venv-py311; do
  if [ -d "$d" ] && [ ! -x "$d/bin/pip" ] && [ ! -x "$d/bin/pip3" ]; then
    echo "  移除损坏目录: $d"
    rm -rf "$d"
  fi
done

echo "==> 4. 以用户 $APP_USER 重建 venv"
sudo -u "$APP_USER" bash -c "cd '$ROOT' && bash scripts/bootstrap_venv.sh"

echo ""
echo "完成。若仍失败，请执行:"
echo "  python3.9 -m venv /tmp/test-venv && /tmp/test-venv/bin/pip --version"
echo "  若 venv 失败: sudo apt-get install -y python3.9-venv"
