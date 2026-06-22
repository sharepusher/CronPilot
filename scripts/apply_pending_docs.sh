#!/usr/bin/env bash
# 仅合并 pending_apply.manifest 中登记的文件（由 sync_all_docs.py 在 PermissionError 时写入）。
# 不会盲目 cp 整个 doc/_pending_sync/，避免陈旧副本覆盖较新的主文档。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PENDING="$ROOT/doc/_pending_sync"
MANIFEST="$PENDING/pending_apply.manifest"
FORCE=0

for arg in "$@"; do
  case "$arg" in
    --force) FORCE=1 ;;
    -h|--help)
      sed -n '2,6p' "$0"
      echo "  --force  即使主文件比 pending 副本新也覆盖（慎用）"
      exit 0
      ;;
    *)
      echo "未知参数: $arg" >&2
      exit 1
      ;;
  esac
done

if [ ! -d "$PENDING" ]; then
  echo "无待合并目录: $PENDING"
  exit 0
fi

if [ ! -f "$MANIFEST" ]; then
  echo "无待合并清单: $MANIFEST"
  echo "说明: 仅有目录说明/归档文件时无需 apply；勿手动把主文档复制到本目录。"
  exit 0
fi

if [ "$(id -u)" -ne 0 ]; then
  echo "请使用 sudo: sudo bash scripts/apply_pending_docs.sh" >&2
  exit 1
fi

APPLIED=0
SKIPPED=0
REMAINING=()

while IFS= read -r rel || [ -n "${rel:-}" ]; do
  rel="${rel%%#*}"
  rel="$(echo "$rel" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
  [ -z "$rel" ] && continue

  case "$rel" in
    doc/_pending_sync/INDEX.md|doc/_pending_sync/已合并补丁记录.md|INDEX.md|已合并补丁记录.md)
      echo "SKIP (meta): $rel" >&2
      continue
      ;;
  esac

  src="$PENDING/$rel"
  dest="$ROOT/$rel"

  if [ ! -f "$src" ]; then
    echo "WARN: manifest 条目缺失文件，跳过: $rel" >&2
    REMAINING+=("$rel")
    continue
  fi

  if [ -f "$dest" ] && [ "$FORCE" -eq 0 ]; then
    if [ "$dest" -nt "$src" ]; then
      echo "SKIP (主文件较新): $rel" >&2
      echo "  → 删除陈旧副本 $src 并从 manifest 移除该行，避免日后误合并。" >&2
      rm -f "$src"
      SKIPPED=$((SKIPPED + 1))
      continue
    fi
  fi

  mkdir -p "$(dirname "$dest")"
  cp -f "$src" "$dest"
  rm -f "$src"
  echo "applied $rel"
  APPLIED=$((APPLIED + 1))
done < "$MANIFEST"

if [ "${#REMAINING[@]}" -gt 0 ]; then
  printf '%s\n' "${REMAINING[@]}" > "$MANIFEST"
else
  rm -f "$MANIFEST"
fi

echo "完成: applied=$APPLIED skipped_stale=$SKIPPED"
if [ "$APPLIED" -gt 0 ]; then
  echo "建议: python3 scripts/html_docs_to_markdown.py --check"
fi
