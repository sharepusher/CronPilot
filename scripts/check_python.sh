#!/bin/bash
# 检查本机是否具备可运行 CronPilot 的 Python 3.8–3.11
set -e
cd "$(dirname "$0")/.."
# shellcheck source=lib/python.sh
source "$(dirname "$0")/lib/python.sh"

echo "探测顺序: PY(若已设) → python3.11 → python3.10 → python3.9 → python3.8 → python3"
echo "---"
for cand in python3.11 python3.10 python3.9 python3.8 python3; do
  if command -v "$cand" >/dev/null 2>&1; then
    if cronpilot_python_ok "$cand"; then
      echo "OK   $cand  $($cand --version 2>&1)"
    else
      echo "SKIP $cand  $($cand --version 2>&1)  (不在 3.8–3.11)"
    fi
  else
    echo "MISS $cand"
  fi
done
echo "---"
PY=$(cronpilot_pick_python)
VENV=$(cronpilot_venv_dir "$PY")
echo "将选用: $PY"
echo "虚拟环境目录: $VENV"
