#!/bin/bash
# 修复 root 属主文档并合入依赖升级 RFC 段落，然后校验 HTML↔MD 同步。
# 用法（需 sudo 改属主）:
#   sudo bash scripts/apply_pending_rfc_doc_sync.sh
#   bash scripts/apply_pending_rfc_doc_sync.sh --skip-chown   # 属主已正确时
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SKIP_CHOWN=0
if [[ "${1:-}" == "--skip-chown" ]]; then
  SKIP_CHOWN=1
fi

TARGET_USER="${SUDO_USER:-$(whoami)}"
DEPLOY_HTML="doc/非Docker部署指南.html"
README="README.md"

if [[ "$SKIP_CHOWN" -eq 0 ]]; then
  if [[ "$(id -u)" -ne 0 ]]; then
    echo "请使用 sudo 运行以修复属主: sudo bash scripts/apply_pending_rfc_doc_sync.sh" >&2
    exit 1
  fi
  chown "$TARGET_USER":"$(id -gn "$TARGET_USER")" "$DEPLOY_HTML" "$README"
  echo "已 chown → $TARGET_USER: $DEPLOY_HTML $README"
fi

python3 <<'PY'
from pathlib import Path

root = Path(".")

deploy = root / "doc/非Docker部署指南.html"
text = deploy.read_text(encoding="utf-8")

old_py = '<tr><td>Python</td><td><strong>3.8～3.11</strong></td><td>勿用 3.12+（Flask 1.1 / gevent 20 易失败）</td></tr>'
new_py = '<tr><td>Python</td><td><strong>3.8～3.11</strong></td><td>勿用 3.12+（当前 gevent 20 栈；升级见 <a href="依赖升级RFC.html">依赖升级 RFC</a> Tier 2）</td></tr>'
if old_py not in text:
    raise SystemExit("未找到预期 Python 行片段，请手动对照 doc/非Docker部署指南.html §2 与 doc/_pending_sync/已合并补丁记录.md 批次 A3")
text = text.replace(old_py, new_py, 1)

old_gevent = '<tr><td><code>pip install gevent</code> 失败</td><td>换 3.8–3.11 中另一版本；本地先用 <code>bash scripts/start_local.sh</code>（core 依赖）</td></tr>'
new_gevent = '''<tr><td><code>pip install gevent</code> 失败</td><td>换 3.9/3.10；或本地用 <code>bash scripts/start_local.sh</code>（core 依赖）。长期方案：<a href="依赖升级RFC.html">依赖升级 RFC</a> Tier 2</td></tr>
      <tr><td><code>manage.py db</code> / Py3.11 报错</td><td>Flask-Script 与 3.11 不兼容；用 3.10 或完成 RFC <strong>Tier 0</strong>（<code>flask db</code>）</td></tr>'''
if old_gevent not in text:
    raise SystemExit("未找到 gevent FAQ 行")
text = text.replace(old_gevent, new_gevent, 1)

old_docs = '        <li><a href="架构设计文档.html">架构设计文档</a>（部署拓扑、集群）</li>'
new_docs = '''        <li><a href="依赖升级RFC.html">依赖升级 RFC</a>（Tier 0～4 分层路线、与 RBAC 排期）</li>
        <li><a href="架构设计文档.html">架构设计文档</a>（部署拓扑、集群）</li>'''
if old_docs not in text:
    raise SystemExit("未找到相关文档列表锚点")
text = text.replace(old_docs, new_docs, 1)
deploy.write_text(text, encoding="utf-8")
print(f"已更新 {deploy}")

readme = root / "README.md"
rt = readme.read_text(encoding="utf-8")
old_r = "| Python | **3.8～3.11**（勿用 3.12+，与 Flask 1.1 / gevent 20 不兼容） |"
new_r = "| Python | **3.8～3.11**（勿用 3.12+；gevent 20 栈见 [doc/依赖升级RFC.html](doc/依赖升级RFC.html) Tier 2） |"
if old_r not in rt:
    raise SystemExit("未找到 README Python 行")
rt = rt.replace(old_r, new_r, 1)
readme.write_text(rt, encoding="utf-8")
print(f"已更新 {readme}")
PY

# 选用项目 venv 若存在
PY=python3
for v in .venv-py311 .venv-py310 .venv-py39 .venv-py38; do
  if [[ -x "$ROOT/$v/bin/python" ]]; then
    PY="$ROOT/$v/bin/python"
    break
  fi
done

"$PY" scripts/html_docs_to_markdown.py
"$PY" scripts/html_docs_to_markdown.py --check
echo "完成：非 Docker 部署指南、README 已合入 RFC 段落，文档同步校验通过。"
