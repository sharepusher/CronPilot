# CronPilot · Ubuntu 安装与运行

> HTML 部署总览：[非Docker部署指南.html](非Docker部署指南.html)

适用 **Ubuntu 20.04 / 22.04 / 24.04**，非 Docker 裸机部署。  
**CentOS 7/8** 见 [centos安装与运行.md](centos安装与运行.md)；**自动识别**见 [linux安装与运行.md](linux安装与运行.md)。

## 一、系统要求

| 项 | 要求 |
|----|------|
| Python | **3.8～3.11**（脚本自动选择；24.04 建议安装 `python3.11`） |
| 数据库 | 试用：**SQLite**；生产：**MySQL** |
| Redis | 集群多机时需要；单机 `is_single=1` 可省略 |
| 端口 | 生产 **5860**（Gunicorn） |

## 二、一键安装（推荐）

```bash
git clone git@github.com:sharepusher/CronPilot.git
cd CronPilot

# 试用：SQLite + 核心依赖 + 生产依赖（Gunicorn/gevent）
sudo bash scripts/install_linux.sh --production --sqlite
# 或: sudo bash scripts/install_ubuntu.sh --production --sqlite
```

以部署用户（非 root）启动：

```bash
bash scripts/run_production.sh
# 或开发冒烟（127.0.0.1:5001）
bash scripts/start_local.sh
```

访问：

- 管理端：`http://<服务器IP>:5860/`（默认密码 `changeme`，请尽快修改 `conf.ini`）
- 文档：`http://<服务器IP>:5860/docs/`

## 三、分步安装

### 3.1 系统包（root）

```bash
sudo apt-get update
sudo apt-get install -y git curl build-essential libffi-dev libev-dev \
  python3-venv python3-dev python3.11 python3.11-venv python3.11-dev
# 22.04 可用 python3.10；20.04 可用 python3.8
```

### 3.2 Python 虚拟环境与依赖

```bash
cd CronPilot
bash scripts/check_python.sh
bash scripts/bootstrap_venv.sh          # 核心依赖 requirements-core.txt
bash scripts/install_production_deps.sh  # 生产：requirements.txt（需 libev-dev）
```

### 3.3 配置

```bash
cp conf.ini.example conf.ini
# 编辑 login_pwd、cron_db_url、cron_job_log_db_url

bash scripts/cronpilot.sh exec python scripts/hash_login_password.py '强密码'
```

**SQLite 单机示例**（路径改为实际目录）：

```ini
cron_db_url=sqlite:////opt/cronpilot/CronPilot/datas/cron.sqlite
cron_job_log_db_url=sqlite:////opt/cronpilot/CronPilot/datas/job_log.sqlite
```

### 3.4 启动与自检

```bash
mkdir -p datas/logs
export FLASK_CONFIG=production
bash scripts/run_production.sh

curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5860/docs/
bash scripts/cronpilot.sh test
```

## 四、systemd（开机自启）

```bash
# 编辑 WorkingDirectory、ExecStart 中的 .venv-py311 路径
sudo cp scripts/systemd/cronpilot.service.example /etc/systemd/system/cronpilot.service
sudo nano /etc/systemd/system/cronpilot.service

sudo systemctl daemon-reload
sudo systemctl enable --now cronpilot
sudo systemctl status cronpilot
```

## 五、防火墙

```bash
sudo ufw allow 5860/tcp
```

## 六、常见问题（Ubuntu）

| 现象 | 处理 |
|------|------|
| `gevent` 编译失败 | `sudo apt-get install -y build-essential libev-dev python3.11-dev` |
| 仅有 Python 3.12 | `sudo apt-get install -y python3.11 python3.11-venv` |
| `Permission denied` venv | 勿用 `sudo pip`；用 `install_ubuntu.sh` 或部署用户执行 `bootstrap_venv.sh` |
| 无法连 MySQL | 试用加 `--sqlite`；或检查 `cron_db_url` 与 MySQL 服务 |
| 5860 无法访问 | `ufw`/安全组放行；确认 `gun.py` 中 `0.0.0.0:5860` |

## 七、脚本索引

| 脚本 | 用途 |
|------|------|
| `scripts/install_ubuntu.sh` | Ubuntu 一键装系统包 + Python 依赖 |
| `scripts/bootstrap_venv.sh` | 创建 venv + 核心依赖 |
| `scripts/install_production_deps.sh` | Gunicorn + gevent |
| `scripts/run_production.sh` | 生产启动 |
| `scripts/cronpilot.sh` | 统一入口 start/test/install |
| `scripts/start_local.sh` | 本地 5001 开发 |
