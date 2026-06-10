#!/bin/bash
# 精简 README「非 Docker 部署」章节，指向 INSTALL.md
# 用法: sudo bash scripts/patch_readme_install.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python3 <<'PY'
from pathlib import Path
readme = Path("README.md")
text = readme.read_text(encoding="utf-8")

start = "## 非 Docker 部署（生产 / 远程访问）"
end = "## Release Notes"
if start not in text or end not in text:
    raise SystemExit("README 锚点未找到")

new_section = """## 非 Docker 部署（Linux）

**安装步骤见 [INSTALL.md](INSTALL.md)。**

```bash
# 试用（SQLite）
sudo bash scripts/install_linux.sh --production --sqlite
bash scripts/run_production.sh

# 生产（MySQL）：去掉 --sqlite，按 INSTALL.md 配置 conf.ini 后启动
```

| 入口 | URL |
|------|-----|
| 管理端 | `http://<IP>:5860/` |
| 文档 | `http://<IP>:5860/docs/` |

- macOS 本地开发：`bash scripts/cronpilot.sh start`（:5001）
- systemd / Nginx / 安全：[非Docker部署指南](doc/非Docker部署指南.html)

"""

idx_s = text.index(start)
idx_e = text.index(end)
text = text[:idx_s] + new_section + text[idx_e:]
readme.write_text(text, encoding="utf-8")
print("patched README.md")
PY
