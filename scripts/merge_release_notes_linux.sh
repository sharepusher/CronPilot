#!/bin/bash
# 将 doc/RELEASE_NOTES_v0.1.1_ubuntu.md 中的 Linux 段落合并进 RELEASE_NOTES.md
# 用法: sudo bash scripts/merge_release_notes_linux.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RN="$ROOT/RELEASE_NOTES.md"
MARKER="### CI（GitHub Actions）"
INSERT_FILE="$ROOT/doc/RELEASE_NOTES_v0.1.1_ubuntu.md"

if [ ! -f "$RN" ]; then
  echo "缺少 $RN" >&2
  exit 1
fi

if grep -q "Linux 安装与运行（Ubuntu + CentOS" "$RN" 2>/dev/null; then
  echo "RELEASE_NOTES.md 已包含 Linux 安装段落，跳过。"
  exit 0
fi

BLOCK=$(cat <<'BLOCK'
### Linux 安装与运行（Ubuntu + CentOS 7/8）

| 脚本 / 文档 | 说明 |
|-------------|------|
| `scripts/install_linux.sh` | **统一入口**，自动识别 Ubuntu / CentOS |
| `scripts/install_ubuntu.sh` | Ubuntu 20.04 / 22.04 / 24.04 |
| `scripts/install_centos.sh` | CentOS 7（SCL rh-python38）/ 8（python39） |
| `scripts/check_python_all.sh` | 探测 3.8–3.11（含 SCL 路径） |
| `doc/linux安装与运行.md` | 双平台总览 |
| `INSTALL.md` | 本仓库安装速查 |

```bash
sudo bash scripts/install_linux.sh --production --sqlite
bash scripts/run_production.sh
```

CentOS 7：`scl enable rh-python38 bash` 或见 `doc/centos安装与运行.md`。

BLOCK
)

python3 - <<PY
from pathlib import Path
rn = Path("$RN")
text = rn.read_text(encoding="utf-8")
marker = "$MARKER"
block = """$BLOCK"""
if "Linux 安装与运行（Ubuntu + CentOS" in text:
    print("already merged")
    raise SystemExit(0)
if marker not in text:
    raise SystemExit(f"marker not found: {marker}")
text = text.replace(marker, block + "\n" + marker, 1)
rn.write_text(text, encoding="utf-8")
print("merged into RELEASE_NOTES.md")
PY
