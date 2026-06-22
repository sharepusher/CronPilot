#!/usr/bin/env bash
# 将「先验收后文档」条款写入 root 拥有的 .cursor 规则文件（需 sudo 一次 chown）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RULES="$ROOT/.cursor/rules"
DOC="$RULES/cronpilot-documentation.mdc"
DEPLOY="$RULES/cronpilot-release-deploy.mdc"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "请使用 sudo 运行（用于 chown + 写入 root 拥有的规则文件）：" >&2
  echo "  sudo bash scripts/sync_optimization_rules.sh" >&2
  exit 1
fi

TARGET_USER="${SUDO_USER:-$USER}"
chown "$TARGET_USER:staff" "$DOC" "$DEPLOY" 2>/dev/null || chown "$TARGET_USER:$TARGET_USER" "$DOC" "$DEPLOY"

cd "$ROOT"
python3 <<'PY'
from pathlib import Path

rules = Path(".cursor/rules")

deploy = rules / "cronpilot-release-deploy.mdc"
text = deploy.read_text(encoding="utf-8")
old = """## 发布检查清单

- [ ] `unittest` 与 `html_docs_to_markdown.py --check` 本地通过
- [ ] `RELEASE_NOTES` 已更新；tag 指向含文档提交的 commit"""
new = """## 发布检查清单

- [ ] **先验收后文档**：`cronpilot.sh test` + `verify_golden_path.sh`（及 Docker/安装链路若相关）已通过
- [ ] `unittest` 与 `html_docs_to_markdown.py --check` 本地通过
- [ ] `RELEASE_NOTES` 与相关 `doc/*.html` 已更新；tag 指向含文档提交的 commit"""
if old in text and "**先验收后文档**" not in text:
    deploy.write_text(text.replace(old, new), encoding="utf-8")
    print("updated", deploy)
elif "**先验收后文档**" in text:
    print("skip (already updated)", deploy)
else:
    raise SystemExit(f"pattern not found in {deploy}")

doc = rules / "cronpilot-documentation.mdc"
text2 = doc.read_text(encoding="utf-8")
marker = "## 优化与文档顺序（强制）"
if marker not in text2:
    old2 = "修改 HTML 后 **必须** `--check` 通过再提交。"
    extra = """

## 优化与文档顺序（强制）

与 `cronpilot-project.mdc` 一致：**不得**在验收未通过时更新 Release/RFC/架构等「已交付」表述。

1. 实现改动（最小 diff）
2. 跑验收（见项目总则「优化验收」表）
3. **仅当全部通过后**：更新本表所列相关 HTML/MD
4. `python scripts/html_docs_to_markdown.py --check`

依赖 Tier、部署脚本、验收脚本变更时，同步 `doc/依赖升级RFC.html` 与 `AGENTS.md` 快速命令（若新增入口）。"""
    if old2 not in text2:
        raise SystemExit(f"pattern not found in {doc}")
    doc.write_text(text2.replace(old2, old2 + extra), encoding="utf-8")
    print("updated", doc)
else:
    print("skip (already updated)", doc)
PY

chown "$TARGET_USER:staff" "$DOC" "$DEPLOY" 2>/dev/null || chown "$TARGET_USER:$TARGET_USER" "$DOC" "$DEPLOY"
echo "OK: 规则文件已归还给 $TARGET_USER"
