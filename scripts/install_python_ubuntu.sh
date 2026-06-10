#!/bin/bash
# Ubuntu/Debian：安装 Python 3.8–3.11（含 venv），直到可用为止
# 必须 root: sudo bash scripts/install_python_ubuntu.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=lib/python.sh
source "$ROOT/scripts/lib/python.sh"

if [ "$(id -u)" -ne 0 ]; then
  echo "错误: 请使用 sudo 运行（apt 需要 root）" >&2
  echo "  sudo bash scripts/install_python_ubuntu.sh" >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive

OS_VER=""
if [ -f /etc/os-release ]; then
  # shellcheck disable=SC1091
  . /etc/os-release
  OS_VER="${VERSION_ID:-unknown}"
  echo "系统: ${PRETTY_NAME:-Linux} (${OS_VER})"
fi

cronpilot_has_usable_python() {
  local cand
  for cand in python3.11 python3.10 python3.9 python3.8; do
    if command -v "$cand" >/dev/null 2>&1 && cronpilot_python_ok "$cand"; then
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

echo "==> 未找到 Python 3.8–3.11，通过 apt 安装…"

if [ "$OS_VER" = "16.04" ]; then
  echo "提示: Ubuntu 16.04 默认源没有 python3.8，必须先添加 deadsnakes PPA"
fi

apt-get update
apt-get install -y software-properties-common apt-transport-https ca-certificates curl \
  || apt-get install -y python-software-properties 2>/dev/null || true

echo "==> 添加 deadsnakes PPA（提供 python3.8 / 3.9 / 3.10 / 3.11）…"
if ! add-apt-repository -y ppa:deadsnakes/ppa; then
  echo "错误: 无法添加 PPA deadsnakes/ppa。请检查网络或 apt 源。" >&2
  exit 1
fi

apt-get update

apt-get install -y \
  build-essential libffi-dev libev-dev \
  python3-venv python3-dev python3-pip

try_install_version() {
  local minor="$1"
  local py="python3.${minor}"
  echo ""
  echo "==> 安装 ${py} ${py}-venv ${py}-dev …"
  if ! apt-get install -y "${py}" "${py}-venv" "${py}-dev"; then
    echo "  ${py} 不可用，尝试下一版本…" >&2
    return 1
  fi
  if ! command -v "$py" >/dev/null 2>&1; then
    echo "  命令 ${py} 不存在" >&2
    return 1
  fi
  if ! cronpilot_python_ok "$py"; then
    echo "  ${py} 版本不符: $($py --version 2>&1)" >&2
    return 1
  fi
  local testdir="/tmp/cronpilot-venv-test-$$"
  if ! "$py" -m venv "$testdir"; then
    rm -rf "$testdir"
    echo "  ${py} 无法建 venv，请确认已装 ${py}-venv" >&2
    return 1
  fi
  rm -rf "$testdir"
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
  echo "" >&2
  echo "常见原因:" >&2
  echo "  1. 未加 deadsnakes PPA（Ubuntu 16.04 直接 apt install python3.8 会报 Unable to locate package）" >&2
  echo "  2. dpkg 损坏 — 先: sudo bash scripts/fix_broken_install.sh" >&2
  echo "" >&2
  echo "手动重试:" >&2
  echo "  sudo add-apt-repository -y ppa:deadsnakes/ppa" >&2
  echo "  sudo apt-get update" >&2
  echo "  sudo apt-get install -y python3.9 python3.9-venv python3.9-dev" >&2
  exit 1
fi

echo ""
echo "Python 安装完成: $INSTALLED"
echo "后续 venv: $(cronpilot_venv_dir "$INSTALLED")"
