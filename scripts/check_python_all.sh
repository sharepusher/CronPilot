#!/bin/bash
# 检查 Python 3.8–3.11（含 CentOS SCL 路径）
set -e
cd "$(dirname "$0")/.."
export PATH="/opt/rh/rh-python38/root/usr/bin:/opt/rh/rh-python39/root/usr/bin:${PATH:-}"
# shellcheck source=lib/python.sh
source "$(dirname "$0")/lib/python.sh"
# shellcheck source=os_detect.sh
source "$(dirname "$0")/os_detect.sh"

echo "探测: PY → python3.11…3.8 → SCL rh-python38/39 → python3"
echo "---"
for cand in python3.11 python3.10 python3.9 python3.8 \
  /opt/rh/rh-python38/root/usr/bin/python3.8 \
  /opt/rh/rh-python39/root/usr/bin/python3.9 \
  python3; do
  if command -v "$cand" >/dev/null 2>&1; then
    if cronpilot_python_ok "$cand"; then
      echo "OK   $cand  $($cand --version 2>&1)"
    else
      echo "SKIP $cand  $($cand --version 2>&1)"
    fi
  else
    echo "MISS $cand"
  fi
done
if cronpilot_is_rhel_family; then
  echo "提示: CentOS7 需 yum install rh-python38 (centos-release-scl)"
fi
echo "---"
PY=$(cronpilot_pick_python)
echo "将选用: $PY → $(cronpilot_venv_dir "$PY")"
