# CronPilot Python 3.8–3.11 自动检测（默认无需设置 PY）

cronpilot_python_ok() {
  "$1" -c 'import sys; v = sys.version_info; raise SystemExit(0 if (3, 8) <= v[:2] <= (3, 11) else 1)' 2>/dev/null
}

# 按 3.11→3.10→3.9→3.8→python3 探测（跳过 3.12+）
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
  echo "未找到 Python 3.8–3.11。请安装 python3.8、3.9、3.10 或 3.11 之一。" >&2
  return 1
}

cronpilot_venv_dir() {
  local py="$1"
  local tag
  tag=$("$py" -c 'import sys; print(f"py{sys.version_info.major}{sys.version_info.minor}")')
  echo ".venv-${tag}"
}

# 若已有 .venv-py* 且 Python 可用，优先复用（避免重复建环境）
cronpilot_pick_existing_venv() {
  local d py
  for d in .venv-py311 .venv-py310 .venv-py39 .venv-py38; do
    py="$d/bin/python"
    if [ -x "$py" ] && cronpilot_python_ok "$py"; then
      echo "$d"
      return 0
    fi
  done
  return 1
}

# 输出两行：PY 路径、VENV 目录（自动匹配，一般无需 export PY）
cronpilot_resolve_runtime() {
  local py venv existing
  if existing=$(cronpilot_pick_existing_venv); then
    py="$existing/bin/python"
    venv="$existing"
  else
    py=$(cronpilot_pick_python)
    venv=$(cronpilot_venv_dir "$py")
  fi
  printf '%s\n%s\n' "$py" "$venv"
}

cronpilot_ensure_venv() {
  local py venv
  py=$(cronpilot_resolve_runtime | sed -n '1p')
  venv=$(cronpilot_resolve_runtime | sed -n '2p')
  if [ ! -d "$venv" ]; then
    "$py" -m venv "$venv"
    "$venv/bin/pip" install -q --upgrade pip
    "$venv/bin/pip" install -q -r requirements-core.txt
  fi
  printf '%s\n%s\n' "$py" "$venv"
}

# 兼容 bash 3.2（macOS）：设置全局 CRONPILOT_PY / CRONPILOT_VENV
cronpilot_load_runtime() {
  local lines
  lines=$(cronpilot_ensure_venv)
  CRONPILOT_PY=$(printf '%s\n' "$lines" | sed -n '1p')
  CRONPILOT_VENV=$(printf '%s\n' "$lines" | sed -n '2p')
}
