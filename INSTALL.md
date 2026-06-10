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

## 安装失败（一键修复）

```bash
sudo bash scripts/fix_broken_install.sh              # 修 dpkg（保留 PG）+ venv
sudo bash scripts/fix_broken_install.sh --install    # 修复后继续安装 CronPilot（SQLite 试用）
sudo bash scripts/fix_broken_install.sh --purge-pg    # 不保留 PostgreSQL 时强制删除 PG 包
```

| 现象 | 说明 |
|------|------|
| `postgresql-* is not configured` | 本机旧 PG 包损坏；上条命令**默认保留 PG** 只修 dpkg |
| `redis-server is not configured` | 同上；SQLite 单机可不装 Redis |
| `.venv-py39/bin/pip: No such file` | 脚本会自动删坏 venv 并重建 |
| `pip install gevent` 失败 | 确认 `--production` 且已装 `libev-dev` |

---

## 分平台说明

- [doc/linux安装与运行.md](doc/linux安装与运行.md)
- [doc/ubuntu安装与运行.md](doc/ubuntu安装与运行.md)
- [doc/centos安装与运行.md](doc/centos安装与运行.md)
