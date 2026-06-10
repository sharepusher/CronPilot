#!/bin/bash
# 创建/更新 venv 并安装 requirements-core.txt
set -e
cd "$(dirname "$0")/.."
# shellcheck source=lib/python.sh
source "$(dirname "$0")/lib/python.sh"
# shellcheck source=venv_helpers.sh
source "$(dirname "$0")/venv_helpers.sh"

export PATH="/opt/rh/rh-python38/root/usr/bin:/opt/rh/rh-python39/root/usr/bin:${PATH:-}"

if ! PY=$(cronpilot_pick_python); then
  echo "未找到 Python 3.8–3.11。请先安装（需 root）：" >&2
  echo "  sudo bash scripts/install_python_ubuntu.sh" >&2
  echo "  或: sudo bash scripts/fix_broken_install.sh --install" >&2
  exit 1
fi

VENV=$(cronpilot_venv_dir "$PY")
cronpilot_bootstrap_venv_deps "$PY" "$VENV"

echo "Python: $PY ($("$PY" --version 2>&1))"
echo "Venv:   $VENV"
echo "核心依赖已安装。"
echo "  开发: bash scripts/start_local.sh"
echo "  生产: bash scripts/install_production_deps.sh && bash scripts/run_production.sh"
