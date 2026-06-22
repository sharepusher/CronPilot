#!/bin/bash
# 补全合并时未正确更新的 非Docker部署指南 与 index.html（需 sudo）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
python3 scripts/sync_all_docs.py
# 仅当 manifest 存在时合并（避免盲目覆盖主文档）
if [ -f doc/_pending_sync/pending_apply.manifest ]; then
  sudo bash scripts/apply_pending_docs.sh
fi
# 强制修补 非Docker / index.html（若仍缺 install_linux）
if ! grep -q "install_linux.sh" doc/非Docker部署指南.md 2>/dev/null; then
  python3 <<'PY'
from pathlib import Path
p = Path("doc/非Docker部署指南.md")
t = p.read_text(encoding="utf-8")
old = """### 3.1 获取代码与虚拟环境

```
git clone git@github.com:sharepusher/CronPilot.git
cd CronPilot

bash scripts/check_python.sh
bash scripts/install_core_deps.sh"""
new = """### 3.1 Linux 一键安装（Ubuntu / CentOS 7·8，推荐）

自动创建 `.venv-py*`。生产 MySQL：`sudo bash scripts/install_linux.sh --production`；试用 SQLite：加 `--sqlite`。

速查：[INSTALL.md](../INSTALL.md) · [linux安装与运行.md](linux安装与运行.md)

```
git clone git@github.com:sharepusher/CronPilot.git
cd CronPilot
sudo bash scripts/install_linux.sh --production
bash scripts/run_production.sh
```

### 3.2 手动安装（macOS）

```
bash scripts/cronpilot.sh install
bash scripts/install_production_deps.sh"""
if old not in t:
    raise SystemExit("非Docker部署指南.md 段落未匹配，请手动编辑")
p.write_text(t.replace(old, new, 1), encoding="utf-8")
print("fixed 非Docker部署指南.md")
PY
fi
if ! grep -q "linux安装与运行" doc/index.html 2>/dev/null; then
  python3 <<'PY'
from pathlib import Path
p = Path("doc/index.html")
card = '''    <div class="card featured" style="border-color:#059669">
      <h2><a href="linux安装与运行.md">Linux 安装与运行（Ubuntu + CentOS）</a></h2>
      <p><span class="tag">运维</span><span class="tag">venv</span></p>
      <p>install_linux.sh、MySQL/SQLite、Docker 验收。</p>
      <p class="formats"><a href="linux安装与运行.md">总览</a><a href="../INSTALL.md">INSTALL</a></p>
    </div>
'''
t = p.read_text(encoding="utf-8")
needle = '    <div class="card featured" style="border-color:#ea580c">'
if "linux安装与运行" in t:
    print("skip index.html")
elif needle not in t:
    raise SystemExit("index.html 锚点未找到")
p.write_text(t.replace(needle, card + needle, 1), encoding="utf-8")
print("fixed index.html")
PY
fi
echo "补全完成。"
