# CronPilot · Linux 安装指南（Ubuntu + CentOS 7/8）

## 数据库怎么选？

| 场景 | 推荐 | 说明 |
|------|------|------|
| **生产 / 正式环境** | **MySQL** | `conf.ini.example` 默认即 MySQL；支持多节点、`is_single=0` 时与 Redis 配合 |
| **本地试用 / 验收** | SQLite | 加 `--sqlite`，**无需安装 MySQL**，装完即可访问 `:5860` |

INSTALL.md 里曾把 `--sqlite` 写在最前面，是为了降低「第一次跑起来」的门槛，**不代表生产也用 SQLite**。生产请用下方 **MySQL 安装**。

---

## 虚拟环境（venv）— 自动创建，一般无需手动操作

**上述一键安装都会用到虚拟环境**，只是脚本替你做了，文档里之前没写清楚。

| 步骤 | 脚本 | 作用 |
|------|------|------|
| 1 | `install_linux.sh` → `bootstrap_venv.sh` | 自动选 Python 3.8–3.11，创建 **`.venv-py311`** 等目录 |
| 2 | `bootstrap_venv.sh` | 在 venv 内 `pip install -r requirements-core.txt` |
| 3 | `--production` 时 `install_production_deps.sh` | 在**同一 venv** 内安装 Gunicorn + gevent |
| 4 | `run_production.sh` / `start_local.sh` | 直接用 `$VENV/bin/gunicorn`、`$VENV/bin/python`，**不必**先 `source activate` |

安装完成后，项目根目录会出现类似：

```text
.venv-py311/          # Ubuntu 22.04 若探测到 python3.11
.venv-py38/           # CentOS 7 常用 SCL 3.8
.venv-py39/           # CentOS 8 常用 python3.9
```

查看本机将用哪个环境：

```bash
bash scripts/check_python_all.sh
# 或
bash scripts/cronpilot.sh check
```

**需要手动进 venv 时**（例如自己 `pip install`）：

```bash
source .venv-py311/bin/activate   # 按实际目录名
pip list
deactivate
```

**注意：** 安装脚本以**部署用户**（`sudo` 时的 `SUDO_USER`）创建 venv，不要用 `sudo pip` 装到系统 Python。

---

## 一键安装 · 生产（MySQL，推荐）

### 1. 安装应用与 Python 依赖

```bash
git clone https://github.com/sharepusher/CronPilot.git
cd CronPilot
sudo bash scripts/install_linux.sh --production
```

`install_linux.sh` 会自动识别发行版：

| 检测到 | 脚本 | Python |
|--------|------|--------|
| Ubuntu / Debian | `install_ubuntu.sh` | apt 安装 3.8–3.11 |
| CentOS 7 | `install_centos.sh` | SCL `rh-python38` |
| CentOS 8 / Rocky / Alma | `install_centos.sh` | `python39` |

### 2. 准备 MySQL

在目标机安装 MySQL 5.7+ / 8.0，并创建库与用户（示例）：

```sql
CREATE DATABASE cron_scheduler CHARACTER SET utf8mb4;
CREATE DATABASE cron_job_log CHARACTER SET utf8mb4;
CREATE USER 'cronpilot'@'localhost' IDENTIFIED BY '强密码';
GRANT ALL ON cron_scheduler.* TO 'cronpilot'@'localhost';
GRANT ALL ON cron_job_log.* TO 'cronpilot'@'localhost';
FLUSH PRIVILEGES;
```

### 3. 编辑 `conf.ini`

```bash
cp conf.ini.example conf.ini   # 若安装脚本已生成可跳过
nano conf.ini
```

```ini
is_single=1
cron_db_url=mysql+pymysql://cronpilot:强密码@127.0.0.1:3306/cron_scheduler
cron_job_log_db_url=mysql+pymysql://cronpilot:强密码@127.0.0.1:3306/cron_job_log
login_pwd=请改为强密码
```

生成密码哈希（推荐）：

```bash
bash scripts/cronpilot.sh exec python scripts/hash_login_password.py '你的强密码'
```

### 4. 启动

```bash
bash scripts/run_production.sh
```

---

## 一键安装 · 试用（SQLite，无需 MySQL）

适合：功能验收、演示、单机 POC。**不建议用于生产**（并发、备份、集群能力弱于 MySQL）。

```bash
git clone https://github.com/sharepusher/CronPilot.git
cd CronPilot
sudo bash scripts/install_linux.sh --production --sqlite
bash scripts/run_production.sh
```

`--sqlite` 会自动写入：

- `datas/cron.sqlite`、`datas/job_log.sqlite`
- `is_single=1`
- 默认登录密码 `changeme`（**请立即修改** `conf.ini`）

---

## 分平台文档

- [doc/linux安装与运行.md](doc/linux安装与运行.md)
- [doc/ubuntu安装与运行.md](doc/ubuntu安装与运行.md)
- [doc/centos安装与运行.md](doc/centos安装与运行.md)

## 检查 Python

```bash
bash scripts/check_python_all.sh   # 含 CentOS SCL 路径
bash scripts/cronpilot.sh check
```

## 防火墙

**Ubuntu：** `sudo ufw allow 5860/tcp`

**CentOS / RHEL：**

```bash
sudo firewall-cmd --permanent --add-port=5860/tcp
sudo firewall-cmd --reload
```

## 访问

- 管理端：`http://<IP>:5860/`
- 技术文档：`http://<IP>:5860/docs/`
