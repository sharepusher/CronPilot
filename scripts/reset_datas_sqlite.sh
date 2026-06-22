#!/usr/bin/env bash
# 仅清除 datas 下运行时 SQLite / 状态文件，保留 datas/model、datas/utils 等 Python 包。
# 用法:
#   bash scripts/reset_datas_sqlite.sh
#   bash scripts/reset_datas_sqlite.sh --backup /tmp/cronpilot-sqlite-bak
#   bash scripts/reset_datas_sqlite.sh --restore /tmp/cronpilot-sqlite-bak
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATAS="${DATAS_DIR:-$ROOT/datas}"
BACKUP_DIR=""
RESTORE_DIR=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --backup)
      shift
      BACKUP_DIR="${1:?--backup requires directory}"
      ;;
    --restore)
      shift
      RESTORE_DIR="${1:?--restore requires directory}"
      ;;
    -h|--help)
      sed -n '2,7p' "$0"
      exit 0
      ;;
    *)
      echo "未知参数: $1" >&2
      exit 1
      ;;
  esac
  shift
done

mkdir -p "$DATAS/logs"

backup_sqlite() {
  local dest="$1"
  mkdir -p "$dest"
  shopt -s nullglob
  local copied=0
  for f in "$DATAS"/*.sqlite "$DATAS"/*.db "$DATAS"/*.pid; do
    [[ -e "$f" ]] || continue
    cp -f "$f" "$dest/"
    copied=1
  done
  if [[ "$copied" -eq 0 ]]; then
    echo "提示: $DATAS 下无可备份的 SQLite/状态文件"
  else
    echo "OK: 已备份 SQLite/状态文件 -> $dest"
  fi
}

restore_sqlite() {
  local src="$1"
  if [[ ! -d "$src" ]]; then
    echo "警告: 备份目录不存在，跳过恢复: $src" >&2
    return 0
  fi
  shopt -s nullglob
  local restored=0
  for f in "$src"/*.sqlite "$src"/*.db "$src"/*.pid; do
    [[ -e "$f" ]] || continue
    cp -f "$f" "$DATAS/"
    restored=1
  done
  if [[ "$restored" -eq 0 ]]; then
    echo "提示: $src 下无 SQLite/状态文件可恢复"
  else
    echo "OK: 已恢复 SQLite/状态文件 <- $src"
  fi
}

clear_sqlite() {
  shopt -s nullglob
  local removed=0
  for f in "$DATAS"/*.sqlite "$DATAS"/*.db "$DATAS"/*.pid; do
    [[ -e "$f" ]] || continue
    rm -f "$f"
    removed=1
  done
  if [[ "$removed" -eq 0 ]]; then
    echo "OK: $DATAS 下无 SQLite/状态文件需清除（已保留 model/utils/logs）"
  else
    echo "OK: 已清除 $DATAS 下 SQLite/状态文件（保留 model/utils/logs）"
  fi
}

if [[ -n "$RESTORE_DIR" ]]; then
  restore_sqlite "$RESTORE_DIR"
  exit 0
fi

if [[ -n "$BACKUP_DIR" ]]; then
  backup_sqlite "$BACKUP_DIR"
fi

clear_sqlite
