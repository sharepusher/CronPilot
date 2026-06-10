#!/bin/bash
# 修复安装中断：dpkg/redis 异常 + 不完整 .venv-py*
# 用法: sudo bash scripts/fix_broken_install.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
APP_USER="${SUDO_USER:-${USER:-admin}}"

echo "==> 1. 修复 apt/dpkg（半安装包：redis / postgresql 等）"
export DEBIAN_FRONTEND=noninteractive

# CronPilot 只需 MySQL 或 SQLite，不需要 PostgreSQL / Redis
if dpkg -l 2>/dev/null | grep -qE '^..r.*(postgresql|redis)'; then
  echo "提示: 检测到损坏的 postgresql/redis 包，CronPilot 不依赖它们"
fi

dpkg --configure -a 2>/dev/null || true
apt-get install -y -f 2>/dev/null || true

# PostgreSQL 9.x 在 Ubuntu 16.04 上常见 postgresql-common 配置失败
if dpkg -l postgresql-common 2>/dev/null | grep -q '^..r'; then
  echo "==> 尝试修复 postgresql-common…"
  mkdir -p /var/lib/postgresql
  id postgres &>/dev/null && chown postgres:postgres /var/lib/postgresql 2>/dev/null || true
  apt-get install -y --reinstall postgresql-common 2>/dev/null || true
  dpkg --configure -a 2>/dev/null || true
fi
if dpkg -l 2>/dev/null | grep -qE '^..r.*postgresql'; then
  echo "==> postgresql 仍异常，移除相关包（不影响 CronPilot）…"
  apt-get remove -y --purge \
    'postgresql-*' postgresql-common 2>/dev/null || true
  apt-get autoremove -y 2>/dev/null || true
fi

dpkg --configure -a 2>/dev/null || true
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
