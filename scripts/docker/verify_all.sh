#!/bin/bash
# 在 Docker 中验证 Ubuntu + CentOS 7/8 完整安装流程（含 venv、SQLite、gunicorn）
# 用法: bash scripts/docker/verify_all.sh [ubuntu|centos8|centos7|all]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if ! command -v docker >/dev/null 2>&1; then
  echo "未找到 docker 命令，请先安装 Docker Desktop / docker-ce" >&2
  exit 1
fi

TARGET="${1:-all}"
FAIL=0

build_one() {
  local name="$1" dockerfile="$2" tag="$3"
  echo ""
  echo "========== Docker 验证: $name =========="
  if docker build -f "$dockerfile" -t "$tag" . ; then
    echo "OK  $name"
  else
    echo "FAIL $name" >&2
    FAIL=$((FAIL+1))
  fi
}

case "$TARGET" in
  ubuntu)
    build_one "Ubuntu 22.04" scripts/docker/Dockerfile.ubuntu cronpilot-verify-ubuntu
    ;;
  centos8)
    build_one "Rocky Linux 8 (CentOS8 路径)" scripts/docker/Dockerfile.centos8 cronpilot-verify-centos8
    ;;
  centos7)
    build_one "CentOS 7 (SCL python38)" scripts/docker/Dockerfile.centos7 cronpilot-verify-centos7
    ;;
  all)
    build_one "Ubuntu 22.04" scripts/docker/Dockerfile.ubuntu cronpilot-verify-ubuntu
    build_one "Rocky Linux 8" scripts/docker/Dockerfile.centos8 cronpilot-verify-centos8
    build_one "CentOS 7" scripts/docker/Dockerfile.centos7 cronpilot-verify-centos7
    ;;
  *)
    echo "用法: $0 [ubuntu|centos8|centos7|all]" >&2
    exit 1
    ;;
esac

echo ""
if [ "$FAIL" -eq 0 ]; then
  echo "全部 Docker 验证通过。"
else
  echo "$FAIL 个镜像构建/验证失败。" >&2
  exit 1
fi
