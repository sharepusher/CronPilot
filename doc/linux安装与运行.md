# CronPilot · Linux 安装与运行（Ubuntu + CentOS）

## 统一入口（自动识别发行版）

```bash
git clone git@github.com:sharepusher/CronPilot.git
cd CronPilot
sudo bash scripts/install_linux.sh --production --sqlite
bash scripts/run_production.sh
```

| 检测到 | 调用脚本 |
|--------|----------|
| Ubuntu / Debian | `install_ubuntu.sh` |
| CentOS / RHEL / Rocky / Alma | `install_centos.sh` |

## 分平台文档

- [ubuntu安装与运行.md](ubuntu安装与运行.md) — Ubuntu 20.04 / 22.04 / 24.04
- [centos安装与运行.md](centos安装与运行.md) — CentOS 7 / 8、RHEL、Rocky、Alma

## 通用脚本（两平台相同）

| 脚本 | 用途 |
|------|------|
| `bootstrap_venv.sh` | Python 3.8–3.11 自动匹配 + 核心依赖 |
| `install_production_deps.sh` | Gunicorn + gevent |
| `run_production.sh` | 生产启动 `:5860` |
| `start_local.sh` | 开发 `:5001` |

## 环境要求（一致）

- Python **3.8～3.11**
- 生产需能编译/安装 **gevent**（libev 开发包）
- 数据库：SQLite（试用）或 MySQL（生产）
