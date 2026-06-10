#!/bin/bash
# 一键修复：dpkg（保留 PostgreSQL）+ redis + 损坏 venv + 可选继续安装 CronPilot
#
# 用法:
#   sudo bash scripts/fix_broken_install.sh              # 只修复环境
#   sudo bash scripts/fix_broken_install.sh --install    # 修复后继续 install_linux（试用 SQLite）
#   sudo bash scripts/fix_broken_install.sh --purge-pg   # 不保留 PG，强制删除损坏的 postgresql 包
#
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
APP_USER="${SUDO_USER:-${USER:-root}}"
DO_INSTALL=0
PURGE_PG=0

for arg in "$@"; do
  case "$arg" in
    --install) DO_INSTALL=1 ;;
    --purge-pg) PURGE_PG=1 ;;
    -h|--help)
      sed -n '2,8p' "$0" | sed 's/^# \?//'
      exit 0
      ;;
  esac
done

if [ "$(id -u)" -ne 0 ]; then
  echo "请使用 root 运行: sudo bash scripts/fix_broken_install.sh" >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
FAILED=0

log() { echo ""; echo "==> $*"; }

# ---------- apt / dpkg：PostgreSQL（默认保留）----------
fix_postgresql_keep() {
  log "PostgreSQL：保留安装，只修 dpkg"

  if ! dpkg -l 2>/dev/null | grep -qE '^..[^ ]*.*postgresql'; then
    echo "  未检测到 postgresql 包，跳过"
    return 0
  fi

  if [ "$PURGE_PG" -eq 1 ]; then
    echo "  --purge-pg：移除 postgresql 包…"
    apt-get remove -y --purge 'postgresql-*' postgresql-common 2>/dev/null || true
    apt-get autoremove -y 2>/dev/null || true
    return 0
  fi

  mkdir -p /var/lib/postgresql /var/log/postgresql /etc/postgresql
  if ! id postgres &>/dev/null; then
    useradd -r -s /bin/bash -d /var/lib/postgresql -m postgres 2>/dev/null || true
  fi
  chown -R postgres:postgres /var/lib/postgresql /var/log/postgresql 2>/dev/null || true
  chmod 700 /var/lib/postgresql 2>/dev/null || true

  if command -v pg_lsclusters >/dev/null 2>&1; then
    echo "  当前集群:"
    pg_lsclusters 2>/dev/null || true
    while read -r ver name port status _; do
      [ -z "${ver:-}" ] && continue
      [[ "$ver" == Ver* ]] && continue
      if [ "${status:-}" != "online" ]; then
        echo "  尝试启动 $ver/$name …"
        pg_ctlcluster "$ver" "$name" start 2>/dev/null || true
      fi
    done < <(pg_lsclusters 2>/dev/null || true)
  fi

  for pkg in postgresql-client-common postgresql-common; do
    if dpkg -l "$pkg" 2>/dev/null | grep -qE '^..'; then
      echo "  配置 $pkg …"
      dpkg --configure "$pkg" 2>/dev/null || true
    fi
  done

  apt-get install -y -f 2>/dev/null || true
  apt-get install -y --reinstall postgresql-common 2>/dev/null || true

  while read -r pkg; do
    [ -z "$pkg" ] && continue
    echo "  配置 $pkg …"
    dpkg --configure "$pkg" 2>/dev/null || true
  done < <(dpkg -l 2>/dev/null | awk '/postgresql/ && $1 !~ /^ii/ {print $2}')

  dpkg --configure -a 2>/dev/null || true
  apt-get install -y -f 2>/dev/null || true

  if dpkg -l 2>/dev/null | awk '/postgresql/ {print $1}' | grep -qE '^i[^i]|^iU|^iF'; then
    echo "  警告: 仍有 postgresql 包未就绪:" >&2
    dpkg -l | grep postgresql | grep -v '^ii' >&2 || true
    echo "  可查看: tail -30 /var/log/dpkg.log" >&2
    echo "  或: bash -x /var/lib/dpkg/info/postgresql-common.postinst configure" >&2
    return 1
  fi
  echo "  PostgreSQL dpkg 已正常"
  pg_lsclusters 2>/dev/null || true
  return 0
}

# ---------- apt / dpkg：redis（CronPilot 单机可不装）----------
fix_redis_optional() {
  log "Redis：尝试修复 dpkg（单机试用 CronPilot 可不装 Redis）"

  if ! dpkg -l 2>/dev/null | grep -qE '^..[^ ]*.*redis'; then
    echo "  未检测到 redis 包，跳过"
    return 0
  fi

  for pkg in redis-server redis; do
    if dpkg -l "$pkg" 2>/dev/null | grep -qE '^..'; then
      dpkg --configure "$pkg" 2>/dev/null || true
    fi
  done
  apt-get install -y -f 2>/dev/null || true

  if dpkg -l 2>/dev/null | awk '/redis/ {print $1}' | grep -qE '^i[^i]|^iU|^iF'; then
    echo "  警告: redis 包仍异常（不影响 SQLite 单机 CronPilot）" >&2
    dpkg -l | grep redis | grep -v '^ii' >&2 || true
    return 1
  fi
  echo "  Redis dpkg 已正常"
  return 0
}

# ---------- apt / dpkg：全局收尾 ----------
fix_dpkg_global() {
  log "apt/dpkg 全局收尾"
  dpkg --configure -a 2>/dev/null || true
  apt-get install -y -f
}

# ---------- Python 3.8–3.11（缺则 apt 安装，失败才报错）----------
fix_python_apt() {
  log "安装 Python 3.8–3.11（含 venv）"
  if ! command -v apt-get >/dev/null 2>&1; then
    echo "  非 apt 系统，请手动安装 Python 3.8–3.11" >&2
    return 1
  fi
  bash "$ROOT/scripts/install_python_ubuntu.sh"
}

# ---------- 损坏的 .venv-py* ----------
fix_venv() {
  log "修复 CronPilot 虚拟环境（用户: $APP_USER）"

  for d in .venv-py39 .venv-py38 .venv-py310 .venv-py311; do
    if [ -d "$d" ]; then
      ok=0
      [ -x "$d/bin/python" ] && { [ -x "$d/bin/pip" ] || [ -x "$d/bin/pip3" ] || "$d/bin/python" -m pip --version >/dev/null 2>&1; } && ok=1
      if [ "$ok" -eq 0 ]; then
        echo "  删除不完整: $d"
        rm -rf "$d"
      fi
    fi
  done

  chown -R "$APP_USER:$APP_USER" "$ROOT" 2>/dev/null || true

  if ! sudo -u "$APP_USER" bash -c "cd '$ROOT' && bash scripts/bootstrap_venv.sh"; then
    echo "  venv 重建失败" >&2
    return 1
  fi
  echo "  venv 已就绪"
  return 0
}

# ---------- 主流程 ----------
log "CronPilot 环境一键修复（保留 PostgreSQL，除非 --purge-pg）"
echo "  项目目录: $ROOT"
echo "  部署用户: $APP_USER"

fix_postgresql_keep || FAILED=$((FAILED + 1))
fix_redis_optional || true
fix_dpkg_global || FAILED=$((FAILED + 1))
fix_python_apt || FAILED=$((FAILED + 1))
fix_venv || FAILED=$((FAILED + 1))

echo ""
echo "=============================================="
if [ "$FAILED" -eq 0 ]; then
  echo " 修复完成"
  echo "=============================================="
  echo "下一步:"
  if [ "$DO_INSTALL" -eq 1 ]; then
    echo "  继续安装 CronPilot…"
    bash "$ROOT/scripts/install_linux.sh" --production --sqlite
    echo ""
    echo "  安装完成，请执行: bash scripts/run_production.sh"
  else
    echo "  sudo bash scripts/install_linux.sh --production --sqlite"
    echo "  bash scripts/run_production.sh"
    echo ""
    echo "  或一条命令: sudo bash scripts/fix_broken_install.sh --install"
  fi
else
  echo " 部分步骤失败 ($FAILED)，请查看上方警告"
  echo "=============================================="
  exit 1
fi
