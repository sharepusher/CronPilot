# CronPilot · Linux 安装

支持 **Ubuntu / Debian**、**CentOS 7/8**、Rocky、Alma。  
Python 3.8–3.11，自动创建 `.venv-py*`，无需手动 `source activate`。

---

## 路径 A：试用（SQLite，3 条命令）

```bash
git clone https://github.com/sharepusher/CronPilot.git
cd CronPilot
sudo bash scripts/install_linux.sh --production --sqlite
bash scripts/run_production.sh
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
| `.venv-py39/bin/pip: No such file` | 上条命令，或 `sudo apt-get install -y python3.9-venv` 后 `rm -rf .venv-py39 && bash scripts/bootstrap_venv.sh` |
| `redis-server is not configured` | `sudo dpkg --configure -a && sudo apt-get install -y -f`（单机试用可不装 Redis） |
| `pip install gevent` 失败 | 确认已加 `--production` 且系统有 `libev-dev`（Ubuntu）/ `libev-devel`（CentOS） |

---

## 分平台说明

- [doc/linux安装与运行.md](doc/linux安装与运行.md)
- [doc/ubuntu安装与运行.md](doc/ubuntu安装与运行.md)
- [doc/centos安装与运行.md](doc/centos安装与运行.md)
