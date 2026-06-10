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

## 路径 A：试用（SQLite）

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
bash scripts/run_production.sh      # 生产启动 :5860
bash scripts/start_local.sh         # 开发启动 :5001
bash scripts/cronpilot.sh test      # 单元测试
bash scripts/check_python_all.sh    # 查看 Python / venv
```

---

## 安装失败

```bash
sudo bash scripts/fix_broken_install.sh
```

| 现象 | 处理 |
|------|------|
| `postgresql-* is not configured` | **与 CronPilot 无关**（本机历史 PG 包损坏）。不需 PG：见下方「移除 PG」；**要保留 PG**：见下方「保留 PG 修 dpkg」 |
| `redis-server is not configured` | 同上 fix 脚本；单机试用可不装 Redis |
| `.venv-py39/bin/pip: No such file` | fix 脚本，或 `sudo apt-get install -y python3.9-venv` 后 `rm -rf .venv-py39 && bash scripts/bootstrap_venv.sh` |
| `pip install gevent` 失败 | 确认 `--production` 且已装 `libev-dev`（Ubuntu）/ `libev-devel`（CentOS） |

### 保留 PostgreSQL，只修 dpkg

CronPilot 不装 PostgreSQL；报错来自本机已有 PG 9.5 未配置完成。按顺序执行：

```bash
# 1. 查看哪一步失败
sudo dpkg --configure -a 2>&1 | tail -20
sudo tail -30 /var/log/dpkg.log

# 2. 常见修复：目录与用户
sudo mkdir -p /var/lib/postgresql
sudo id postgres &>/dev/null || sudo useradd -r -s /bin/bash -d /var/lib/postgresql -m postgres
sudo chown -R postgres:postgres /var/lib/postgresql
sudo chmod 700 /var/lib/postgresql

# 3. 查看集群状态（Ubuntu 16.04 多为 9.5 main）
sudo pg_lsclusters

# 4. 集群 down 时尝试启动；无集群则创建（会初始化空库，慎用覆盖已有数据目录）
# sudo pg_ctlcluster 9.5 main start
# 或仅当 pg_lsclusters 为空且无旧数据时：
# sudo pg_createcluster 9.5 main

# 5. 重新配置包
sudo dpkg --configure postgresql-common
sudo dpkg --configure postgresql-9.5
sudo dpkg --configure -a
sudo apt-get install -y -f

# 6. 验证 PG 与 apt
sudo pg_lsclusters
dpkg -l | grep postgresql | grep -v '^ii'
```

`dpkg --configure postgresql-common` 仍失败时，看具体报错：

```bash
sudo bash -x /var/lib/dpkg/info/postgresql-common.postinst configure 2>&1 | tail -30
```

修好 apt 后再装 CronPilot：

```bash
cd CronPilot
sudo bash scripts/install_linux.sh --production --sqlite
bash scripts/run_production.sh
```

### 不需要 PostgreSQL（移除坏包）

```bash
sudo apt-get remove --purge -y postgresql-9.5 postgresql-contrib-9.5 \
  postgresql-plpython3-9.5 postgresql-common
sudo apt-get autoremove -y && sudo apt-get install -y -f
```

---

## 分平台说明

- [doc/linux安装与运行.md](doc/linux安装与运行.md)
- [doc/ubuntu安装与运行.md](doc/ubuntu安装与运行.md)
- [doc/centos安装与运行.md](doc/centos安装与运行.md)
