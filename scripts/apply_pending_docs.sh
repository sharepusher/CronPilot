#!/bin/bash
# 将 doc/_pending_sync/ 中文件覆盖到仓库（用于 root 属主文档）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PENDING="$ROOT/doc/_pending_sync"
if [ ! -d "$PENDING" ]; then
  echo "无待合并文件: $PENDING"
  exit 0
fi
if [ "$(id -u)" -ne 0 ]; then
  echo "请使用 sudo: sudo bash scripts/apply_pending_docs.sh" >&2
  exit 1
fi
cd "$PENDING"
find . -type f | while read -r f; do
  f="${f#./}"
  dest="$ROOT/$f"
  mkdir -p "$(dirname "$dest")"
  cp "$f" "$dest"
  echo "applied $f"
done
rm -rf "$PENDING"
echo "完成。建议: python3 scripts/html_docs_to_markdown.py --check"
