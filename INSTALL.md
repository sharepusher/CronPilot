# CronPilot · Linux 安装

支持 **Ubuntu / Debian**、**CentOS 7/8**、Rocky、Alma。  
Python 3.8–3.11，自动创建 `.venv-py*`，无需手动 `source activate`。

## 两步分别做什么

| 命令 | 做什么 | 会不会打开网页 |
|------|--------|----------------|
| `install_linux.sh` | 装系统包、建 venv、装 Python 依赖、生成 `conf.ini` | **不会** — 装完就退出 |
| `run_production.sh` | 启动 Gunicorn，监听 `:5860` | **会** — 进程需一直运行 |

`install` = 准备环境（装软件）；`run` = 启动服务（跑起来）。  
生产环境常把 `run` 交给 **systemd** 开机自启，见 [非Docker部署指南](doc/非Docker部署指南.html)。

---

## Python 与虚拟环境：为什么有时要 sudo？

CronPilot 安装分 **两层**，职责不同：

| 层级 | 是否需要 sudo | 装什么 | 装在哪 |
|------|---------------|--------|--------|
| **Python 解释器** | apt 需要；pyenv 不需要 | `python3.9` 可执行文件 | `/usr/bin` 或 `~/.pyenv` |
| **项目 venv** | **不需要** | Flask、gunicorn 等 pip 包 | 项目内 `.venv-py39` |

虚拟环境 **不能替代安装 Python**。`python3.9 -m venv .venv-py39` 要求机器上 **已有** `python3.9`；venv 只隔离 pip 依赖，**不包含 Python 本身**。

- **sudo apt**：解释器装到系统路径（有 root、apt 正常时推荐）。
- **pyenv**：解释器装到 `~/.pyenv`（无 sudo 或 dpkg 损坏时）。

应用依赖始终在 `.venv-py*` 里，不会装到系统 site-packages。

---

## 部署路径一览

| 路径 | 场景 | 需要 Docker | 需要 sudo（宿主机） |
|------|------|-------------|---------------------|
| **A** SQLite 裸机 | 有 root、apt 正常 | 否 | 是（装系统 Python） |
| **B** MySQL 裸机 | 生产、自建 MySQL | 否 | 是 |
| **C** pyenv 裸机 | 无 sudo / dpkg 坏 | 否 | 否（Python 在 ~/.pyenv） |
| **D** Docker | 快速试用、隔离环境 | **是** | 否（容器内完成安装） |

---

## 路径 A：试用（SQLite，推荐 apt 一键装）

```bash
git clone https://github.com/sharepusher/CronPilot.git
cd CronPilot
sudo bash scripts/install_linux.sh --production --sqlite   # ① 安装（不启动服务）
bash scripts/run_production.sh                             # ② 启动（前台运行，Ctrl+C 停止）
```

| 项 | 值 |
|----|-----|
| 管理端 | `http://<IP>:5860/` |
| 文档 | `http://<IP>:5860/docs/` |
| 默认密码 | `changeme`（改 `conf.ini` → `login_pwd`） |

---

## 路径 B：生产（MySQL）

### 步骤 1 — 安装应用

```bash
git clone https://github.com/sharepusher/CronPilot.git
cd CronPilot
sudo bash scripts/install_linux.sh --production
```

### 步骤 2 — 准备 MySQL

```sql
CREATE DATABASE cron_scheduler CHARACTER SET utf8mb4;
CREATE DATABASE cron_job_log CHARACTER SET utf8mb4;
CREATE USER 'cronpilot'@'localhost' IDENTIFIED BY '你的密码';
GRANT ALL ON cron_scheduler.* TO 'cronpilot'@'localhost';
GRANT ALL ON cron_job_log.* TO 'cronpilot'@'localhost';
FLUSH PRIVILEGES;
```

### 步骤 3 — 配置 `conf.ini`

```bash
nano conf.ini
```

```ini
is_single=1
cron_db_url=mysql+pymysql://cronpilot:你的密码@127.0.0.1:3306/cron_scheduler
cron_job_log_db_url=mysql+pymysql://cronpilot:你的密码@127.0.0.1:3306/cron_job_log
login_pwd=你的管理端密码
```

可选：生成密码哈希

```bash
bash scripts/cronpilot.sh exec python scripts/hash_login_password.py '你的管理端密码'
```

### 步骤 4 — 启动

```bash
bash scripts/run_production.sh
```

### 步骤 5 — 放行端口

```bash
# Ubuntu
sudo ufw allow 5860/tcp

# CentOS / RHEL
sudo firewall-cmd --permanent --add-port=5860/tcp && sudo firewall-cmd --reload
```

---

## 路径 C：无 sudo 或 apt 损坏 — 用 pyenv 装 Python

适用：**没有 sudo**、**dpkg/PostgreSQL 卡住导致 apt 装不了 Python**、或 **不想改系统 Python**。

CronPilot **不使用 PostgreSQL**；若本机 PG 包损坏会阻塞 apt，需管理员先修 dpkg（见下方「安装失败」），**不必**用 apt 装 Python。

### 步骤 1 — 编译依赖（管理员一次性，可选但强烈建议）

pyenv 从源码编译 Python，需要编译器和头文件。这 **不是** 安装系统 Python，只是工具链：

```bash
sudo apt-get install -y build-essential libssl-dev zlib1g-dev \
  libbz2-dev libreadline-dev libsqlite3-dev libffi-dev liblzma-dev \
  curl git libev-dev
```

### 步骤 2 — 部署用户：pyenv + Python 3.9（无需 sudo）

```bash
cd CronPilot

curl -fsSL https://pyenv.run | bash

export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"

pyenv install -s 3.9.18
pyenv local 3.9.18

python --version    # 应显示 3.9.18
```

建议把下面三行写入 `~/.bashrc`，重新登录后生效：

```bash
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"
```

### 步骤 3 — 建 venv、装依赖、启动（无需 sudo）

```bash
export PY="$HOME/.pyenv/versions/3.9.18/bin/python"
bash scripts/bootstrap_venv.sh
bash scripts/install_production_deps.sh
bash scripts/run_production.sh
```

试用 SQLite 时：

```bash
cp conf.ini.example conf.ini
# 编辑 conf.ini：is_single=1，数据库 URL 改为 sqlite（见 conf.ini.example 注释）
```

### pyenv 常见编译错误

| 现象 | 处理 |
|------|------|
| `ModuleNotFoundError: _ssl` | `sudo apt-get install -y libssl-dev`，然后 `pyenv uninstall 3.9.18 && pyenv install 3.9.18` |
| `pyenv install` 整体失败 | 确认步骤 1 编译依赖已装；查看 `~/.pyenv/cache/` 下日志 |
| `bootstrap_venv` 找不到 Python | 显式 `export PY=~/.pyenv/versions/3.9.18/bin/python` 后重试 |

---

## 路径 D：Docker 部署（推荐快速试用）

> 完整说明：[doc/Docker部署指南.md](doc/Docker部署指南.md)

适用：**不想在宿主机装 Python**、**apt/dpkg 有问题**、或 **快速验证**。  
镜像基于 Ubuntu 22.04 + Python 3.9，容器内自动执行 `install_ubuntu.sh --production --sqlite`，**不依赖宿主机 PostgreSQL / deadsnakes**。

### 前置

- 已安装 [Docker](https://docs.docker.com/get-docker/) 与 Docker Compose v2
- 无需在宿主机执行 `install_linux.sh`

### 步骤 1 — 构建并启动

```bash
git clone https://github.com/sharepusher/CronPilot.git
cd CronPilot
cp conf.ini.example conf.ini   # 首次

docker compose up --build -d
```

| 项 | 值 |
|----|-----|
| 管理端 | `http://<宿主机IP>:5860/` |
| 文档 | `http://<宿主机IP>:5860/docs/` |
| 默认密码 | `changeme`（改挂载的 `conf.ini` → `login_pwd`） |
| 数据持久化 | 宿主机 `./datas` 挂载到容器 |

### 步骤 2 — 查看日志 / 停止

```bash
docker compose logs -f
docker compose down
```

### 自定义配置

编辑宿主机 `conf.ini` 后重启：

```bash
nano conf.ini
docker compose restart
```

生产使用 **MySQL** 时：在 `conf.ini` 配置 `cron_db_url`；MySQL 在宿主机时 URL 用 `host.docker.internal`（Mac/Win）或宿主机网桥 IP（Linux）。

### 手动构建（不用 compose）

```bash
docker build -t cronpilot:latest .
docker run --rm -p 5860:5860 \
  -v "$(pwd)/datas:/opt/cronpilot/datas" \
  -v "$(pwd)/conf.ini:/opt/cronpilot/conf.ini" \
  cronpilot:latest
```

### CI 与本地验收（开发者）

裸机安装脚本（非运行镜像）：

```bash
bash scripts/docker/verify_all.sh all
```

Mac 一键验收运行镜像：

```bash
bash scripts/verify_cronpilot_docker_mac.sh
```

### 变更说明（v0.1.1+）

| 旧版（已废弃） | 新版 |
|----------------|------|
| Ubuntu 16.04 + Python 3.6 | Ubuntu 22.04 + Python 3.9 |
| 容器 `:80` → 宿主机 `5002` | 统一 **`:5860`**（与裸机 `gun.py` 一致） |
| Supervisor + `docker_start.sh` | 直接 `scripts/run_production.sh` |
| 豆瓣 pip 源 | 容器内标准 `install_ubuntu.sh` |

`docker-compose.run.yml` 与 `docker-compose.yml` 等价（兼容旧命令 `-f docker-compose.run.yml`）。

---

## 安装参数

```bash
sudo bash scripts/install_linux.sh [--production] [--sqlite]
```

| 参数 | 作用 |
|------|------|
| `--production` | 安装 Gunicorn + gevent（生产必加） |
| `--sqlite` | 自动配置 SQLite，无需 MySQL |

---

## 常用命令

```bash
bash scripts/run_production.sh                 # 生产启动 :5860
bash scripts/start_local.sh                    # 开发启动 :5001
bash scripts/cronpilot.sh test                 # 单元测试
bash scripts/check_python_all.sh               # 查看 Python / venv
sudo bash scripts/install_python_ubuntu.sh     # 仅装系统 Python（apt，需 root）
bash scripts/bootstrap_venv.sh                 # 仅建/修 venv（需已有 Python 3.8–3.11）
```

---

## 安装失败（一键修复）

```bash
sudo bash scripts/fix_broken_install.sh              # 修 dpkg（保留 PG）+ Python + venv
sudo bash scripts/fix_broken_install.sh --install    # 修复后继续安装 CronPilot（SQLite 试用）
sudo bash scripts/fix_broken_install.sh --purge-pg   # 不保留 PostgreSQL 时强制删除 PG 包
```

### PostgreSQL dpkg 卡住（CronPilot 不用 PG，但会阻塞 apt）

若出现 `postgresql-common is not configured`、`postgresql-9.5 depends on postgresql-common`：

```bash
sudo mkdir -p /var/lib/postgresql /var/log/postgresql /var/run/postgresql
sudo id postgres || sudo useradd -r -g postgres -d /var/lib/postgresql -m postgres
sudo chown -R postgres:postgres /var/lib/postgresql /var/log/postgresql

sudo dpkg --configure postgresql-client-common
sudo dpkg --configure postgresql-common

sudo pg_lsclusters
sudo pg_ctlcluster 9.5 main start    # 若有集群但未 online
# 或无集群时: sudo pg_createcluster 9.5 main --start

sudo dpkg --configure postgresql-9.5 postgresql-contrib-9.5
sudo apt-get install -y -f
```

仍失败时诊断：

```bash
sudo bash -x /var/lib/dpkg/info/postgresql-common.postinst configure 2>&1 | tail -50
```

修完 dpkg 后：有 sudo 走 **路径 A**；无 sudo 或不想 apt 装 Python 走 **路径 C（pyenv）**。

### 其他常见问题

| 现象 | 说明 |
|------|------|
| `postgresql-* is not configured` | 见上节；`fix_broken_install.sh` **默认保留 PG** |
| `redis-server is not configured` | 同上；SQLite 单机可不装 Redis |
| 未找到 python3.8 / Unable to locate package | **Ubuntu 16.04 默认源无 3.8**；`sudo bash scripts/install_python_ubuntu.sh`；或 **路径 C pyenv** |
| Permission denied / dpkg lock | 所有 apt 命令前加 **sudo** |
| `.venv-py39/bin/pip: No such file` | `rm -rf .venv-py* && bash scripts/bootstrap_venv.sh` |
| `pip install gevent` 失败 | 确认 `--production` 且已装 `libev-dev`；或换 Python 3.9/3.10。长期见 [doc/依赖升级RFC.html](doc/依赖升级RFC.html) Tier 2 |
| 数据库迁移 CLI | `export FLASK_APP=manage:app` 后 `flask db migrate` / `flask db upgrade`（Py3.11 可用；见 [依赖升级 RFC](doc/依赖升级RFC.html) Tier 0） |

---

## 分平台说明

- [doc/linux安装与运行.md](doc/linux安装与运行.md)
- [doc/ubuntu安装与运行.md](doc/ubuntu安装与运行.md)
- [doc/centos安装与运行.md](doc/centos安装与运行.md)
