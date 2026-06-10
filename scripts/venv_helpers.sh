# venv 创建与修复（source 用）

cronpilot_venv_ok() {
  local venv="$1"
  [ -d "$venv" ] && [ -x "$venv/bin/python" ] && {
    [ -x "$venv/bin/pip" ] || [ -x "$venv/bin/pip3" ] || "$venv/bin/python" -m pip --version >/dev/null 2>&1
  }
}

cronpilot_create_venv() {
  local py="$1" venv="$2"
  if "$py" -m venv "$venv" 2>/dev/null; then return 0; fi
  echo "警告: $py -m venv 失败，请安装 python*-venv（如 python3.9-venv）" >&2
  "$py" -m venv --without-pip "$venv"
  "$venv/bin/python" -m ensurepip --upgrade
}

cronpilot_venv_pip() {
  local venv="$1"
  if [ -x "$venv/bin/pip" ]; then echo "$venv/bin/pip"
  elif [ -x "$venv/bin/pip3" ]; then echo "$venv/bin/pip3"
  else echo "$venv/bin/python -m pip"; fi
}

cronpilot_bootstrap_venv_deps() {
  local py="$1" venv="$2" pip
  if [ -d "$venv" ] && ! cronpilot_venv_ok "$venv"; then
    echo "警告: $venv 不完整，删除并重建…" >&2
    rm -rf "$venv"
  fi
  if [ ! -d "$venv" ]; then cronpilot_create_venv "$py" "$venv"; fi
  if ! cronpilot_venv_ok "$venv"; then
    echo "错误: 无法创建虚拟环境 $venv" >&2
    echo "  请执行: sudo apt-get install -y python3.9-venv python3-venv" >&2
    return 1
  fi
  pip=$(cronpilot_venv_pip "$venv")
  # shellcheck disable=SC2086
  $pip install -q --upgrade 'pip<25'
  # shellcheck disable=SC2086
  $pip install -q -r requirements-core.txt
}
