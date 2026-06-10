#!/bin/bash
# Ubuntu/Debian：安装 Python 3.8–3.11（含 venv），直到可用为止
# 必须 root: sudo bash scripts/install_python_ubuntu.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=lib/python.sh
source "$ROOT/scripts/lib/python.sh"

if [ "$(id -u)" -ne 0 ]; then
  echo "请使用 root: sudo bash scripts/install_python_ubuntu.sh" >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive

cronpilot_has_usable_python() {
  local cand
  for cand in python3.11 python3.10 python3.9 python3.8; do
    if command -v "$cand" >/dev/null 2>&1 && cronpilot_python_ok "$cand"; then
      # 还需要能建 venv：对应 *-venv 或 python3-venv
      if "$cand" -m venv --help >/dev/null 2>&1; then
        echo "$cand"
        return 0
      fi
    fi
  done
  return 1
}

if picked=$(cronpilot_has_usable_python 2>/dev/null); then
  echo "已有可用 Python: $picked ($($picked --version 2>&1))"
  exit 0
fi

echo "==> 未找到 Python 3.8–3.11，开始通过 apt 安装…"

apt-get update
apt-get install -y software-properties-common curl ca-certificates

# deadsnakes（Ubuntu 16.04/18.04 等需要）
if ! add-apt-repository -y ppa:deadsnakes/ppa 2>/dev/null; then
  echo "警告: 无法添加 deadsnakes PPA，仍尝试系统源…" >&2
fi
apt-get update

apt-get install -y \
  build-essential libffi-dev libev-dev \
  python3-venv python3-dev python3-pip

try_install_version() {
  local minor="$1"
  local py="python3.${minor}"
  echo ""
  echo "==> 安装 ${py} + ${py}-venv + ${py}-dev …"
  if ! apt-get install -y "${py}" "${py}-venv" "${py}-dev"; then
    echo "  apt 安装 ${py} 失败，尝试下一版本…" >&2
    return 1
  fi
  if ! command -v "$py" >/dev/null 2>&1; then
    echo "  命令 ${py} 不存在" >&2
    return 1
  fi
  if ! cronpilot_python_ok "$py"; then
    echo "  ${py} 版本不在 3.8–3.11: $($py --version 2>&1)" >&2
    return 1
  fi
  if ! "$py" -m venv /tmp/cronpilot-venv-test-"$$" 2>/dev/null; then
    rm -rf "/tmp/cronpilot-venv-test-$$"
    echo "  ${py} 无法创建 venv，请确认已安装 ${py}-venv" >&2
    return 1
  fi
  rm -rf "/tmp/cronpilot-venv-test-$$"
  echo "  OK: $py $($py --version 2>&1)"
  return 0
}

INSTALLED=""
for minor in 9 10 11 8; do
  if try_install_version "$minor"; then
    INSTALLED="python3.${minor}"
    break
  fi
done

if [ -z "$INSTALLED" ]; then
  echo "" >&2
  echo "错误: 无法安装 Python 3.8–3.11。" >&2
  echo "  请检查: apt-get update 是否正常、dpkg 是否损坏（先运行 fix_broken_install.sh）" >&2
  echo "  Ubuntu 16.04 建议: sudo apt-get install -y python3.9 python3.9-venv python3.9-dev" >&2
  exit 1
fi

echo ""
echo "Python 安装完成: $INSTALLED"
echo "后续 venv 将使用: $(cronpilot_venv_dir "$INSTALLED")"
