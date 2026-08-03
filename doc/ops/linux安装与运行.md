# CronPilot · Linux 安装（Ubuntu + CentOS）

完整步骤见 **[INSTALL.md](../../INSTALL.md)**。本文仅列平台差异。

## Docker 快速试用

不想在宿主机装 Python，或 apt/dpkg 有问题时：

```bash
cp conf.ini.example conf.ini   # 必须，否则 conf.ini 可能被挂载成目录
docker compose up --build -d
# http://<IP>:5860/  用户名 admin · 初始密码见 login_pwd（常 changeme）；改密走用户管理
```

详见 **[Docker部署指南.md](Docker部署指南.md)**。

## 统一命令（裸机）

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
- [Docker部署指南.md](Docker部署指南.md) — 容器部署

## 安装失败

```bash
sudo bash scripts/fix_broken_install.sh --install
```

无 sudo 装 Python：见 [INSTALL.md](../../INSTALL.md) 路径 C（pyenv）。
