#!/bin/bash
# 在 README.md「非 Docker 部署」章节加入 Linux 一键安装说明
# 用法: sudo bash scripts/patch_readme_linux.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
README="$ROOT/README.md"

if grep -q "install_linux.sh" "$README" 2>/dev/null; then
  echo "README.md 已包含 install_linux.sh，跳过。"
  exit 0
fi

python3 - <<'PY'
from pathlib import Path
readme = Path("README.md")
text = readme.read_text(encoding="utf-8")
old = """### 安装

```bash
git clone https://github.com/sharepusher/CronPilot.git
cd CronPilot

bash scripts/check_python.sh"""
new = """### 安装

**Linux 一键安装（Ubuntu / CentOS 7·8）：** 见 [INSTALL.md](INSTALL.md)

```bash
git clone https://github.com/sharepusher/CronPilot.git
cd CronPilot
sudo bash scripts/install_linux.sh --production --sqlite
bash scripts/run_production.sh
```

**手动安装（macOS 或自定义环境）：**

```bash
git clone https://github.com/sharepusher/CronPilot.git
cd CronPilot

bash scripts/check_python.sh"""
if old not in text:
    raise SystemExit("README 安装段落未找到，请手动合并 INSTALL.md 链接")
text = text.replace(old, new, 1)
fw_old = """### 防火墙

```bash
sudo ufw allow 5860/tcp
```"""
fw_new = """### 防火墙

**Ubuntu：** `sudo ufw allow 5860/tcp`

**CentOS / RHEL：** `sudo firewall-cmd --permanent --add-port=5860/tcp && sudo firewall-cmd --reload`"""
if fw_old in text:
    text = text.replace(fw_old, fw_new, 1)
readme.write_text(text, encoding="utf-8")
print("patched README.md")
PY
