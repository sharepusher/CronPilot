# CronPilot Python 3.8–3.11 检测（被 start_local.sh / install_core_deps.sh source）

cronpilot_python_ok() {
  "$1" -c 'import sys; v = sys.version_info; raise SystemExit(0 if (3, 8) <= v[:2] <= (3, 11) else 1)' 2>/dev/null
}

# 优先使用环境变量 PY；否则按 3.11→3.8→python3 探测
cronpilot_pick_python() {
  if [ -n "${PY:-}" ]; then
    if command -v "$PY" >/dev/null 2>&1 && cronpilot_python_ok "$PY"; then
      echo "$PY"
      return 0
    fi
    echo "PY=$PY 不可用或版本不在 3.8–3.11" >&2
    return 1
  fi
  local cand
  for cand in python3.11 python3.10 python3.9 python3.8 python3; do
    if command -v "$cand" >/dev/null 2>&1 && cronpilot_python_ok "$cand"; then
      echo "$cand"
      return 0
    fi
  done
  echo "未找到 Python 3.8–3.11。请安装其一，或: export PY=python3.10" >&2
  return 1
}

cronpilot_venv_dir() {
  local py="$1"
  local tag
  tag=$("$py" -c 'import sys; print(f"py{sys.version_info.major}{sys.version_info.minor}")')
  echo ".venv-${tag}"
}
