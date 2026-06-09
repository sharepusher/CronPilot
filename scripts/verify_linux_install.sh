#!/bin/bash
# 本地验证 Ubuntu/CentOS 安装脚本（无需 root、无需真实 yum/apt）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PASS=0
FAIL=0

ok() { echo "PASS $1"; PASS=$((PASS+1)); }
bad() { echo "FAIL $1"; FAIL=$((FAIL+1)); }

echo "=== 1. bash -n 语法检查 ==="
for f in scripts/install_linux.sh scripts/install_centos.sh scripts/install_common.sh \
  scripts/os_detect.sh scripts/check_python_all.sh scripts/bootstrap_venv.sh \
  scripts/install_ubuntu.sh scripts/patch_readme_linux.sh scripts/merge_release_notes_linux.sh; do
  if bash -n "$f" 2>/dev/null; then ok "syntax $f"
  else bad "syntax $f"; fi
done

echo ""
echo "=== 2. os_detect 发行版识别（函数 mock）==="
source "$ROOT/scripts/os_detect.sh"

MOCK_ID=""
MOCK_VER=""
mock_os() {
  MOCK_ID="$1"
  MOCK_VER="$2"
  cronpilot_os_id() { echo "$MOCK_ID"; }
  cronpilot_os_version() { echo "$MOCK_VER"; }
}

expect_ubuntu() {
  mock_os "$1" "$2"
  if ! cronpilot_is_ubuntu; then bad "detect $1 -> ubuntu"; return; fi
  if cronpilot_is_rhel_family; then bad "$1 should not be rhel"; return; fi
  ok "detect $1 -> ubuntu"
}

expect_centos7() {
  mock_os centos 7
  cronpilot_is_rhel_family || { bad "centos7 rhel"; return; }
  cronpilot_is_centos7 || { bad "centos7 c7"; return; }
  cronpilot_is_centos8 && bad "centos7 not c8" && return
  ok "detect centos 7"
}

expect_centos8() {
  mock_os "$1" "$2"
  cronpilot_is_rhel_family || { bad "$1 rhel"; return; }
  cronpilot_is_centos8 || { bad "$1 c8"; return; }
  ok "detect $1 $2 -> centos8"
}

expect_ubuntu ubuntu 22.04
expect_ubuntu debian 12
expect_centos7
expect_centos8 centos 8
expect_centos8 rocky 8.6

echo ""
echo "=== 3. install_linux 路由 ==="
route() {
  mock_os "$1" "$2"
  if cronpilot_is_ubuntu; then echo ubuntu
  elif cronpilot_is_rhel_family; then echo centos
  else echo unknown; fi
}
[ "$(route ubuntu 22.04)" = ubuntu ] && ok "route ubuntu" || bad "route ubuntu"
[ "$(route centos 7)" = centos ] && ok "route centos7" || bad "route centos7"
[ "$(route rocky 8.6)" = centos ] && ok "route rocky8" || bad "route rocky8"

echo ""
echo "=== 4. CentOS 安装脚本关键逻辑 ==="
grep -q 'rh-python38' scripts/install_centos.sh && ok "centos7 SCL python38" || bad "centos7 SCL"
grep -q 'python39' scripts/install_centos.sh && ok "centos8 python39" || bad "centos8 python39"
grep -q 'CRONPILOT_PY_OVERRIDE' scripts/install_centos.sh && ok "PY override" || bad "PY override"
grep -q 'install_common.sh' scripts/install_centos.sh && ok "centos uses install_common" || bad "install_common"

echo ""
echo "=== 5. bootstrap SCL PATH ==="
grep -q 'rh-python38' scripts/bootstrap_venv.sh && ok "bootstrap SCL path" || bad "bootstrap SCL"

echo ""
echo "=== 6. 文档与 INSTALL.md ==="
for d in "doc/linux安装与运行.md" "doc/ubuntu安装与运行.md" "doc/centos安装与运行.md" INSTALL.md; do
  [ -f "$d" ] && ok "exists $d" || bad "missing $d"
done

echo ""
echo "=== 7. README / RELEASE_NOTES 合并状态 ==="
if grep -q 'install_linux.sh' README.md 2>/dev/null; then ok "README has install_linux"
else echo "WARN README 未合并（需 sudo bash scripts/patch_readme_linux.sh）"; fi
if grep -q 'Linux 安装与运行' RELEASE_NOTES.md 2>/dev/null; then ok "RELEASE_NOTES has linux section"
else echo "WARN RELEASE_NOTES 未合并（需 sudo bash scripts/merge_release_notes_linux.sh）"; fi

echo ""
echo "=== 8. 单元测试 ==="
if bash scripts/cronpilot.sh test >/tmp/cronpilot_test.log 2>&1; then ok "unit tests (14)"
else bad "unit tests"; tail -5 /tmp/cronpilot_test.log; fi

echo ""
echo "=============================================="
echo " 通过: $PASS  失败: $FAIL"
echo "=============================================="
[ "$FAIL" -eq 0 ]
