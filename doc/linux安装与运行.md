# CronPilot · Linux 安装（Ubuntu + CentOS）

完整步骤见 **[INSTALL.md](../INSTALL.md)**。本文仅列平台差异。

## 统一命令

```bash
sudo bash scripts/install_linux.sh --production          # 生产 MySQL
sudo bash scripts/install_linux.sh --production --sqlite # 试用 SQLite
bash scripts/run_production.sh
```

| 检测到 | 脚本 |
|--------|------|
| Ubuntu / Debian | `install_ubuntu.sh` |
| CentOS / RHEL / Rocky / Alma | `install_centos.sh` |

## 分平台

- [ubuntu安装与运行.md](ubuntu安装与运行.md) — Ubuntu 20.04+
- [centos安装与运行.md](centos安装与运行.md) — CentOS 7/8

## 安装失败

```bash
sudo bash scripts/fix_broken_install.sh
```
