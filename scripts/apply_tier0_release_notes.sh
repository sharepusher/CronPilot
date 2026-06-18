#!/bin/bash
# 修复 RELEASE_NOTES 属主并写入 Tier 0（Flask-Script → flask db）变更说明。
# 用法: sudo bash scripts/apply_tier0_release_notes.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

TARGET_USER="${SUDO_USER:-$(whoami)}"
if [[ "$(id -u)" -ne 0 ]]; then
  echo "请使用 sudo 运行: sudo bash scripts/apply_tier0_release_notes.sh" >&2
  exit 1
fi
chown "$TARGET_USER":"$(id -gn "$TARGET_USER")" RELEASE_NOTES.md doc/RELEASE_NOTES.html doc/RELEASE_NOTES.md 2>/dev/null || \
  chown "$TARGET_USER":"$(id -gn "$TARGET_USER")" RELEASE_NOTES.md doc/RELEASE_NOTES.html

python3 <<'PY'
from pathlib import Path

unreleased_md = """## [Unreleased]

### 依赖升级 · Tier 0

| 变更 | 说明 |
|------|------|
| 退役 Flask-Script | `manage.py` 改用 Flask 内置 `flask db`（Click 注册 Migrate 子命令） |
| `requirements.txt` | 移除 `Flask-Script==2.0.6` |
| `requirements-core.txt` | 增加 `Flask-Migrate`、`alembic==1.4.3` 等迁移依赖 |

用法：

```bash
export FLASK_APP=manage:app
flask db migrate -m "描述"
flask db upgrade
```

试用配置可 `cp conf.ci.ini conf.ini`（SQLite 内存库，无需 MySQL）。

---

"""

root_md = Path("RELEASE_NOTES.md")
text = root_md.read_text(encoding="utf-8")
marker = "## [0.1.1]"
if "## [Unreleased]" not in text:
    if marker not in text:
        raise SystemExit("RELEASE_NOTES.md 结构异常")
    text = text.replace("---\n\n" + marker, "---\n\n" + unreleased_md + marker, 1)
    root_md.write_text(text, encoding="utf-8")
    print("已更新 RELEASE_NOTES.md")
else:
    print("RELEASE_NOTES.md 已有 [Unreleased]，跳过")

html = Path("doc/RELEASE_NOTES.html")
ht = html.read_text(encoding="utf-8")
unreleased_html = """
  <h2 class="new">[Unreleased] · 依赖升级 Tier 0</h2>
  <div class="card highlight">
    <p>退役 Flask-Script；迁移 CLI 改为 <code>flask db</code>（Python 3.11 可用）。<strong>无 API 协议变更。</strong></p>
  </div>
  <table>
    <tr><th>变更</th><th>说明</th></tr>
    <tr><td>Flask-Script 移除</td><td><code>manage.py</code> 注册 Click <code>db</code> 子命令</td></tr>
    <tr><td><code>requirements-core.txt</code></td><td>锁定 <code>Flask-Migrate</code>、<code>alembic==1.4.3</code></td></tr>
  </table>
  <pre>export FLASK_APP=manage:app
flask db migrate -m "描述"
flask db upgrade</pre>
  <p>详 <a href="依赖升级RFC.html">依赖升级 RFC</a> Tier 0。</p>

  <hr style="border:none;border-top:1px solid var(--border);margin:2.5rem 0">

"""
if "[Unreleased]" not in ht:
    anchor = '  <h2 class="new">[0.1.1] — 2026-06-01</h2>'
    if anchor not in ht:
        raise SystemExit("RELEASE_NOTES.html 结构异常")
    ht = ht.replace(anchor, unreleased_html.strip() + "\n\n" + anchor, 1)
    html.write_text(ht, encoding="utf-8")
    print("已更新 doc/RELEASE_NOTES.html")
else:
    print("doc/RELEASE_NOTES.html 已有 Unreleased，跳过")

# doc/RELEASE_NOTES.md 与根目录保持同步（若存在）
doc_md = Path("doc/RELEASE_NOTES.md")
if doc_md.exists():
    doc_md.write_text(root_md.read_text(encoding="utf-8"), encoding="utf-8")
    print("已同步 doc/RELEASE_NOTES.md")
PY

echo "完成：Release Notes Tier 0 条目已写入。"
