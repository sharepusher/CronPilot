# CronPilot · CentOS 7 / 8 安装与运行

> 通用入口：[linux安装与运行.md](linux安装与运行.md) · Ubuntu：[ubuntu安装与运行.md](ubuntu安装与运行.md)

## 一、版本与 Python

| 系统 | 推荐 Python | 说明 |
|------|-------------|------|
| **CentOS 7** | **3.8**（SCL `rh-python38`） | 系统自带常为 3.6，**不满足** CronPilot 要求 |
| **CentOS 8** | **3.9+**（`python39` 模块） | 可用 `dnf install python39` |
| Rocky / Alma 8 | 同 CentOS 8 | 使用 `install_centos.sh` |

应用要求：**Python 3.8～3.11**（与 Ubuntu 相同）。

## 二、一键安装（推荐）

```bash
git clone git@github.com:sharepusher/CronPilot.git
cd CronPilot

# 自动识别 CentOS → install_centos.sh
sudo bash scripts/install_linux.sh --production --sqlite

bash scripts/run_production.sh
```

或显式：

```bash
sudo bash scripts/install_centos.sh --production --sqlite
```

## 三、CentOS 7 分步说明

```bash
# root
sudo yum install -y epel-release centos-release-scl
sudo yum install -y git gcc make libffi-devel openssl-devel libev-devel
sudo yum install -y rh-python38 rh-python38-python-devel rh-python38-python-pip

# 部署用户
cd CronPilot
export PATH="/opt/rh/rh-python38/root/usr/bin:$PATH"
export PY=/opt/rh/rh-python38/root/usr/bin/python3.8
bash scripts/bootstrap_venv.sh
bash scripts/install_production_deps.sh

cp conf.ini.example conf.ini
# 配置 SQLite 或 MySQL
bash scripts/run_production.sh
```

长期会话可加：`scl enable rh-python38 bash`

## 四、CentOS 8 分步说明

```bash
sudo dnf install -y epel-release
sudo dnf install -y git gcc make libffi-devel openssl-devel libev-devel
sudo dnf install -y python39 python39-devel python39-pip

cd CronPilot
export PY=python3.9
bash scripts/bootstrap_venv.sh
bash scripts/install_production_deps.sh
bash scripts/run_production.sh
```

## 五、防火墙与 SELinux

```bash
# firewalld（CentOS 默认）
sudo firewall-cmd --permanent --add-port=5860/tcp
sudo firewall-cmd --reload

# SELinux：若服务已起但无法访问，排查
sudo ausearch -m avc -ts recent
# 或临时测试: sudo setenforce 0（生产请配置正确策略）
```

## 六、systemd

```bash
sudo cp scripts/systemd/cronpilot.service.example /etc/systemd/system/cronpilot.service
# 修改 WorkingDirectory、ExecStart 中 .venv-py38 或 .venv-py39 路径
sudo systemctl daemon-reload
sudo systemctl enable --now cronpilot
```

## 七、与 Ubuntu 的差异摘要

| 项 | CentOS 7/8 | Ubuntu |
|----|------------|--------|
| 包管理 | `yum` / `dnf` | `apt` |
| gevent 编译依赖 | `libev-devel` | `libev-dev` |
| Python 7 | SCL `rh-python38` | `apt install python3.8` |
| 防火墙 | `firewalld` | `ufw` |
| SELinux | 常见 | 少见 |
| 一键脚本 | `install_centos.sh` | `install_ubuntu.sh` |

应用层（`conf.ini`、Gunicorn、`/docs/`、API）**无区别**。

## 八、常见问题

| 现象 | 处理 |
|------|------|
| 找不到 python3.8 | CentOS7 安装 `rh-python38`，`export PATH=/opt/rh/rh-python38/root/usr/bin:$PATH` |
| gevent 编译失败 | 安装 `gcc make libev-devel libffi-devel openssl-devel` |
| 5860 不通 | `firewalld` + 云安全组 + SELinux |
| 仍用 python 3.6 | **不可运行**，必须 3.8+ |
